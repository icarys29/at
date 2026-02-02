---
name: continuous-learning
version: "0.5.0"
updated: "2026-02-02"
description: "Extract reusable patterns from a session and optionally persist to learning state."
argument-hint: "[--session <id|dir>] [--apply]"
allowed-tools: Read, Write, Glob, Bash
---

# /at:continuous-learning

Extract reusable patterns and learnings from a completed session.

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

### 2) Read session artifacts

Read these files from `SESSION_DIR`:
- `retrospective/RETROSPECTIVE.json` — if exists
- `status/session_audit.json` — if exists
- `compliance/compliance_report.json` — compliance decision
- `quality/quality_report.json` — quality results

### 3) Extract learnings

Identify:
- Successful patterns (what worked well)
- Failure patterns (what caused issues)
- Recommendations from retrospective/audit

### 4) Generate learning entry

```json
{
  "version": 1,
  "generated_at": "{timestamp}",
  "session_id": "{id}",
  "outcome": {
    "compliance_decision": "{APPROVE|REJECT}",
    "gates_ok": true|false,
    "quality_ok": true|false
  },
  "patterns": [
    {"type": "success|failure", "description": "..."}
  ],
  "recommendations": [
    "recommendation 1",
    "recommendation 2"
  ]
}
```

### 5) Preview or apply

If `--apply` not provided:
- Show preview only
- Print: "To persist: /at:continuous-learning --session {id} --apply"

If `--apply` provided:
- Write to `.claude/learning/learnings/{session_id}.json`
- Update `.claude/learning/LEARNINGS.md` rollup

### 6) Output

```
# Continuous Learning

- session_id: `{id}`
- outcome: `{decision}`
- apply: `{true|false}`

## Learnings
- {learning 1}
- {learning 2}

## Recommendations
- {recommendation 1}
```

## Output

Learning preview to stdout. If `--apply`, persists to `.claude/learning/`.
