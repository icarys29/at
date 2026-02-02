---
name: prune-audit-logs
version: "0.5.0"
updated: "2026-02-02"
description: Prune `.claude/audit_logs` (dry-run default; use --apply to delete).
argument-hint: "[--days N] [--max-total-mb N] [--apply] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:prune-audit-logs

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit/prune_audit_logs.py" $ARGUMENTS`

