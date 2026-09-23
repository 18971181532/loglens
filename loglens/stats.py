"""Aggregate statistics: level distribution, sources, top errors."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from .parser import LogEntry
from .template import Cluster, cluster_entries, error_clusters


def level_distribution(entries: List[LogEntry]) -> Dict[str, int]:
    c = Counter(e.level for e in entries if e.message.strip())
    return dict(c.most_common())


def source_distribution(entries: List[LogEntry], top_n: int = 20) -> List[dict]:
    c = Counter(e.source for e in entries if e.source and e.message.strip())
    return [{"source": s, "count": n} for s, n in c.most_common(top_n)]


def top_errors(entries: List[LogEntry], n: int = 10) -> List[dict]:
    clusters = error_clusters(cluster_entries(entries))
    return [c.to_dict() for c in clusters[:n]]


def summary(entries: List[LogEntry], clusters: List[Cluster]) -> dict:
    levels = level_distribution(entries)
    total = sum(levels.values())
    errors = levels.get("ERROR", 0) + levels.get("CRITICAL", 0)
    warnings = levels.get("WARNING", 0)
    timed = sum(1 for e in entries if e.timestamp)
    return {
        "total_lines": len(entries),
        "parsed_messages": total,
        "with_timestamp": timed,
        "error_count": errors,
        "warning_count": warnings,
        "unique_templates": len(clusters),
        "error_clusters": len(error_clusters(clusters)),
        "error_rate": round(errors / total, 4) if total else 0,
    }
