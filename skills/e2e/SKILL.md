---
name: e2e
version: "0.5.0"
updated: "2026-02-02"
description: Run E2E tests only (outside deliver workflow).
argument-hint: "[--session <id|dir>] [--profile <local|ci>]"
allowed-tools: Read, Bash
---

# /at:e2e

Run E2E tests only, without the full deliver workflow.

## Procedure

### 1) Resolve or create session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow deliver [--resume "${SESSION_ARG}"])
```

### 2) Run E2E via quality suite

Use the quality suite with E2E profile:
```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" \
  --session "${SESSION_DIR}" \
  --only e2e \
  --e2e-profile "${PROFILE:-local}"
```

### 3) Read results

Read `SESSION_DIR/quality/quality_report.json` for E2E results.

### 4) Output report

```
# E2E Test Results

- session_id: `{id}`
- profile: `{profile}`
- status: `{passed|failed}`

## Results
- command: `{e2e_command}`
- exit_code: `{code}`
- duration: `{seconds}s`

## Output
{test output summary}

## Next Steps
{if failed: "Review test output and fix failures"}
{if passed: "E2E tests pass. Ready for /at:run review or commit."}
```

## Output

E2E results to stdout. Updates session quality report.
