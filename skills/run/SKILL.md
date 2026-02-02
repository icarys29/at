---
name: run
version: "0.5.0"
updated: "2026-02-02"
description: >
  Orchestrate the at workflow kernel: `deliver|triage|review|ideate` (default: deliver).
argument-hint: "[deliver|triage|review|ideate] [--tdd] [--session <id|dir>] [--dry-run] [--from-phase <phase>] [--rollback <id|dir> [--checkpoint <cp-id>]] <request>"
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
   - If workflow=`deliver` and user provided `--from-phase <phase>`, rerun deterministic steps and stop:
     - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/workflow/run_deterministic.py" --session "<id|dir>" --from-phase "<phase>"`
       - Phases: `task_contexts|checkpoint|quality|progress`
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
     - Read session artifacts and build triage context inline
     - Task: `root-cause-analyzer` → writes `analysis/ROOT_CAUSE_ANALYSIS.{md,json}`
     - Update progress and stop.
   - If workflow=`review`:
     - Read session artifacts and build review context inline
     - Task: `reviewer` → writes `review/REVIEW_REPORT.{md,json}`
     - Update progress and stop.
   - If workflow=`deliver` (default): continue with the full pipeline:
5) Deliver: architecture brief + user stories + plan:
   - Task: `solution-architect` → `planning/ARCHITECTURE_BRIEF.{md,json}`
   - Task: `story-writer` → `planning/USER_STORIES.{md,json}`
   - Task: `action-planner` → `planning/actions.json` (+ checklists)
     - Reminder: if `SESSION_STRATEGY=tdd`, the plan must satisfy `workflow.strategy=tdd` constraints (validated by hook).
6) Deliver: validate plan (via hook) + build contexts:
   - Plan validation happens automatically via `validate_actions_write.py` hook when actions.json is written.
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_task_contexts.py" --session "${SESSION_DIR}"`
7) Deliver dry-run (optional; plan-only):
   - If user provided `--dry-run`, generate report inline and stop (no checkpoints, no repo edits, no code tasks):
     - Read actions.json, summarize tasks and write scopes, output dry-run report.
8) Deliver: checkpoint:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/checkpoint/create_checkpoint.py" --session "${SESSION_DIR}"`
9) Deliver: execute code tasks (parallel-safe, dependency-aware):
   - Read `SESSION_DIR/planning/actions.json` as a DAG (respect `depends_on[]`).
   - Execute `parallel_execution.groups` in `execution_order`, dispatching only tasks whose dependencies are satisfied.
   - **Before each task dispatch**: Set `AT_FILE_SCOPE_WRITES` env var to the task's `file_scope.writes[]` joined by `:` (colon-separated paths). This enables scope enforcement hooks.
   - owner `implementor` → Task `implementor` with `SESSION_DIR/inputs/task_context/<task_id>.md`
   - owner `tests-builder` → Task `tests-builder` with `SESSION_DIR/inputs/task_context/<task_id>.md`
10) Deliver: gates (binary done):
    - If plan includes `type=lsp` verifications and `.claude/project.yaml` has `lsp.enabled=true` and `lsp.mode` is `fail|warn` (not `skip`): Task `lsp-verifier` → writes `quality/lsp_verifications.{md,json}`
    - Quality suite: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/quality/run_quality_suite.py" --session "${SESSION_DIR}"`
    - Docs update (always-on, agentic): Task `docs-keeper` with `SESSION_DIR/inputs/task_context/docs-keeper.md`
    - Docs lint: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_lint.py"`
    - Read quality report and docs lint results, generate compliance decision inline (APPROVE if all pass, REJECT otherwise)
    - If any gate fails: prefer controlled remediation:
      - Task: `remediator` (updates `planning/actions.json`, writes `planning/REMEDIATION_PLAN.md`)
      - Re-run: build task contexts → dispatch remediation tasks → rerun quality suite.
      - If remediation loops are exhausted, stop and optionally use `--rollback`.
11) Deliver: update progress + report:
    - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/task_board.py" --session "${SESSION_DIR}"`
    - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/session_progress.py" --session "${SESSION_DIR}"`
    - Print the session directory and the key artifacts to review next.

## Optional resources
- Reference: `references/deliver.md`
