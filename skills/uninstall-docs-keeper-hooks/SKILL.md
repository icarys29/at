---
name: uninstall-docs-keeper-hooks
version: "0.5.0"
updated: "2026-02-02"
description: Uninstall docs-keeper hooks from project/team/user settings (best-effort).
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-docs-keeper-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/uninstall_docs_keeper_hooks.py" $ARGUMENTS`

