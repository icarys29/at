---
name: run
version: "0.1.0"
updated: "2026-02-01"
description: >
  Orchestrate the at deliver workflow: create/resume session, plan, validate, build task contexts,
  then dispatch implementor/tests tasks (parallel-safe by default).
argument-hint: "[--session <id|dir>] [--from-phase <phase>|--gate <gate>] [--rollback <id|dir> [--checkpoint <cp-id>]] <request>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:run

## When to use
- You want the full at workflow with session artifacts and strict scope.

## When NOT to use
- You only want project bootstrap (`/at:init-project`) or checks (`/at:doctor`).

## Inputs / Outputs
- Inputs: `$ARGUMENTS`
- Outputs: a `SESSION_DIR` under `workflow.sessions_dir` with deterministic artifacts.

## Procedure (deliver MVP)
0) Rollback mode (optional):
   - If user provided `--rollback <id|dir>`, restore and stop:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/checkpoint/restore_checkpoint.py" --session "<id|dir>" [--checkpoint <cp-id>]`
     - Print the restore report path under `SESSION_DIR/checkpoints/<cp-id>/RESTORE_REPORT.md` and stop.
0.5) Deterministic rerun mode (optional):
   - If user provided `--from-phase <phase>` or `--gate <gate>`, rerun deterministic steps and stop:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_deterministic.py" --session "<id|dir>" --from-phase "<phase>"`
       - Phases: `validate_plan|task_contexts|checkpoint|gates|progress`
     - Or: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_deterministic.py" --session "<id|dir>" --gate "<gate>"`
       - Gates: `validate_actions|build_task_contexts|checkpoint|validate_task_artifacts|plan_adherence|parallel_conformance|quality|docs_gate|changed_files|compliance|progress`
1) Create or resume a session:
   - If user provided `--session`, resume; otherwise create a new session.
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow deliver [--resume <id|dir>]`
   - Capture the printed `SESSION_DIR`.
2) Write the request to `SESSION_DIR/inputs/request.md`.
3) Build the context pack:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_context_pack.py" --session "${SESSION_DIR}"`
4) Plan (agentic) using `action-planner`:
   - Task: `action-planner`
   - Inputs: `SESSION_DIR/inputs/request.md`, `SESSION_DIR/inputs/context_pack.md`
   - Output files: `SESSION_DIR/planning/actions.json` + checklists.
5) Validate the plan deterministically:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_actions.py" --session "${SESSION_DIR}"`
   - If it fails: re-run `action-planner` with the error list and require a corrected `planning/actions.json`.
5.5) Compute deterministic docs requirements for the plan (for transparency):
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_requirements_for_plan.py" --session "${SESSION_DIR}"`
   - Output: `SESSION_DIR/documentation/docs_requirements_for_plan.{json,md}`
6) Build per-task context slices:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_task_contexts.py" --session "${SESSION_DIR}"`
7) Create a rollback checkpoint (git best-effort):
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/checkpoint/create_checkpoint.py" --session "${SESSION_DIR}"`
8) Execute code tasks (parallel by default):
   - Read `SESSION_DIR/planning/actions.json`.
   - If `parallel_execution.enabled=true`, execute `parallel_execution.groups` in `execution_order`.
   - Within each group, dispatch tasks via Task tool up to `max_concurrent_agents` (from plan).
   - For each task:
     - owner `implementor` → Task `implementor` with `SESSION_DIR/inputs/task_context/<task_id>.md`
     - owner `tests-builder` → Task `tests-builder` with `SESSION_DIR/inputs/task_context/<task_id>.md`
9) Gates (binary done):
   - Task artifacts: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_task_artifacts.py" --session "${SESSION_DIR}"`
   - Plan adherence: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/plan_adherence.py" --session "${SESSION_DIR}"`
   - Parallel conformance: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/parallel_conformance.py" --session "${SESSION_DIR}"`
   - Quality suite: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}"`
   - Docs update (always-on, agentic): Task `docs-keeper` with `SESSION_DIR/inputs/task_context/docs-keeper.md`
   - Docs gate: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/docs_gate.py" --session "${SESSION_DIR}"`
   - Changed files scope: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_changed_files.py" --session "${SESSION_DIR}"`
   - Compliance report (deterministic): `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/compliance/generate_compliance_report.py" --session "${SESSION_DIR}" --rerun-supporting-checks`
   - Optional narrative: Task `compliance-checker` (should not change decision rules)
   - If any gate fails: prefer controlled remediation:
     - Task: `remediator` (updates `planning/actions.json`, writes `planning/REMEDIATION_PLAN.md`)
     - Re-run: validate actions → build task contexts → dispatch remediation tasks → rerun deterministic gates.
     - If remediation loops are exhausted, stop and optionally use `--rollback`.
10) Update progress:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/task_board.py" --session "${SESSION_DIR}"`
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/session_progress.py" --session "${SESSION_DIR}"`
11) Report:
   - Print the session directory and the key artifacts to review next.

## Optional resources
- Reference: `references/deliver.md`
