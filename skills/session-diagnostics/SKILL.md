---
name: session-diagnostics
version: "0.5.0"
updated: "2026-02-02"
description: Generate diagnostics report for a session with next steps.
argument-hint: "[--session <id|dir>]"
allowed-tools: Read, Glob, Bash
---

# /at:session-diagnostics

Generate a diagnostics report identifying blockers and next steps for a session.

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

### 2) Read session state

Read these files from `SESSION_DIR`:
- `session.json` — workflow, status, timestamps
- `planning/actions.json` — tasks and dependencies
- `implementation/tasks/*.yaml` — completed implementation tasks
- `testing/tasks/*.yaml` — completed test tasks
- `status/gates_summary.json` — gate results (if exists)

### 3) Analyze progress

Determine:
- Total tasks vs completed tasks
- Current phase (planning, implementation, testing, gates)
- Blocked tasks (dependencies not met)
- Failed gates

### 4) Identify blockers

Check for:
- Missing required artifacts
- Failed quality commands
- Scope violations
- Unmet dependencies

### 5) Generate next steps

Based on state:
- If in planning: "Complete planning phase"
- If tasks incomplete: "Continue with task {next_task_id}"
- If gates failing: "Fix {gate}: {specific_action}"
- If all green: "Ready for commit or /at:run review"

### 6) Output report

```
# Session Diagnostics

- session_id: `{id}`
- workflow: `{workflow}`
- status: `{status}`
- phase: `{current_phase}`

## Progress
- Tasks: {completed}/{total}
- Gates: {passed}/{total}

## Blockers
- {blocker 1}
- {blocker 2}

## Next Steps
1. {next step 1}
2. {next step 2}
```

## Output

Diagnostics to stdout. Optionally write to `SESSION_DIR/status/session_diagnostics.md`.
