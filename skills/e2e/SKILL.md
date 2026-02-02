---
name: e2e
version: "0.4.0"
updated: "2026-02-02"
description: Run configured E2E tests only (outside deliver), using `.claude/at/e2e.json` profiles and local env file loading.
argument-hint: "[--session <id|dir>] [--profile <local|ci|...>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

# /at:e2e

Runs E2E only (no planning/implementation), writing evidence under a session directory.

## Procedure
1) Create or resume a session:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow deliver [--session <id|dir>]`
   - Capture the printed `SESSION_DIR`.
2) Run E2E command only:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}" --only e2e --e2e-profile <profile>`
3) Enforce E2E policy:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/e2e_gate.py" --session "${SESSION_DIR}"`
4) Summarize gates:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/gates_summary.py" --session "${SESSION_DIR}"`

