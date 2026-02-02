---
name: verify
version: "0.5.0"
updated: "2026-02-02"
description: Run CI-friendly verification (quality suite + docs lint).
argument-hint: "[--session <id|dir>]"
allowed-tools: Read, Bash
---

# /at:verify

Run comprehensive verification checks suitable for CI or pre-commit.

## Procedure

### 1) Resolve or create session

If `--session` provided:
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG}")
```

Otherwise create a temporary verification session:
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow deliver)
```

### 2) Run quality suite
```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}"
```

### 3) Run docs lint
```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_lint.py"
```

### 4) Aggregate results

Read:
- `SESSION_DIR/quality/quality_report.json`
- Docs lint output

### 5) Output report

```
# Verification Report

- session_id: `{id}`
- status: `{PASS|FAIL}`

## Quality Suite
- format: `{passed|failed}`
- lint: `{passed|failed}`
- typecheck: `{passed|failed}`
- test: `{passed|failed}`

## Docs Lint
- status: `{passed|failed}`
- issues: `{count}`

## Overall
- Status: `{PASS|FAIL}`
```

### 6) Exit code

- Exit 0 if all checks pass
- Exit 1 if any check fails

## Output

Verification report to stdout. Exit non-zero on failure.
