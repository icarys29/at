---
name: self-audit
version: "0.4.0"
updated: "2026-02-02"
description: Run deterministic integrity checks for the at plugin (script refs, version metadata, contract parity, fixtures).
argument-hint: "[--out-dir <dir>] [--strict]"
allowed-tools: Read, Bash
---

# /at:self-audit

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/maintenance/self_audit.py" $ARGUMENTS`

