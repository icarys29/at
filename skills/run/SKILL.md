---
name: run
version: "0.4.0"
updated: "2026-02-02"
description: >
  Orchestrate the at workflow kernel: `deliver|triage|review|ideate` (default: deliver).
argument-hint: "[deliver|triage|review|ideate] [--tdd] [--session <id|dir>] [--dry-run] [--from-phase <phase>|--gate <gate>] [--rollback <id|dir> [--checkpoint <cp-id>]] <request>"
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

## Procedure (workflow kernel)
0) Select workflow (default: `deliver`):
   - If the first token of `$ARGUMENTS` is one of `deliver|triage|review|ideate`, treat it as the workflow and remove it from the request text.
   - Otherwise, workflow=`deliver`.
0.1) TDD mode (optional; deliver only):
   - If workflow=`deliver` and user provided `--tdd`, set `SESSION_STRATEGY=tdd` for this session:
     - Pass `--strategy tdd` to `create_session.py` (session-scoped; does not modify repo config).
     - Ensure `action-planner` produces a tests-first plan (tests-builder tasks precede implementor tasks and implementor depends on tests).
0.25) Rollback mode (optional; any workflow):
   - If user provided `--rollback <id|dir>`, restore and stop:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/checkpoint/restore_checkpoint.py" --session "<id|dir>" [--checkpoint <cp-id>]`
     - Print the restore report path under `SESSION_DIR/checkpoints/<cp-id>/RESTORE_REPORT.md` and stop.
0.5) Deterministic rerun mode (optional; deliver sessions):
   - If workflow=`deliver` and user provided `--from-phase <phase>` or `--gate <gate>`, rerun deterministic steps and stop:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_deterministic.py" --session "<id|dir>" --from-phase "<phase>"`
       - Phases: `validate_plan|task_contexts|checkpoint|gates|progress`
     - Or: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_deterministic.py" --session "<id|dir>" --gate "<gate>"`
       - Gates: `validate_actions|build_task_contexts|checkpoint|validate_task_artifacts|plan_adherence|parallel_conformance|quality|docs_gate|changed_files|compliance|progress`
1) Create or resume a session for the chosen workflow:
   - If user provided `--session`, resume; otherwise create a new session.
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow "<deliver|triage|review|ideate>" [--strategy <default|tdd>] [--resume <id|dir>]`
   - Capture the printed `SESSION_DIR`.
   - Note: create_session.py automatically sets `AT_SESSION_DIR` and `AT_SESSION_ID` environment variables for hooks.
2) Write the request to `SESSION_DIR/inputs/request.md`.
3) Build the context pack:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_context_pack.py" --session "${SESSION_DIR}"`
4) Branch by workflow:
   - If workflow=`ideate`:
     - Task: `solution-architect` → writes `planning/ARCHITECTURE_BRIEF.{md,json}`
     - Task: `ideation` → writes `planning/IDEATION.{md,json}`
     - Stop (session-only ideation; no planning/actions.json by default).
   - If workflow=`triage`:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_triage.py" --session "${SESSION_DIR}"`
     - Task: `root-cause-analyzer` → writes `analysis/ROOT_CAUSE_ANALYSIS.{md,json}`
     - Update progress (task board + session progress) and stop.
   - If workflow=`review`:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_review.py" --session "${SESSION_DIR}"`
     - Task: `reviewer` → writes `review/REVIEW_REPORT.{md,json}`
     - Update progress (task board + session progress) and stop.
   - If workflow=`deliver` (default): continue with the full pipeline:
5) Deliver: architecture brief + user stories + plan:
   - Task: `solution-architect` → `planning/ARCHITECTURE_BRIEF.{md,json}`
   - Task: `story-writer` → `planning/USER_STORIES.{md,json}`
   - Task: `action-planner` → `planning/actions.json` (+ checklists)
     - Reminder: if `SESSION_STRATEGY=tdd`, the plan must satisfy `workflow.strategy=tdd` constraints (validated).
6) Deliver: validate plan + preflight docs requirements:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_actions.py" --session "${SESSION_DIR}"`
   - Run (optional; when configured): `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/user_stories_gate.py" --session "${SESSION_DIR}"`
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_requirements_for_plan.py" --session "${SESSION_DIR}"`
7) Deliver dry-run (optional; plan-only):
   - If user provided `--dry-run`, run and stop (no checkpoints, no repo edits, no code tasks):
     - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/generate_dry_run_report.py" --session "${SESSION_DIR}"`
8) Deliver: build contexts + checkpoint:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_task_contexts.py" --session "${SESSION_DIR}"`
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/checkpoint/create_checkpoint.py" --session "${SESSION_DIR}"`
9) Deliver: execute code tasks (parallel-safe, dependency-aware):
   - Read `SESSION_DIR/planning/actions.json` as a DAG (respect `depends_on[]`).
   - Execute `parallel_execution.groups` in `execution_order`, dispatching only tasks whose dependencies are satisfied.
   - **Before each task dispatch**: Set `AT_FILE_SCOPE_WRITES` env var to the task's `file_scope.writes[]` joined by `:` (colon-separated paths). This enables scope enforcement hooks.
   - owner `implementor` → Task `implementor` with `SESSION_DIR/inputs/task_context/<task_id>.md`
   - owner `tests-builder` → Task `tests-builder` with `SESSION_DIR/inputs/task_context/<task_id>.md`
10) Deliver: gates (binary done):
    - Task artifacts: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_task_artifacts.py" --session "${SESSION_DIR}"`
    - If plan includes `type=lsp` verifications and `.claude/project.yaml` has `lsp.enabled=true` and `lsp.mode` is `fail|warn` (not `skip`): Task `lsp-verifier` → writes `quality/lsp_verifications.{md,json}`
    - Plan adherence: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/plan_adherence.py" --session "${SESSION_DIR}"`
    - Parallel conformance: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/parallel_conformance.py" --session "${SESSION_DIR}"`
    - Quality suite: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}"`
    - E2E gate: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/e2e_gate.py" --session "${SESSION_DIR}"`
    - Docs update (always-on, agentic): Task `docs-keeper` with `SESSION_DIR/inputs/task_context/docs-keeper.md`
    - Docs gate: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/docs_gate.py" --session "${SESSION_DIR}"`
    - Changed files scope: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/validate_changed_files.py" --session "${SESSION_DIR}"`
    - Compliance report (deterministic): `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/compliance/generate_compliance_report.py" --session "${SESSION_DIR}" --rerun-supporting-checks`
    - Optional narrative: Task `compliance-checker` (should not change decision rules)
    - Summarize gates: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/validate/gates_summary.py" --session "${SESSION_DIR}"`
    - If any gate fails: prefer controlled remediation:
      - Task: `remediator` (updates `planning/actions.json`, writes `planning/REMEDIATION_PLAN.md`)
      - Re-run: validate actions → build task contexts → dispatch remediation tasks → rerun deterministic gates.
      - If remediation loops are exhausted, stop and optionally use `--rollback`.
11) Deliver: update progress + report:
    - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/task_board.py" --session "${SESSION_DIR}"`
    - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/session_progress.py" --session "${SESSION_DIR}"`
    - Print the session directory and the key artifacts to review next.

## Optional resources
- Reference: `references/deliver.md`
