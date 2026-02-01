# Audit — Self-Healing Reliability Improvements

Date: 2026-02-01

## Objective

Increase deliver workflow reliability and remediation efficiency by:
- making “done” evidence deterministic (verifications)
- reducing time-to-diagnosis (single gate summary artifact)

## Changes

### 1) Gate Summary Artifact (remediation efficiency)

Added a best-effort aggregator:
- Script: `scripts/validate/gates_summary.py`
- Outputs:
  - `SESSION_DIR/status/gates_summary.json`
  - `SESSION_DIR/status/gates_summary.md`

Purpose:
- Provide a single “what failed and where” overview for `remediator` and humans.
- Avoid hunting across multiple report files.

### 2) Optional strict verification requirement (reliability)

Introduced a project-config flag:
- `workflow.require_verifications_for_code_tasks: true|false`

Behavior:
- Plan-time: `scripts/validate/actions_validator.py` fails if a code task has no `acceptance_criteria[].verifications[]` anywhere (when flag enabled).
- Gate-time: `scripts/validate/plan_adherence.py` treats “no verifications” as an error (when flag enabled).

Default:
- Enabled in `templates/project.yaml` for new projects.

## Expected Impact

- Fewer false “green” runs where code changes land without runnable evidence.
- Faster self-heal loops because gates can point at failing commands (instead of ambiguous criteria).

## Remaining Gaps (not addressed here)

- `at:run` remediation loop remains orchestrator-driven (prompted), not a deterministic state machine.
- Some gates are fail-open when git is unavailable; consider `workflow.require_git=true` in strict environments.

