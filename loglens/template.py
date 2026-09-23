"""Message templating and log clustering.

The core idea: variable parts of a log message (numbers, UUIDs, IPs, paths,
URLs, emails, hex strings, quoted strings) are replaced with placeholders,
producing a stable *template*. Messages sharing a template are the same
*event type* and form a cluster.

This is a simplified, dependency-free version of the Drain / Spell approach.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .parser import LogEntry


# order matters: more specific patterns first
_PATTERNS = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<UUID>"),
    (re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.I), "<MAC>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b[0-9a-f]{32,}\b", re.I), "<HEX>"),
    (re.compile(r"https?://\S+"), "<URL>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<EMAIL>"),
    (re.compile(r"(?:^|[\s(])/(?:[\w.-]+/?)+"), "<PATH>"),
    (re.compile(r'"[^"]*"'), "<QSTR>"),
    (re.compile(r"'[^']*'"), "<QSTR>"),
    (re.compile(r"\b\d+\.\d+\.\d+(?:[.-][\w.-]+)?\b"), "<VERSION>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<DATE>"),
    (re.compile(r"\b\d{2}:\d{2}(?::\d{2})?\b"), "<TIME>"),
    (re.compile(r"\b\d+(?:\.\d+)?(?![\d.])"), "<NUM>"),
]

# tokens that are too generic to be useful as template discriminators
_STOP_TOKENS = {"the", "a", "an", "to", "of", "for", "in", "on", "at", "with",
                "by", "from", "is", "was", "be", "been", "being", "and", "or",
                "not", "no", "as", "it", "its", "this", "that", "these", "those"}


def template_of(message: str) -> str:
    """Return the templated form of a message."""
    t = message
    for pat, repl in _PATTERNS:
        t = pat.sub(repl, t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def signature(template: str) -> str:
    """A shorter signature for fuzzy matching: content tokens only."""
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", template)
    tokens = [t for t in tokens if t.lower() not in _STOP_TOKENS and len(t) > 1]
    return " ".join(tokens[:12])


@dataclass
class Cluster:
    template: str
    count: int = 0
    level_counts: Dict[str, int] = field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    sample: str = ""
    sources: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "template": self.template,
            "count": self.count,
            "level_counts": self.level_counts,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "sample": self.sample,
            "sources": self.sources,
            "dominant_level": max(self.level_counts, key=self.level_counts.get)
                if self.level_counts else "INFO",
        }


def cluster_entries(entries: List[LogEntry]) -> List[Cluster]:
    """Group entries by template, return clusters sorted by count desc."""
    groups: Dict[str, Cluster] = {}
    for e in entries:
        if not e.message.strip():
            continue
        tmpl = template_of(e.message)
        c = groups.get(tmpl)
        if c is None:
            c = Cluster(template=tmpl, sample=e.message[:300])
            groups[tmpl] = c
        c.count += 1
        c.level_counts[e.level] = c.level_counts.get(e.level, 0) + 1
        c.sources[e.source] = c.sources.get(e.source, 0) + 1
        ts = e.timestamp.isoformat() if e.timestamp else None
        if ts:
            if c.first_seen is None or ts < c.first_seen:
                c.first_seen = ts
            if c.last_seen is None or ts > c.last_seen:
                c.last_seen = ts
    return sorted(groups.values(), key=lambda c: c.count, reverse=True)


def error_clusters(clusters: List[Cluster]) -> List[Cluster]:
    """Clusters whose dominant level is ERROR or CRITICAL."""
    return [c for c in clusters
            if c.to_dict()["dominant_level"] in ("ERROR", "CRITICAL")]
