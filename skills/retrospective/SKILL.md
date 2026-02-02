---
name: retrospective
version: "0.4.0"
updated: "2026-02-02"
description: "Generate a controlled retrospective report for a session (outcome + signals + recommendations)."
argument-hint: "[--session <id|dir>] [--project-dir <path>]"
allowed-tools: Read, Bash
---

# /at:retrospective

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/retrospective.py" $ARGUMENTS`

