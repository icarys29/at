# P1 — Kernel (deliver workflow MVP)

## Outcome

Deliver the minimal end-to-end kernel:
- session creation/resume
- plan creation (agentic) + deterministic validation
- context pack + per-task context slices
- scoped execution via core subagents
- core hooks that enforce scope + artifact contracts

This phase should enable a “plan → implement/tests” loop with deterministic artifacts, even before full gates exist.

## References (read first; keep context lean)

- Template: `references/skills-template.md`
- Template: `references/agents-template.md`
- Claude Code: `references/claude-code/skills.md`
- Claude Code: `references/claude-code/subagents.md`
- Claude Code hooks: `references/claude-code/hooks-guidelines.md`

## Scope (include)

### Skills (minimal set)

- `/at:run` (deliver only for MVP; triage/review/ideate can be stubbed)
- `/at:init-project`
- `/at:doctor`
- `/at:sessions`
- `/at:session-progress`

### Agents (minimal set)

- `action-planner`
- `implementor`
- `tests-builder`

### Deterministic scripts (MVP set)

- Sessions:
  - `scripts/session/create_session.py`
  - `scripts/session/list_sessions.py`
  - `scripts/session/session_progress.py`
- Planning validation:
  - `scripts/validate/validate_actions.py`
- Context:
  - `scripts/context/build_context_pack.py`
  - `scripts/context/build_task_contexts.py`
- Hooks:
  - `scripts/hooks/enforce_file_scope.py`
  - `scripts/hooks/on_subagent_stop.py`
  - `scripts/hooks/validate_actions_write.py` (optional but recommended)

## Default Parallelization (must be implemented here)

Planning default:
- `action-planner` always emits `parallel_execution.enabled=true` unless user requests sequential execution.
- Planner must provide non-overlapping `file_scope.writes[]` per task when parallel is enabled.

Execution default:
- `/at:run` respects `parallel_execution.groups` and executes groups with `max_concurrent_agents`.

## Work Items (structured; many can run in parallel)

### P1-01 Implement session machinery

Deliverables:
- scripts under `scripts/session/`
- session dir layout + `session.json` contract

Acceptance:
- Can create a new session and resume an existing one deterministically.
- `session_progress` produces both JSON + Markdown.

### P1-02 Implement planning contract enforcement

Deliverables:
- `schemas/actions.schema.json` finalized (if not already)
- `scripts/validate/validate_actions.py` validating:
  - schema adherence
  - `parallel_execution` invariants (writes required + no overlap within group)

Acceptance:
- Invalid `actions.json` fails fast with actionable errors.

### P1-03 Build context pack + task contexts

Deliverables:
- `inputs/context_pack.md`
- `inputs/task_context/<task_id>.md` + `inputs/task_context_manifest.json`

Acceptance:
- Task contexts include: task spec, project config, minimal docs referenced by `context.doc_ids`.
- Enforce doc path safety and `policies.forbid_secrets_globs`.

### P1-04 Core agents + artifact contracts

Deliverables:
- `agents/action-planner.md` writes planning artifacts only.
- `agents/implementor.md` and `agents/tests-builder.md`:
  - require reading task context
  - write per-task YAML artifacts under `implementation/tasks/` and `testing/tasks/`

Acceptance:
- Per-task artifacts are small, consistent, and machine-checkable.
- Agents follow `references/agents-template.md` (frontmatter minimal; SRP; clear inputs/outputs; ≤ 500 lines).

### P1-05 Core hooks (component-based)

Deliverables:
- `hooks/hooks.json` enabling:
  - `PreToolUse` scope enforcement for `Write/Edit` (subagents)
  - `SubagentStop` artifact contract validation + circuit breaker
  - (optional) `PostToolUse` validation on `planning/actions.json` write

Acceptance:
- Out-of-scope writes are blocked at tool time.
- Missing artifacts cause a remediation loop without infinite recursion.
- Hook configs follow `references/claude-code/hooks-guidelines.md` (correct scopes, safe blocking behavior, loop guard).

### P1-06 `/at:run` deliver MVP

Deliverables:
- `skills/run/SKILL.md` orchestrator (kept short; ≤ 500 lines; long material goes to `skills/run/references/`)
- `skills/run/references/deliver.md` workflow reference (kept short; scripts are the truth)

Acceptance:
- `deliver` can: create session → plan → validate plan → build task contexts → dispatch implementor/tests tasks.
- Produces stable artifacts under session dir.
- Skills follow `references/skills-template.md` (frontmatter minimal; optional resources are explicit; keep deep detail in `references/`).

## Exit Criteria

- A deliver session is possible end-to-end with deterministic artifacts and strict write scope.
- Parallel execution is enabled by default and safe via explicit `file_scope.writes[]`.
