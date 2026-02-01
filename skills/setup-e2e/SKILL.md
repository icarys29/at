---
name: setup-e2e
version: "0.1.0"
updated: "2026-02-01"
description: Setup guided E2E scaffolding (README + env example + config) without touching secrets.
argument-hint: "[--force] [--project-dir <path>]"
allowed-tools: Read, Write, Bash
---

# /at:setup-e2e

Installs:
- `e2e/README.md`
- `e2e/.env.example`
- `.claude/at/e2e.json`
- Ensures `.gitignore` contains `e2e/.env`

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/e2e/setup_e2e.py" $ARGUMENTS`

