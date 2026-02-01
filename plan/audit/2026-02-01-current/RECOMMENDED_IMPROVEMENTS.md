# Recommended Improvements Backlog (at)

Date: 2026-02-01

This is an actionable follow-up backlog derived from `CURRENT_PLUGIN_AUDIT_REPORT.md`.

## P0 (Immediate, high ROI)

### IMP-001 — Make scope enforcement deterministic (reduce heuristic inference)

- Target: `scripts/hooks/enforce_file_scope.py`
- Outcome: scope enforcement is reliable even when transcripts vary.
- Status: Done (commit `dbd8241`)
- Acceptance:
  - Hook uses `session_id` from hook input when present.
  - When task id cannot be resolved, the hook either:
    - denies writes outside `SESSION_DIR`, or
    - emits a prominent warning and logs the failure (no silent fail-open).

### IMP-002 — Make SubagentStop enforcement deterministic (reduce transcript inference)

- Target: `scripts/hooks/on_subagent_stop.py`
- Outcome: final reply contracts + required artifacts are always enforced for `at` subagents.
- Status: Done (commit `dbd8241`)
- Acceptance:
  - Hook resolves `SESSION_DIR` via `session_id` when possible.
  - Enforcement is scoped to known `at` agent names to avoid false positives.

### IMP-003 — Add deterministic self-audit gate for plugin integrity

- Target: new script (e.g., `scripts/maintenance/self_audit.py`) + a skill wrapper.
- Outcome: “deterministic gate” validates that the agentic workflow will behave as expected.
- Status: Done (commit `dbd8241`)
- Suggested checks:
  - `plugin.json` version matches `VERSION`
  - all `uv run` referenced scripts exist
  - agents/skills/scripts carry required version metadata (as defined)
  - schemas and validators have representative fixture coverage
  - hooks configs are valid JSON and point at existing scripts

### IMP-004 — Validate per-task artifacts before downstream gates

- Target: `/at:run` + `scripts/validate/validate_task_artifacts.py`
- Outcome: earlier, clearer failures when implementor/tests outputs are missing or malformed.
- Status: Done (commit `dbd8241`)
- Acceptance:
  - `validate_task_artifacts.py` runs after execution and before plan adherence/parallel conformance.

## P1 (Stability + UX)

### IMP-005 — Deterministic compliance report generation

- Target: new script to write `compliance/COMPLIANCE_VERIFICATION_REPORT.md` (and optionally JSON).
- Outcome: compliance decision is reproducible and testable.
- Status: Done (commit `dbd8241`)
- Acceptance:
  - Report includes `DECISION: APPROVE|REJECT` and links to the evidence artifacts.

### IMP-006 — Deterministic rerun/resume controls

- Target: `/at:run` + a small state/progress engine script.
- Outcome: users can rerun only the failing phase/gate deterministically.
- Status: Done (commit `dbd8241`)
- Acceptance:
  - `--from-phase <phase>` reruns only the requested subset.
  - Session progress reflects rerun outcomes without redoing completed phases.

### IMP-009 — Always-on docs updates + planner-actionable docs registry (`when`)

- Target: deliver gate sequence + `agents/docs-keeper.md` + `scripts/validate/docs_gate.py` + docs registry generator
- Outcome: documentation is always kept in sync with delivered work, and planners can select docs by topic/trigger.
- Status: Done (this working tree; to be committed)
- Acceptance:
  - `docs-keeper` runs during deliver and updates `docs/PROJECT_CONTEXT.md` and `docs/ARCHITECTURE.md` (and ADRs when needed).
  - `docs/DOCUMENTATION_REGISTRY.json` requires `when` for every entry (gate-enforced).
  - `docs/DOCUMENTATION_REGISTRY.md` is generated from JSON and drift is gate-enforced.
  - Context pack includes a registry summary that includes `when` (and `tags[]`) so action-planner can choose `context.doc_ids[]` without opening all docs.

## P2 (Agentic leverage, gated)

### IMP-007 — Remediation agent that produces new plan tasks (not ad-hoc edits)

- Target: new agent + deterministic validator wiring.
- Outcome: gate failures lead to controlled remediation via updated `actions.json`, rather than informal “fixes”.
- Acceptance:
  - Remediation writes a corrected `planning/actions.json` (validated by `validate_actions.py`) and produces new task contexts.

### IMP-008 — Improve task contexts without expanding context size

- Target: planning contract + context builder scripts.
- Outcome: better context relevance while preserving least-context and secrecy policies.
- Acceptance:
  - planner can specify explicit “code pointers” (paths + grep patterns) that a deterministic script embeds safely into per-task context.
