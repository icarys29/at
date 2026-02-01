---
name: setup-learning-hooks
version: "0.1.0"
updated: "2026-02-01"
description: Install opt-in learning hooks (SessionStart learning snippet) into project or user settings.
argument-hint: "[--scope project|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:setup-learning-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/learning/install_learning_hooks.py" $ARGUMENTS`

