# P0/P1 Implementation Notes (Docs System)

Date: 2026-02-01

## P0 — Reliability

- Scope enforcement compatibility (docs-keeper)
  - `scripts/context/build_task_contexts.py` now always generates:
    - `SESSION_DIR/inputs/task_context/docs-keeper.md`
    - a `docs-keeper` entry in `SESSION_DIR/inputs/task_context_manifest.json` with `file_scope.writes: ["docs/"]`
  - `skills/run/SKILL.md` now specifies invoking `docs-keeper` with that context file.
  - `agents/docs-keeper.md` now requires reading that context before any `docs/` edits.
- Actionable lint/gate outputs
  - `scripts/docs/docs_lint.py` and `scripts/validate/docs_gate.py` now include samples for orphan docs + broken links in both JSON and MD outputs.

## P1 — Trust and usability

- Deterministic keyword matching (reduced false positives)
  - `scripts/docs/coverage_rules.py` now uses token/phrase matching with word-boundary semantics (no substring surprises like `auth` in `author`).
- Planner transparency aligned with enforcement
  - `scripts/docs/docs_requirements_for_plan.py` now passes per-task keyword text (summary/description/acceptance criteria) and reports `matched_keywords`.
  - `scripts/validate/actions_validator.py` now includes a short “why” excerpt (triggered rule ids + matched keywords/paths sample) when rejecting missing required docs.
- Deterministic doc ID allocator
  - `scripts/docs/allocate_doc_id.py` allocates the next numeric id for a doc type based on registry prefix + managed dir scan.

