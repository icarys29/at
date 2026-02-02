---
name: docs-code-index
version: "0.4.0"
updated: "2026-02-02"
description: "Generate a session-backed code index to help docs-keeper generate/update docs from code."
argument-hint: "[--session <id|dir>] [--mode changed|full] [--project-dir <path>]"
allowed-tools: Read, Bash
---

# /at:docs-code-index

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/code_index.py" $ARGUMENTS`

