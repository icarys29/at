---
name: audit
version: "0.5.0"
updated: "2026-02-02"
description: Interactive audit log inspection (list/sessions/tools/timing/traces/trace-detail) for `.claude/audit_logs`.
argument-hint: "<list|sessions|tools|timing|traces|trace-detail> [--session-id <id>] [--project-dir <path>]"
allowed-tools: Bash, Read
---

# /at:audit

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit/audit_cli.py" $ARGUMENTS`

