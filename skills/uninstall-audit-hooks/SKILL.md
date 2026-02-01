---
name: uninstall-audit-hooks
version: "0.1.0"
updated: "2026-02-01"
description: Uninstall at-managed audit hooks from project or user settings.
argument-hint: "[--scope project|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-audit-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit/uninstall_audit_hooks.py" $ARGUMENTS`

