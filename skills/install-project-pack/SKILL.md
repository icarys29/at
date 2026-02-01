---
name: install-project-pack
version: "0.1.0"
updated: "2026-02-01"
description: Install a minimal project pack (enforcement runner + default enforcements) into `.claude/at/`.
argument-hint: "[--force] [--project-dir <path>] [--style none|hex --domain-path <path> --application-path <path> --adapters-path <path>] [--enforcement-mode fail|warn] [--sessions-dir <dir>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:install-project-pack

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/project_pack/install_project_pack.py" $ARGUMENTS`
