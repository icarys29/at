---
name: god-class-audit
version: "0.4.0"
updated: "2026-02-02"
description: "Scan for oversized Python classes (SRP heuristic) and emit a report (JSON+MD). Exits non-zero on findings."
argument-hint: "[--session <id|dir>] [--max-methods N] [--max-lines N] [--project-dir <path>]"
allowed-tools: Read, Bash
---

# /at:god-class-audit

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/enforcement/god_class_audit.py" $ARGUMENTS`

