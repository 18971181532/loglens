"""Multi-format log parser with auto-detection.

Supports:
- JSON lines ({"timestamp": ..., "level": ..., "message": ...})
- syslog (MMM DD HH:MM:SS host process[pid]: message)
- nginx access log
- common: 2024-01-01 12:00:00 INFO message  /  2024-01-01T12:00:00Z INFO message
- generic fallback (best-effort timestamp + level extraction)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


LEVELS = {"TRACE", "DEBUG", "INFO", "NOTICE", "WARN", "WARNING", "ERROR", "ERR",
          "CRIT", "CRITICAL", "ALERT", "EMERG", "FATAL"}

LEVEL_NORMALIZE = {
    "WARN": "WARNING", "ERR": "ERROR", "CRIT": "CRITICAL",
    "FATAL": "CRITICAL", "EMERG": "CRITICAL", "NOTICE": "INFO",
    "TRACE": "DEBUG",
}


@dataclass
class LogEntry:
    timestamp: Optional[datetime]
    level: str
    source: str
    message: str
    raw: str
    line_no: int = 0


# --- timestamp patterns ---

_TS_ISO = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_TS_SYSLOG = re.compile(
    r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
)
_TS_NGINX = re.compile(r"\[(\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2}\s+[+-]\d{4})\]")
_TS_EPOCH = re.compile(r"^\s*(\d{10}(?:\.\d+)?)\s")

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _parse_iso(s: str) -> Optional[datetime]:
    s = s.strip()
    # normalize Z and tz without colon
    s = s.replace("Z", "+00:00").replace("T", " ")
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:?\d{2})?$", s)
    if not m:
        return None
    base, frac, tz = m.groups()
    fmt = "%Y-%m-%d %H:%M:%S"
    if frac:
        fmt += ".%f"
        base += frac
    try:
        dt = datetime.strptime(base, fmt)
    except ValueError:
        return None
    if tz:
        # keep naive but record; we don't need tz for bucketing
        pass
    return dt


def _parse_syslog_ts(s: str) -> Optional[datetime]:
    # MMM DD HH:MM:SS — assume current year
    m = _TS_SYSLOG.match(s)
    if not m:
        return None
    parts = m.group(1).split()
    mon = _MONTHS.get(parts[0])
    if not mon:
        return None
    day = int(parts[1])
    h, mi, se = parts[2].split(":")
    return datetime(datetime.now().year, mon, day, int(h), int(mi), int(se))


def _parse_nginx_ts(s: str) -> Optional[datetime]:
    m = _TS_NGINX.search(s)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None


# --- format-specific parsers ---

def _parse_json_line(line: str) -> Optional[LogEntry]:
    line = line.strip()
    if not (line.startswith("{") and line.endswith("}")):
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    ts_raw = (obj.get("timestamp") or obj.get("time") or obj.get("@timestamp")
              or obj.get("ts") or obj.get("@time"))
    ts = None
    if isinstance(ts_raw, (int, float)):
        try:
            ts = datetime.fromtimestamp(float(ts_raw))
        except (OSError, ValueError, OverflowError):
            ts = None
    elif isinstance(ts_raw, str):
        ts = _parse_iso(ts_raw)
    level = str(obj.get("level") or obj.get("severity") or obj.get("loglevel")
                 or obj.get("log.level") or "INFO").upper()
    level = LEVEL_NORMALIZE.get(level, level)
    msg = str(obj.get("message") or obj.get("msg") or obj.get("log")
              or obj.get("body") or "")
    source = str(obj.get("source") or obj.get("logger") or obj.get("service")
                 or obj.get("name") or "json")
    return LogEntry(timestamp=ts, level=level, source=source,
                    message=msg, raw=line)


_SYSLOG_RE = re.compile(
    r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s*(.*)$"
)


def _parse_syslog_line(line: str) -> Optional[LogEntry]:
    ts = _parse_syslog_ts(line)
    if ts is None:
        return None
    m = _SYSLOG_RE.match(line)
    if m:
        host, proc, pid, msg = m.groups()
        source = f"{proc}[{pid}]" if pid else proc
    else:
        host, source, msg = "", "syslog", line
    return LogEntry(timestamp=ts, level="INFO", source=source,
                    message=msg, raw=line)


_NGINX_RE = re.compile(
    r'^(\S+)\s+\S+\s+\S+\s+\[[^\]]+\]\s+"(\S+)\s+(\S+)\s+\S+"\s+(\d{3})\s+(\d+|-)'
)


def _parse_nginx_line(line: str) -> Optional[LogEntry]:
    ts = _parse_nginx_ts(line)
    if ts is None:
        return None
    m = _NGINX_RE.match(line)
    if not m:
        return LogEntry(timestamp=ts, level="INFO", source="nginx",
                        message=line, raw=line)
    ip, method, path, status, size = m.groups()
    code = int(status)
    level = "ERROR" if code >= 500 else ("WARNING" if code >= 400 else "INFO")
    msg = f"{method} {path} {status} {size} from {ip}"
    return LogEntry(timestamp=ts, level=level, source="nginx",
                    message=msg, raw=line)


def _parse_common_line(line: str) -> Optional[LogEntry]:
    """2024-01-01 12:00:00 INFO source: message  (source optional)."""
    m = _TS_ISO.match(line)
    if not m:
        return None
    ts = _parse_iso(m.group(1))
    rest = line[m.end():].strip()
    # extract level
    level = "INFO"
    lm = re.match(r"([A-Z]+)\s+", rest)
    if lm and lm.group(1) in LEVELS:
        level = LEVEL_NORMALIZE.get(lm.group(1), lm.group(1))
        rest = rest[lm.end():]
    # extract "source: message"
    source = "app"
    sm = re.match(r"([\w.\-/\[\]]+):\s+", rest)
    if sm:
        source = sm.group(1)
        rest = rest[sm.end():]
    return LogEntry(timestamp=ts, level=level, source=source,
                    message=rest, raw=line)


def _parse_generic_line(line: str, line_no: int) -> LogEntry:
    """Best-effort: try timestamp anywhere, then level keyword."""
    ts = None
    m = _TS_ISO.search(line)
    if m:
        ts = _parse_iso(m.group(1))
    else:
        m = _TS_EPOCH.match(line)
        if m:
            try:
                ts = datetime.fromtimestamp(float(m.group(1)))
            except (OSError, ValueError, OverflowError):
                pass
    level = "INFO"
    for kw in ("ERROR", "CRITICAL", "FATAL", "WARNING", "WARN", "DEBUG", "TRACE", "INFO"):
        if re.search(r"\b" + kw + r"\b", line, re.IGNORECASE):
            level = LEVEL_NORMALIZE.get(kw, kw)
            break
    return LogEntry(timestamp=ts, level=level, source="generic",
                    message=line.strip(), raw=line, line_no=line_no)


_PARSERS = [_parse_json_line, _parse_syslog_line, _parse_nginx_line, _parse_common_line]


def parse_line(line: str, line_no: int = 0) -> LogEntry:
    """Parse a single log line, auto-detecting format."""
    if not line.strip():
        return LogEntry(timestamp=None, level="INFO", source="",
                        message="", raw=line, line_no=line_no)
    for p in _PARSERS:
        try:
            entry = p(line)
        except Exception:
            continue
        if entry is not None:
            entry.line_no = line_no
            return entry
    return _parse_generic_line(line, line_no)


def parse_lines(lines) -> List[LogEntry]:
    return [parse_line(line, i + 1) for i, line in enumerate(lines)]


def parse_file(path: str) -> List[LogEntry]:
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            entries.append(parse_line(line.rstrip("\n"), i))
    return entries
