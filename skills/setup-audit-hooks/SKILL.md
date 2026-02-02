---
name: setup-audit-hooks
version: "0.4.0"
updated: "2026-02-02"
description: Install opt-in audit hooks (tool/session/subagent lifecycle JSONL) into project/team/user settings.
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:setup-audit-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit/install_audit_hooks.py" $ARGUMENTS`
