---
name: retrospective
version: "0.5.0"
updated: "2026-02-02"
description: "Generate a retrospective report for a session (outcome + signals + recommendations)."
argument-hint: "[--session <id|dir>]"
allowed-tools: Read, Glob, Bash
---

# /at:retrospective

Generate a retrospective report summarizing session outcome and lessons learned.

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

### 2) Read session artifacts

Read these files from `SESSION_DIR`:
- `inputs/request.md` — original request
- `status/gates_summary.json` — gate results
- `quality/quality_report.json` — quality results
- `compliance/compliance_report.json` — compliance decision
- `documentation/docs_gate_report.json` — docs gate

### 3) Analyze outcome

Determine:
- `gates_ok`: all gates passed?
- `quality_ok`: all quality commands passed?
- `docs_ok`: docs gate passed?
- `compliance_decision`: APPROVE or REJECT

Identify signals:
- `failing_gates`: list of failed gate IDs
- `missing_gates`: list of missing gate artifacts
- `quality_failed_command_ids`: list of failed quality commands

### 4) Generate recommendations

Based on signals:
- If missing gates: "Generate missing gate artifacts"
- If docs_gate failed: "Run /at:docs sync"
- If quality_suite failed: "Use /at:resolve-failed-quality"
- If plan_adherence failed: "Ensure tasks have explicit verifications"
- If compliance rejected: "Address failing/missing gates first"

### 5) Output report

```
# Retrospective

- session_id: `{id}`
- compliance_decision: `{decision}`

## Outcome
- gates_ok: `{value}`
- quality_ok: `{value}`
- docs_ok: `{value}`
- compliance_ok: `{value}`

## Signals
- failing_gates: {list}
- missing_gates: {list}
- quality_failed: {list}

## Recommendations
- {recommendation 1}
- {recommendation 2}
```

## Output

Report to stdout. Optionally write to `SESSION_DIR/retrospective/RETROSPECTIVE.md`.
