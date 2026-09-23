# 🔍 LogLens

**Local-first log intelligence.** Point LogLens at any log file and it
auto-detects the format, clusters similar messages into event types, detects
anomaly spikes, and visualizes everything in an interactive dashboard — all
with **zero third-party dependencies** and everything stays on your machine.

[![tests](https://github.com/18971181532/loglens/actions/workflows/test.yml/badge.svg)](https://github.com/18971181532/loglens/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![dependencies](https://img.shields.io/badge/dependencies-zero-success)]()

---

## Why LogLens?

Logs are noisy. `user 123 logged in` and `user 456 logged in` are the *same
event* with different data, but grep and tail treat them as unrelated lines.
When a crisis hits, you need to know:

- **What are the recurring event types?** (not individual lines)
- **Which errors are happening over and over?**
- **When did traffic spike?** (anomaly detection)
- **What's the error rate over time?**

LogLens answers these by *templating* messages — replacing numbers, UUIDs,
IPs, paths, URLs, and quoted strings with placeholders — so every variant of
the same event collapses into one cluster.

## Features

- **Auto format detection** — JSON lines, syslog, nginx access, common
  `TIMESTAMP LEVEL message`, and generic fallback
- **Message templating & clustering** — UUID/IP/path/URL/number/hex/version
  normalization; groups identical event types
- **Anomaly detection** — sliding-window z-score on time-bucketed volume
- **Timeline aggregation** — minute / 5min / 15min / hour / day buckets
- **Level & source distribution** — ERROR/WARN/INFO/DEBUG breakdown
- **Top error clusters** — the recurring errors that matter
- **Interactive dashboard** — stacked-bar timeline with anomaly markers,
  level bars, cluster tables, raw log browser
- **100% local** — no network calls, no data leaves your machine
- **Zero dependencies** — pure Python stdlib

## Architecture

```
loglens/
├── parser.py     # multi-format log parsing + auto-detection
├── template.py   # message templating (UUID/IP/path/...) + clustering
├── timeline.py   # time-bucket aggregation + z-score anomaly detection
├── stats.py      # level/source/error distribution + summary
├── lens.py       # aggregate into one JSON payload
├── server.py     # http.server REST API + static dashboard
├── cli.py        # summary / clusters / errors / timeline / serve
└── web/          # vanilla-JS dashboard, hand-rolled Canvas charts
```

Data flow:

```
log file ──► parser (auto-detect) ──► template (clusters)
                  │                        │
                  └──► timeline (buckets) ─┴──► lens (JSON) ──► web UI / CLI
```

## Install

```bash
git clone https://github.com/18971181532/loglens.git
cd loglens
python -m pip install -e .
```

Requires Python 3.9+. No dependencies.

## CLI

```bash
# Overall summary
loglens summary /var/log/app.log

# Event template clusters (what kinds of things happen)
loglens clusters /var/log/app.log -n 30

# Recurring error clusters
loglens errors /var/log/app.log

# Time-bucketed timeline with anomaly markers
loglens timeline /var/log/app.log --bucket 5min

# Start the interactive dashboard
loglens serve /var/log/app.log --port 8765
```

## Web dashboard

```bash
loglens serve /var/log/app.log
```

Open <http://127.0.0.1:8765>. You get:

- **Timeline** — stacked bar chart (info/warn/error) with total-volume line
  and red anomaly-spike markers; auto-rescales on window resize
- **Levels** — level distribution bars
- **Clusters** — every event template sorted by frequency
- **Errors** — recurring error clusters with samples
- **Anomalies** — detected volume spikes with z-scores
- **Raw** — browsable parsed log entries

## REST API

| Method | Path | Description |
|---|---|---|
| GET | `/api/lens?bucket=5min` | Full analysis JSON |
| GET | `/api/raw?limit=200` | Raw parsed entries |

## How templating works

```
user 42 logged in from 192.168.1.10  →  user <NUM> logged in from <IP>
user 99 logged in from 10.0.0.5      →  user <NUM> logged in from <IP>  ✓ same cluster
```

Placeholders: `<UUID>`, `<MAC>`, `<IP>`, `<HEX>`, `<URL>`, `<EMAIL>`,
`<PATH>`, `<QSTR>`, `<VERSION>`, `<DATE>`, `<TIME>`, `<NUM>`.

## Development

```bash
python -m unittest discover -s tests -v
```

CI runs on Python 3.9–3.12.

## Roadmap

- [ ] Multi-file / directory ingestion (merge logs from many sources)
- [ ] Live tail mode (`loglens tail -f`)
- [ ] Export clusters to CSV / JSON
- [ ] Custom template rules (user-defined regex placeholders)
- [ ] Correlation: trace ID extraction and request-flow reconstruction
- [ ] Diff mode (compare two log files / time windows)

## License

MIT — see [LICENSE](LICENSE).
