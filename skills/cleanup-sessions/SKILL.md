---
name: cleanup-sessions
version: "0.5.0"
updated: "2026-02-02"
description: Prune old sessions under workflow.sessions_dir (dry-run default; use --apply to delete).
argument-hint: "[--keep N] [--days N] [--apply] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:cleanup-sessions

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/maintenance/cleanup_sessions.py" $ARGUMENTS`

