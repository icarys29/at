---
name: setup-learning-hooks
version: "0.4.0"
updated: "2026-02-02"
description: Install opt-in learning hooks (SessionStart learning snippet) into project/team/user settings.
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:setup-learning-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/learning/install_learning_hooks.py" $ARGUMENTS`
