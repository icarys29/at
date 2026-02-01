# Deliver Workflow (at) — ASCII Diagram

Date: 2026-02-01

```text
User Request
  |
  v
scripts/session/create_session.py
  - in:  workflow (deliver), optional --resume
  - out: SESSION_DIR/session.json (+ inputs/request.md)
  |
  v
scripts/context/build_context_pack.py
  - in:  repo state + docs registry summary
  - out: SESSION_DIR/inputs/context_pack.md
  |
  v
Task: action-planner (agentic)
  - in:  SESSION_DIR/inputs/{request.md,context_pack.md}
  - out: SESSION_DIR/planning/actions.json
        SESSION_DIR/planning/{REQUIREMENT_TRACEABILITY_MATRIX.md,VERIFICATION_CHECKLIST.md}
  |
  v
scripts/validate/validate_actions.py  (deterministic gate)
  - validates: schema + parallel safety + file_scope + required doc_ids (when enabled)
  |
  v
scripts/docs/docs_requirements_for_plan.py  (deterministic transparency)
  - in:  planning/actions.json + docs/DOCUMENTATION_REGISTRY.json coverage_rules[]
  - out: SESSION_DIR/documentation/docs_requirements_for_plan.{json,md}
  |
  v
scripts/context/build_task_contexts.py
  - in:  planning/actions.json + docs registry docs[] (doc_ids->paths)
  - out: SESSION_DIR/inputs/task_context/<task_id>.md (per code task)
         SESSION_DIR/inputs/task_context/docs-keeper.md (always)
         SESSION_DIR/inputs/task_context_manifest.json (for scope enforcement)
  |
  v
scripts/checkpoint/create_checkpoint.py
  - out: SESSION_DIR/checkpoints/<cp-id>/... (best-effort rollback)
  |
  v
Task groups (agentic, parallel-safe):
  - Task: implementor    -> writes repo code within file_scope.writes + SESSION_DIR/implementation/tasks/<task>.yaml
  - Task: tests-builder  -> writes tests within file_scope.writes + SESSION_DIR/testing/tasks/<task>.yaml
  |
  v
Deterministic gates:
  - scripts/validate/validate_task_artifacts.py
  - scripts/validate/plan_adherence.py
  - scripts/validate/parallel_conformance.py
  - scripts/quality/run_quality_suite.py
  |
  v
Task: docs-keeper (agentic, always-on)
  - MUST read: SESSION_DIR/inputs/task_context/docs-keeper.md (scope contract)
  - in:  SESSION_DIR/planning/actions.json + SESSION_DIR/{implementation,testing}/tasks/*.yaml
         docs/DOCUMENTATION_REGISTRY.json + docs/_templates/*.tpl
  - out: repo updates under docs/*
         docs/DOCUMENTATION_REGISTRY.json (source of truth)
         docs/DOCUMENTATION_REGISTRY.md (generated from JSON)
         SESSION_DIR/documentation/{docs_plan.json,docs_lint_report.json,...} (evidence)
  |
  v
scripts/validate/docs_gate.py  (deterministic gate)
  - out: SESSION_DIR/documentation/docs_gate_report.{json,md}
  |
  v
scripts/validate/validate_changed_files.py + scripts/compliance/generate_compliance_report.py
  |
  v
scripts/session/session_progress.py
  - out: SESSION_DIR/status/session_progress.json (+ summary)
```

## Hooks in play (what triggers, what it does)

```text
PreToolUse (Write/Edit) -> scripts/hooks/enforce_file_scope.py
  - purpose: blocks repo edits outside the active task’s file_scope.writes[]
  - inputs: hook payload + SESSION_DIR/inputs/task_context_manifest.json
  - key requirement: subagent must read SESSION_DIR/inputs/task_context/<task_id>.md

SubagentStop -> scripts/hooks/docs_post_task_drift.py (non-blocking)
  - purpose: warns if code changed but docs/registry not touched (drift risk)

PreToolUse (Bash) -> scripts/hooks/docs_pre_commit_gate.py (blocking)
  - purpose: on likely git commit/push/PR commands, run docs lint and block if failing
  - remediation: run docs sync (docs-keeper) then retry
```

