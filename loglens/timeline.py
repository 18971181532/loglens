"""Time-bucket aggregation and anomaly detection for log entries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .parser import LogEntry


BUCKET_CHOICES = ("minute", "5min", "15min", "hour", "day")

_BUCKET_SECONDS = {
    "minute": 60,
    "5min": 300,
    "15min": 900,
    "hour": 3600,
    "day": 86400,
}


def _bucket_key(dt: datetime, bucket: str) -> datetime:
    secs = _BUCKET_SECONDS[bucket]
    epoch = int(dt.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % secs))


@dataclass
class Bucket:
    time: str
    total: int = 0
    error: int = 0
    warning: int = 0
    info: int = 0
    debug: int = 0

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "total": self.total,
            "error": self.error,
            "warning": self.warning,
            "info": self.info,
            "debug": self.debug,
        }


def build_timeline(entries: List[LogEntry], bucket: str = "5min") -> List[Bucket]:
    """Aggregate entries into time buckets."""
    if bucket not in _BUCKET_SECONDS:
        bucket = "5min"
    buckets: Dict[datetime, Bucket] = {}
    for e in entries:
        if e.timestamp is None:
            continue
        key = _bucket_key(e.timestamp, bucket)
        b = buckets.get(key)
        if b is None:
            b = Bucket(time=key.strftime("%Y-%m-%d %H:%M:%S"))
            buckets[key] = b
        b.total += 1
        lvl = e.level
        if lvl in ("ERROR", "CRITICAL"):
            b.error += 1
        elif lvl == "WARNING":
            b.warning += 1
        elif lvl == "DEBUG":
            b.debug += 1
        else:
            b.info += 1
    return [buckets[k] for k in sorted(buckets)]


def detect_anomalies(timeline: List[Bucket], window: int = 7,
                     threshold: float = 2.5) -> List[dict]:
    """Sliding-window z-score anomaly detection on total counts.

    A bucket is anomalous if its total is > mean + threshold * stddev
    of the preceding `window` buckets.
    """
    anomalies = []
    if len(timeline) <= window:
        return anomalies
    counts = [b.total for b in timeline]
    for i in range(window, len(timeline)):
        hist = counts[i - window:i]
        mean = sum(hist) / len(hist)
        var = sum((x - mean) ** 2 for x in hist) / len(hist)
        std = var ** 0.5
        if std == 0:
            # no variance in history — any nonzero spike is anomalous
            if counts[i] > mean and counts[i] > 0:
                anomalies.append({
                    "time": timeline[i].time,
                    "count": counts[i],
                    "expected": round(mean, 1),
                    "zscore": 999.0,
                    "error": timeline[i].error,
                })
            continue
        if counts[i] > mean + threshold * std:
            anomalies.append({
                "time": timeline[i].time,
                "count": counts[i],
                "expected": round(mean, 1),
                "zscore": round((counts[i] - mean) / std, 2),
                "error": timeline[i].error,
            })
    return anomalies


def time_range(entries: List[LogEntry]) -> Tuple[Optional[str], Optional[str]]:
    times = [e.timestamp for e in entries if e.timestamp]
    if not times:
        return None, None
    return min(times).isoformat(), max(times).isoformat()
