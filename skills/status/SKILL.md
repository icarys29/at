---
name: status
version: "0.5.0"
updated: "2026-02-02"
description: Quick status view of the current or most recent session - shows progress, gates, and next action.
argument-hint: "[--session <id|dir>]"
allowed-tools: Read, Bash
---

# /at:status

Quick status view for Agent Team (at) sessions.

## When to use
- Check progress on current work
- See what happened in the last session
- Determine next steps after resuming

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

If no session found, show:
```
No active session found.

Start a new session:
  /at:run deliver "your request"

List past sessions:
  /at:sessions
```

### 2) Read session state

Read these files:
- `session.json` - workflow, status, timestamps
- `planning/actions.json` - task list (if exists)
- `status/gates_summary.json` - gate results (if exists)
- `implementation/tasks/*.yaml` - completed tasks (if exist)
- `testing/tasks/*.yaml` - completed tests (if exist)

### 3) Generate status display

Output format:
```
Session: 20260202-143021-abc123
Workflow: deliver
Status: in_progress
Started: 2h ago

Tasks: 3/5 completed
  ✓ T1: Implement auth middleware
  ✓ T2: Add login endpoint
  ◐ T3: Write auth tests (in progress)
  ○ T4: Update documentation
  ○ T5: Add integration tests

Gates:
  ✓ Plan validation
  ✓ Quality suite (lint, test, typecheck)
  ○ Documentation (pending)
  ○ Compliance (pending)

Next: Complete task T3, then run remaining gates.

Resume: /at:run --session abc123
```

### 4) Status indicators

Use these symbols:
- `✓` - Completed/passed
- `✗` - Failed
- `◐` - In progress
- `○` - Pending
- `⊘` - Skipped

### 5) Suggest next action

Based on state:
- If tasks incomplete: "Continue with task {next_task}"
- If gates failing: "Fix {failing_gate}: {suggestion}"
- If all green: "Ready for /at:run review or commit"
- If blocked: "Blocked: {reason}. Consider /at:run --rollback"

## Output

Concise status to stdout. No session artifacts written.
