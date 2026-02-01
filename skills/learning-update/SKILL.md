---
name: learning-update
version: "0.1.0"
updated: "2026-02-01"
description: Update `.claude/agent-team/learning` state from a session (writes only under learning dir).
argument-hint: "[--session <id|dir>] [--emit-adr] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:learning-update

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/learning/update_learning_state.py" $ARGUMENTS`

