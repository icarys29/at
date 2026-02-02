---
name: session-auditor
version: "0.5.0"
updated: "2026-02-02"
description: Audit a session and generate scorecard with recommendations.
argument-hint: "[--session <id|dir>]"
allowed-tools: Read, Glob, Bash
---

# /at:session-auditor

Audit a workflow session to evaluate quality and generate improvement recommendations.

## Procedure

### 1) Resolve session
```bash
SESSION_DIR=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --resume "${SESSION_ARG:-}")
```

### 2) Read session artifacts

Read these files from `SESSION_DIR`:
- `session.json` — workflow, status
- `status/gates_summary.json` — gate results
- `quality/quality_report.json` — quality command results
- `quality/plan_adherence_report.json` — plan adherence
- `quality/parallel_conformance_report.json` — parallel conformance
- `documentation/docs_gate_report.json` — docs gate
- `compliance/compliance_report.json` — compliance decision

### 3) Generate scorecard

Score each dimension (0-100):
- **Gates health**: passed / (passed + failed + 0.5*missing)
- **Quality suite**: 100 - (failed_commands / total) * 100
- **Plan adherence**: 100 if ok=true, 0 if ok=false
- **Docs gate**: 100 if ok=true, 0 if ok=false
- **Compliance**: 100 if ok=true, 0 if ok=false
- **Evidence completeness**: 100 - (missing_artifacts * 15)

Calculate weighted overall score.

### 4) Generate recommendations

Based on failures:
- If gates failing: "Fix {gate}: {suggestion}"
- If quality failing: "Use /at:resolve-failed-quality {command_id}"
- If docs failing: "Run /at:docs sync"
- If missing artifacts: "Rerun deterministic gates"

### 5) Output report

```
# Session Audit

- session_id: `{id}`
- overall_score: `{score}` ({status})

## Scorecard
- gates: `{score}` — {details}
- quality: `{score}` — {details}
- compliance: `{score}` — {details}
...

## Recommendations
- {recommendation 1}
- {recommendation 2}
```

## Output

Audit report to stdout. Optionally write to `SESSION_DIR/status/session_audit.md`.
