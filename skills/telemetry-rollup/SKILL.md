---
name: telemetry-rollup
version: "0.5.0"
updated: "2026-02-02"
description: Roll up session KPIs across sessions dir into telemetry_rollup.{json,md}.
argument-hint: "[--limit N] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:telemetry-rollup

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry/rollup_kpis.py" $ARGUMENTS`

