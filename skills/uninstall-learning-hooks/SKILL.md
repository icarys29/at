---
name: uninstall-learning-hooks
version: "0.5.0"
updated: "2026-02-02"
description: Uninstall at-managed learning hooks from project/team/user settings.
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-learning-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/learning/uninstall_learning_hooks.py" $ARGUMENTS`
