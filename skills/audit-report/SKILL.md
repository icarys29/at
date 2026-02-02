---
name: audit-report
version: "0.5.0"
updated: "2026-02-02"
description: Generate an audit report from `.claude/audit_logs` into `.claude/audit_reports/`.
argument-hint: "[--out <dir>] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:audit-report

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit/analyze_audit_logs.py" $ARGUMENTS`

