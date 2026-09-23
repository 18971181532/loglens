"""Command-line interface for LogLens."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .lens import lens_from_file
from .parser import parse_file
from .template import cluster_entries
from .timeline import build_timeline, detect_anomalies
from .server import serve


def _safe_parse_file(path):
    try:
        return parse_file(path)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_summary(args) -> int:
    try:
        data = lens_from_file(args.file, bucket=args.bucket)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    s = data["summary"]
    print(f"LogLens — {args.file}")
    print(f"  lines:           {s['total_lines']}")
    print(f"  parsed:          {s['parsed_messages']}")
    print(f"  with timestamp:  {s['with_timestamp']}")
    print(f"  errors:          {s['error_count']}")
    print(f"  warnings:        {s['warning_count']}")
    print(f"  error rate:      {s['error_rate']*100:.2f}%")
    print(f"  unique events:   {s['unique_templates']}")
    print(f"  error clusters:  {s['error_clusters']}")
    if data["time_range"]["first"]:
        print(f"  range:           {data['time_range']['first']} → {data['time_range']['last']}")
    print("\nLevel distribution:")
    for lvl, n in data["levels"].items():
        print(f"  {lvl:10s} {n}")
    if data["anomalies"]:
        print(f"\n{len(data['anomalies'])} anomaly spike(s) detected:")
        for a in data["anomalies"][:5]:
            print(f"  {a['time']}  count={a['count']}  expected≈{a['expected']}  z={a['zscore']}")
    return 0


def cmd_clusters(args) -> int:
    entries = _safe_parse_file(args.file)
    clusters = cluster_entries(entries)
    print(f"{len(clusters)} unique event template(s), top {args.n}:")
    print(f"  {'count':>6}  {'level':8s}  template")
    for c in clusters[: args.n]:
        d = c.to_dict()
        tmpl = d["template"][:80]
        print(f"  {c.count:>6}  {d['dominant_level']:8s}  {tmpl}")
    return 0


def cmd_errors(args) -> int:
    try:
        data = lens_from_file(args.file, bucket=args.bucket)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errs = data["top_errors"]
    if not errs:
        print("No error entries found.")
        return 0
    print(f"{len(errs)} error cluster(s):")
    for i, c in enumerate(errs[: args.n], 1):
        print(f"\n  #{i}  count={c['count']}  level={c['dominant_level']}")
        print(f"      template: {c['template'][:120]}")
        print(f"      sample:   {c['sample'][:120]}")
    return 0


def cmd_timeline(args) -> int:
    entries = _safe_parse_file(args.file)
    tl = build_timeline(entries, bucket=args.bucket)
    anomalies = detect_anomalies(tl)
    anom_times = {a["time"] for a in anomalies}
    print(f"Timeline ({args.bucket} buckets, {len(tl)} points):")
    print(f"  {'time':20s} {'total':>6} {'err':>5} {'warn':>5}  flag")
    for b in tl:
        flag = "  <== SPIKE" if b.time in anom_times else ""
        print(f"  {b.time:20s} {b.total:>6} {b.error:>5} {b.warning:>5}{flag}")
    return 0


def cmd_serve(args) -> int:
    serve(args.file, host=args.host, port=args.port, bucket=args.bucket)
    return 0


def _add_bucket(p):
    p.add_argument("--bucket", default="5min",
                   choices=["minute", "5min", "15min", "hour", "day"],
                   help="Time bucket size (default: 5min)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="loglens",
        description="Local-first log intelligence: parse, cluster, visualize.",
    )
    p.add_argument("--version", action="version", version=f"loglens {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    q = sub.add_parser("summary", help="Overall summary")
    q.add_argument("file", help="Path to log file")
    _add_bucket(q)
    q.set_defaults(func=cmd_summary)

    q = sub.add_parser("clusters", help="List event template clusters")
    q.add_argument("file", help="Path to log file")
    q.add_argument("-n", type=int, default=20)
    q.set_defaults(func=cmd_clusters)

    q = sub.add_parser("errors", help="List error clusters")
    q.add_argument("file", help="Path to log file")
    q.add_argument("-n", type=int, default=10)
    _add_bucket(q)
    q.set_defaults(func=cmd_errors)

    q = sub.add_parser("timeline", help="Show time-bucketed timeline")
    q.add_argument("file", help="Path to log file")
    _add_bucket(q)
    q.set_defaults(func=cmd_timeline)

    q = sub.add_parser("serve", help="Start the web dashboard")
    q.add_argument("file", help="Path to log file")
    q.add_argument("--host", default="127.0.0.1")
    q.add_argument("--port", type=int, default=8765)
    _add_bucket(q)
    q.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
