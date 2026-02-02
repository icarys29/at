---
name: setup-ux-nudges-hooks
version: "0.4.0"
updated: "2026-02-02"
description: "Install optional UX nudge hooks (debug detection + compaction suggestion) into project/team/user settings."
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:setup-ux-nudges-hooks

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/install_ux_nudges_hooks.py" $ARGUMENTS`
