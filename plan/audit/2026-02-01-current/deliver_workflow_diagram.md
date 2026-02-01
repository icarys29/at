# Deliver Workflow Diagram (at) — `/at:run`

Date: 2026-02-01

This describes the *deliver* workflow and the deterministic scripts/hooks it uses, including inputs/outputs and artifact flow.

Legend:
- `(A)` agentic step (subagent via `Task`)
- `(S)` script step (`uv run ...`)
- `(H)` hook step (Claude Code hooks calling scripts)
- `SESSION_DIR` is the session root created under `workflow.sessions_dir` (default `.session/<session_id>/`)

---

## High-level flow (ASCII)

```text
User request
   |
   v
 /at:run (deliver)
   |
   +--> (S) scripts/session/create_session.py             -> SESSION_DIR/
   +--> (tool) Write                                    -> inputs/request.md
   +--> (S) scripts/context/build_context_pack.py         -> inputs/context_pack.md
   +--> (A) agents/action-planner.md                      -> planning/actions.json (+ checklists)
   +--> (S) scripts/validate/validate_actions.py          -> (exit 0/1)
   +--> (S) scripts/context/build_task_contexts.py        -> inputs/task_context/<tid>.md (+ manifest)
   +--> (S) scripts/checkpoint/create_checkpoint.py       -> checkpoints/cp-###/*
   +--> (A) agents/implementor.md / agents/tests-builder.md
   |                                                      -> implementation|testing/tasks/<tid>.yaml
   +--> (S) scripts/validate/validate_task_artifacts.py   -> quality/task_artifacts_report.{json,md}
   +--> (S) scripts/validate/plan_adherence.py            -> quality/plan_adherence_report.{json,md}
   +--> (S) scripts/validate/parallel_conformance.py      -> quality/parallel_conformance_report.{json,md}
   +--> (S) scripts/quality/run_quality_suite.py          -> quality/quality_report.{json,md} (+ logs)
   +--> (A) agents/docs-keeper.md (always-on docs)         -> updates `docs/*` + registry JSON
   +--> (S) scripts/docs/generate_registry_md.py          -> docs/DOCUMENTATION_REGISTRY.md
   +--> (S) scripts/validate/docs_gate.py                 -> documentation/docs_* (session)
   +--> (S) scripts/validate/validate_changed_files.py    -> quality/changed_files_report.{json,md}
   +--> (S) scripts/compliance/generate_compliance_report.py
   |                                                      -> compliance/* (APPROVE/REJECT)
   '--> (S) scripts/session/session_progress.py           -> status/session_progress.{json,md}

Hooks (during execution):
  (H) scripts/hooks/enforce_file_scope.py (PreToolUse Write/Edit)
  (H) scripts/hooks/validate_actions_write.py (PostToolUse Write planning/actions.json)
  (H) scripts/hooks/on_subagent_stop.py (SubagentStop; contract + artifacts)
```

---

## Key scripts (purpose + IO)

```text
(S) scripts/context/build_context_pack.py
  Purpose: bounded planning context (request + config + docs registry summary)
  Inputs : SESSION_DIR/inputs/request.md
           .claude/project.yaml (if present), CLAUDE.md (best-effort)
           docs/DOCUMENTATION_REGISTRY.json (best-effort)
  Outputs: SESSION_DIR/inputs/context_pack.md

(A) agents/action-planner.md
  Purpose: plan tasks with strict file scopes + (optional) docs selection
  Inputs : request.md + context_pack.md (includes docs registry 'when'/tags summary)
  Outputs: planning/actions.json (+ checklists)

(A) agents/docs-keeper.md
  Purpose: always-on documentation updates; maintain registry 'when' + tags
  Inputs : planning/actions.json + per-task YAML artifacts
  Outputs: repo docs under docs/* (including docs/DOCUMENTATION_REGISTRY.json)

(S) scripts/docs/generate_registry_md.py
  Purpose: generate docs/DOCUMENTATION_REGISTRY.md from docs/DOCUMENTATION_REGISTRY.json
  Inputs : docs/DOCUMENTATION_REGISTRY.json
  Outputs: docs/DOCUMENTATION_REGISTRY.md

(S) scripts/validate/docs_gate.py
  Purpose: validate docs registry + enforce MD drift check (deterministic)
  Inputs : docs/DOCUMENTATION_REGISTRY.json + docs/* files (+ config)
  Outputs: SESSION_DIR/documentation/docs_summary.{json,md}
           SESSION_DIR/documentation/docs_gate_report.{json,md}
```

