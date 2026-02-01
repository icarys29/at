---
name: verify
version: "0.1.0"
updated: "2026-02-01"
description: Run a CI-friendly verify (quality suite + docs lint) and emit one report.
argument-hint: "[--session <id|dir>] [--project-dir <path>] [--e2e-profile <name>]"
allowed-tools: Read, Bash
---

# /at:verify

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/verify.py" $ARGUMENTS`

