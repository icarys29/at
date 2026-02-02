---
name: upgrade-project
version: "0.5.0"
updated: "2026-02-02"
description: Upgrade the repo overlay to the latest templates (dry-run default; use --apply to write).
argument-hint: "[--apply] [--rollback <backup_dir>] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:upgrade-project

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade/upgrade_project.py" $ARGUMENTS`
