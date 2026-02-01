---
name: run
description: >
  Orchestrate the at deliver workflow: create/resume session, plan, validate, build task contexts,
  then dispatch implementor/tests tasks (parallel-safe by default).
argument-hint: "[--session <id|dir>] [--rollback <id|dir> [--checkpoint <cp-id>]] <request>"
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
   - Plan adherence: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/plan_adherence.py" --session "${SESSION_DIR}"`
   - Parallel conformance: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/parallel_conformance.py" --session "${SESSION_DIR}"`
   - Quality suite: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}"`
   - Docs gate: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/docs_gate.py" --session "${SESSION_DIR}"`
   - Compliance report (agent): Task `compliance-checker` (writes `compliance/COMPLIANCE_VERIFICATION_REPORT.md`)
   - If any gate fails: stop and report remediation steps (optionally use `--rollback`).
10) Update progress:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/session_progress.py" --session "${SESSION_DIR}"`
11) Report:
   - Print the session directory and the key artifacts to review next.

## Optional resources
- Reference: `references/deliver.md`
