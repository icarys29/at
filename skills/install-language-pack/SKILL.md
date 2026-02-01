---
name: install-language-pack
version: "0.1.0"
updated: "2026-02-01"
description: Install a language pack into `.claude/` (rules + structured metadata) for predictable planning and enforcement.
argument-hint: "--lang <python|go|typescript|rust> [--force] [--project-dir <path>]"
allowed-tools: Read, Write, Bash
---

# /at:install-language-pack

Installs:
- `.claude/rules/at/lang/<lang>.md`
- `.claude/at/languages/<lang>.json`

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/languages/install_language_pack.py" $ARGUMENTS`

