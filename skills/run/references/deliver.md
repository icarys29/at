# Deliver workflow (at) — reference

This file is a short reference for `/at:run`. Scripts are the source of truth.

## Session artifacts (minimum)

- `session.json`
- `inputs/request.md`
- `inputs/context_pack.md`
- `planning/actions.json`
- `inputs/task_context_manifest.json`
- `inputs/task_context/<task_id>.md`
- `implementation/tasks/<task_id>.yaml`
- `testing/tasks/<task_id>.yaml`
- `checkpoints/<cp-id>/checkpoint.json`
- `quality/task_artifacts_report.{json,md}`
- `quality/plan_adherence_report.{json,md}`
- `quality/parallel_conformance_report.{json,md}`
- `quality/quality_report.{json,md}`
- `quality/changed_files_report.{json,md}`
- `docs/PROJECT_CONTEXT.md` (repo doc; always-on update via docs-keeper)
- `docs/ARCHITECTURE.md` (repo doc; always-on update via docs-keeper)
- `docs/adr/*` (repo docs; optional ADRs when a material decision occurs)
- `docs/DOCUMENTATION_REGISTRY.json` (repo doc; source of truth, includes required `when`)
- `docs/DOCUMENTATION_REGISTRY.md` (generated from JSON; kept in sync)
- `documentation/docs_summary.{json,md}`
- `documentation/docs_gate_report.{json,md}`
- `compliance/COMPLIANCE_VERIFICATION_REPORT.md`
- `compliance/compliance_report.json`
- `status/session_progress.{json,md}`
- `status/deterministic_run_report.{json,md}` (when using deterministic rerun)

## Parallel execution default

Plans must include:

- `parallel_execution.enabled=true` by default
- `parallel_execution.groups[]` covering all code tasks
- Non-overlapping `file_scope.writes[]` per code task within each group

Optional context improvements:
- `context.code_pointers[]` can embed small, grep-based code excerpts into per-task contexts.
- `context.doc_ids[]` (when using docs registry): planner selects doc ids using each doc’s `when` (and `tags[]`) so tasks embed minimal relevant documentation.
