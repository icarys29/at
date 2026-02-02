---
name: uninstall-ux-nudges-hooks
version: "0.5.0"
updated: "2026-02-02"
description: Uninstall at-managed UX nudge hooks from project/team/user settings.
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-ux-nudges-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/uninstall_ux_nudges_hooks.py" $ARGUMENTS`
