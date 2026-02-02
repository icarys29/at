---
name: telemetry-session-kpis
version: "0.5.0"
updated: "2026-02-02"
description: Generate per-session KPIs under the session directory.
argument-hint: "[--session <id|dir>] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:telemetry-session-kpis

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry/build_session_kpis.py" $ARGUMENTS`

