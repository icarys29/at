---
name: fix-quality
version: "0.5.0"
updated: "2026-02-02"
description: Rerun a single quality command for targeted remediation.
argument-hint: "<command_id> [--session <id|dir>]"
allowed-tools: Read, Bash
---

# /at:fix-quality

Rerun a single quality command for targeted remediation without running the full suite.

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

### 2) Read quality report

Read `SESSION_DIR/quality/quality_report.json` to find the command configuration.

### 3) Identify command

If `command_id` provided, use it.
Otherwise, pick the first failing command from the report.

### 4) Rerun command

Use the quality suite with `--only` filter:
```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" \
  --session "${SESSION_DIR}" \
  --only "<command_id>"
```

### 5) Report result

```
# Fix Quality

- command_id: `{id}`
- status: `{passed|failed}`
- exit_code: `{code}`

## Output
{command output}

## Next Steps
{if failed: suggestions for fixing}
{if passed: "Command now passes. Run /at:verify for full check."}
```

## Output

Command result to stdout. Updates `SESSION_DIR/quality/quality_report.json`.
