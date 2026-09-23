"""Top-level aggregation: parse → cluster → timeline → stats → one payload."""

from __future__ import annotations

from typing import List, Optional

from .parser import LogEntry, parse_file, parse_lines
from .template import cluster_entries
from .timeline import build_timeline, detect_anomalies, time_range
from .stats import level_distribution, source_distribution, top_errors, summary


def build_lens(entries: List[LogEntry], bucket: str = "5min",
               top_clusters: int = 50, top_sources: int = 20) -> dict:
    clusters = cluster_entries(entries)
    tl = build_timeline(entries, bucket)
    anomalies = detect_anomalies(tl)
    first, last = time_range(entries)
    return {
        "summary": summary(entries, clusters),
        "time_range": {"first": first, "last": last},
        "levels": level_distribution(entries),
        "sources": source_distribution(entries, top_sources),
        "clusters": [c.to_dict() for c in clusters[:top_clusters]],
        "top_errors": top_errors(entries),
        "timeline": [b.to_dict() for b in tl],
        "anomalies": anomalies,
        "bucket": bucket,
    }


def lens_from_file(path: str, bucket: str = "5min") -> dict:
    return build_lens(parse_file(path), bucket=bucket)


def lens_from_text(text: str, bucket: str = "5min") -> dict:
    return build_lens(parse_lines(text.splitlines()), bucket=bucket)
