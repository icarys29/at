---
name: session-auditor
version: "0.4.0"
updated: "2026-02-02"
description: Deterministic session audit scorecard + actionable recommendations (artifact-first, low-sensitivity by default).
argument-hint: "[--session <id|dir>] [--project-dir <path>] [--format full|summary|json] [--no-compare] [--compare-with <id|dir>]"
allowed-tools: Bash, Read
---

# /at:session-auditor

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/session_auditor.py" $ARGUMENTS`
