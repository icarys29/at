---
name: setup-docs-keeper-hooks
version: "0.1.0"
updated: "2026-02-01"
description: Install the minimal docs-keeper hooks into project or user scope (2 hooks).
argument-hint: "[--scope project|user]"
allowed-tools: Bash, Read
---

# /at:setup-docs-keeper-hooks

Installs exactly two hooks into Claude Code settings (idempotent):

1) `SubagentStop` docs drift warning (non-blocking)
2) `PreToolUse(Bash)` pre-commit/PR gate via docs lint (blocking)

## Procedure

- Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/install_docs_keeper_hooks.py" --scope project`

