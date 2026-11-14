---
name: mcporter
description: Reach David's MCP servers on demand through the mcporter CLI - grafana (dashboards, Prometheus, Loki, alerts, incidents), victoriametrics (metrics/MetricsQL), victorialogs (logs/LogsQL), karakeep (bookmarks) and mobbin (UI design references). Use whenever a task needs monitoring data, metrics, logs, dashboards, alerts, saved bookmarks or app-design screens.
---

# MCP servers through mcporter

These servers are not loaded as MCP tools. Call them with the `mcporter` CLI through Bash. The
config is `~/.mcporter/mcporter.json` (holds tokens: never print it).

| Server | What it has |
|---|---|
| `grafana` | Dashboards, datasources, Prometheus and Loki queries, alert rules, incidents, OnCall (80 tools) |
| `victoriametrics` | Metrics: MetricsQL queries, labels, series, alerts, rules (16 tools) |
| `victorialogs` | Logs: LogsQL queries, streams, field names and values, hits, stats (13 tools) |
| `karakeep` | David's bookmarks, lists, tags and highlights (29 tools) |
| `mobbin` | App screens, flows and UI sections for design reference (needs `mcporter auth mobbin` once, in a terminal the person runs) |

## Workflow

1. Find the tool: `mcporter list <server>` prints each tool's signature and doc comment. Pipe through
   `grep -A8 -i <word>` to narrow it; grafana's list is long.
2. Call it: `mcporter call <server>.<tool> key=value ...`, or `--args '{"key": "value"}'` for nested
   values. Add `--output json` when you will parse the result.
3. Keep queries narrow (a time range, a label filter, `limit`): metrics and log results can be large.

Examples:

```sh
mcporter call victoriametrics.query query='up{job="node"}'
mcporter call victorialogs.query query=error start=15m limit=20
mcporter call grafana.search_dashboards query=node
mcporter call karakeep.search-bookmarks query="rails hotwire"
```

A server that reports "auth required" needs the person to run `mcporter auth <server>` themselves.
