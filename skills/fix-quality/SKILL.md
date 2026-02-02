---
name: fix-quality
version: "0.4.0"
updated: "2026-02-02"
description: Rerun a single configured quality command for a session (targeted remediation helper).
argument-hint: "<command_id|path/to/quality_report.json> [<command_id>] [--session <id|dir>] [--project-dir <path>]"
allowed-tools: Read, Bash
---

# /at:fix-quality

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/rerun_quality_command.py" $ARGUMENTS`
