# Current Plugin Audit Report (at)

- Date: 2026-02-01
- Scope: this repo working tree at `plugin.json` version `0.1.0` (git `f6351fe6afa6`)
- Comparison baseline: prior `at` plugin snapshot v`0.7.42` (see `plan/audit/previous_plugin_*`)

## Executive Summary

The rebuild is materially aligned with the stated ambitions in `CLAUDE.md`: a session-backed, contract-driven workflow kernel where scripts provide deterministic artifacts/gates and subagents do the semantic work (plan + code + tests + docs). Compared to the previous plugin snapshot, the current implementation is smaller (agents/skills/scripts), Python-only (no JS hooks), and it ships the core guardrails (sessions, scope enforcement, checkpoints, plan validation, and gate reports).

The main risk is **not “too many scripts”** so much as **where determinism is currently anchored**:
- Several *enforcement-critical* hooks still infer session/task context via transcript parsing and fail open when inference fails.
- Some “contracts” are defined in multiple places (JSON Schemas vs bespoke validators), which can reintroduce drift—the largest reliability killer called out in the previous audit.

If you want scripts to function primarily as **deterministic gates** (your stated goal), the key improvement is to (1) make enforcement hooks more reliable and less heuristic, and (2) tighten the contract single-source-of-truth story so agents can be flexible without breaking determinism.

## Snapshot (Current vs Previous)

### Size / Surface Area (inventory-based)

See `plan/audit/2026-02-01-current/compare_previous_plugin.md` and `plan/audit/2026-02-01-current/current_inventory.json`.

- Previous plugin snapshot (v0.7.42): 20 agents, 32 skills, 96 Python files, 7 JS files
- Current working tree (v0.1.0): 6 agents, 20 skills, 55 Python scripts, 0 JS files

### Progress vs requirements artifacts

From `plan/requirements/*`:
- User stories: 12 Done, 9 In progress, 2 Not started (counted from `Status:` fields)
- Capabilities: 73 Done, 13 Todo (counted from `[x]` markers)

## Ambitions & Goals Alignment

This section maps `CLAUDE.md` “non‑negotiables” and the phased plan to what’s implemented.

### Strong alignment (implemented as designed)

- Sessions are first-class: `scripts/session/create_session.py` creates deterministic `SESSION_DIR` layout + `session.json`.
- Planning is agentic but contract-validated: `agents/action-planner.md` + `scripts/validate/validate_actions.py` (+ `scripts/hooks/validate_actions_write.py`).
- Least-context execution: `scripts/context/build_context_pack.py` + `scripts/context/build_task_contexts.py` produce bounded, per-task contexts.
- Scope enforcement exists at tool-time: `scripts/hooks/enforce_file_scope.py` with `hooks/hooks.json` (`PreToolUse`).
- Binary gates exist and emit evidence: `scripts/validate/plan_adherence.py`, `scripts/validate/parallel_conformance.py`, `scripts/quality/run_quality_suite.py`, `scripts/validate/docs_gate.py`.
- Rollback safety exists: `scripts/checkpoint/create_checkpoint.py` + `scripts/checkpoint/restore_checkpoint.py`, surfaced by `/at:run --rollback`.
- Optional P3 subsystems are clearly opt-in: audit hooks, learning hooks, telemetry rollups.

### Partial / at-risk alignment

- “One contract → one schema → one validator”: JSON Schemas exist (`schemas/*.json`), but enforcement relies primarily on bespoke validators in `scripts/validate/*`. This is workable, but raises drift risk.
- “Hooks enforce invariants”: hooks exist, but enforcement reliability is impacted by heuristic transcript parsing (details in Findings).
- “Workflow is repeatable and resumable”: `scripts/session/session_progress.py` summarizes state, but `/at:run` does not yet provide deterministic `--from-phase` reruns/resume controls (still listed as “Not started” in user stories).

## Scripts vs Agentic Capabilities (Current Split)

Current division is broadly healthy:

### What scripts do (deterministic)

- **Scaffolding**: create sessions, build context packs/slices, create checkpoints.
- **Validation / gates**: validate plan schema/invariants, plan adherence, parallel conformance, docs gate, quality suite.
- **Enforcement (hooks)**: enforce write scopes, enforce plan validity at write-time, block secrets/destructive commands (policy hooks), audit logging.
- **Utilities**: doctor, sessions listing, cleanup, telemetry, learning state update.

### What agents do (semantic/heuristic)

- **Planning**: interpret request → tasks, file scopes, acceptance criteria.
- **Implementation & tests**: write code; run project-specific verifications.
- **Docs**: decide what to update; script verifies registry invariants.
- **Compliance reporting**: currently an agent, but its decision rules are almost fully deterministic.

### Is this “too script-heavy”?

Given the plugin’s stated goal (high reliability, deterministic artifacts, strict scope, reproducible gates), the current bias toward scripts for scaffolding + validation is appropriate.

The more relevant question is: **Are scripts doing any “semantic deciding” that should belong to agents?**
- Today, most scripts decide *how to enforce/check* rather than *what to change*, which is correct.
- The places to guard against are: context selection heuristics (keep deterministic), docs heuristics (keep in agent), remediation (should be agentic, gated).

## Findings (Audit Issues + Recommendations)

Severity levels: Critical / High / Medium / Low.

## Previous Plugin Audit (2026-01-25) — Status Check

This is a point-in-time comparison against `plan/audit/upstream/PLUGIN_AUDIT_2026-01-25.md` (old plugin v0.7.2) to show what the rebuild already addressed vs what remains.

### Addressed (in current repo)

- Docs registry coupling: template defaults `docs.require_registry=false` and gates are onboarding-friendly (`scripts/validate/docs_gate.py`).
- Rollback mechanism: checkpoint create/restore exists and is integrated into `/at:run` (`scripts/checkpoint/*`).
- Session directory pollution: cleanup helper exists (`scripts/maintenance/cleanup_sessions.py`, `/at:cleanup-sessions`).
- Final reply contracts: enforced at `SubagentStop` with a circuit breaker (`scripts/hooks/on_subagent_stop.py`).
- Node-based hooks: removed (current repo is Python-only for hooks).

### Partially addressed / still open

- “Binary gates without gradation”: schema supports `acceptance_criteria.severity`, but gates/compliance are still effectively binary (severity is not used by `plan_adherence.py` or `compliance-checker`).
- “Orchestrator is untestable Markdown”: `/at:run` remains prose orchestration (`skills/run/SKILL.md`). A deterministic state/progress engine is still recommended for resume/rerun semantics.
- “Policy hooks are opt-in”: install/uninstall is deterministic and idempotent, but not installed by default in `scripts/init_project.py`.
- “Dry-run / diff preview”: not implemented as a first-class workflow flag (still “Not started” in user stories).
- “Resume from phase / rerun a gate”: session progress exists, but deterministic `--from-phase` controls are not implemented (still “Not started” in user stories).

### F-01 (Critical) — Scope enforcement hook can fail open due to heuristic session/task detection

- Evidence: `scripts/hooks/enforce_file_scope.py`
- Problem: when the hook cannot infer `(session_dir, task_id)` from `transcript_path`, it returns allow (`0`). In those cases, out-of-scope writes are not blocked at tool time.
- Why it matters: scope enforcement is a foundational invariant for safe parallelism and plan adherence.
- Recommendation:
  1) Prefer hook input fields over transcript parsing when available (e.g., `session_id`).
  2) If task_id cannot be determined, consider a “fail-closed outside session dir” mode (deny writes to non-session paths) or at least emit a loud `systemMessage`/log so failures aren’t silent.
  3) Add a deterministic integration check in CI/self-audit: simulate hook input payloads and ensure enforcement triggers.

### F-02 (High) — SubagentStop contract validation can fail open because session inference is transcript-based

- Evidence: `scripts/hooks/on_subagent_stop.py`
- Problem: if session dir can’t be found from transcript content, the hook allows stop without validating the final reply contract or artifacts.
- Recommendation:
  - Use hook input `session_id` to resolve `SESSION_DIR` directly where possible.
  - Optionally scope contract enforcement to known `at` agents (when `payload.agent` matches your agent ids) so other plugins/sessions aren’t affected.

### F-03 (High) — Contract drift risk: schema files vs bespoke validators are not mechanically tied

- Evidence: `schemas/actions.schema.json` vs `scripts/validate/actions_validator.py`
- Problem: contracts exist in multiple forms; validators enforce a subset/superset of schema fields. This is the failure mode highlighted in `plan/audit/previous_plugin_lessons_report.md`.
- Recommendation options (pick one path):
  - **Schema-as-truth**: add `jsonschema` (pinned) and validate `actions.json` against schema + run extra invariants separately.
  - **Validator-as-truth**: treat `scripts/validate/actions_validator.py` as authoritative and generate/export schemas from it (or shrink schema to match what you actually enforce).
  - **Test-as-glue (low-dependency)**: add deterministic “fixture plans” and a script that asserts schema+validator accept/reject the same fixtures.

### F-04 (Medium) — Compliance gate is largely deterministic but implemented as an agent

- Evidence: `agents/compliance-checker.md` decision rules + `scripts/validate/validate_changed_files.py`
- Problem: variability risk without real upside; the decision is almost purely mechanical (missing gate reports, ok flags, etc).
- Recommendation:
  - Make compliance a deterministic script that writes `compliance/COMPLIANCE_VERIFICATION_REPORT.md` (and maybe JSON), and keep an optional agent for narrative explanation only.

### F-05 (Medium) — Skills do not appear to follow the stated per-file version metadata discipline

- Evidence: `CLAUDE.md` “Per-file version metadata” vs `skills/*/SKILL.md` frontmatter (no `version` / `updated`)
- Recommendation:
  - Either add `version`/`updated` to skill frontmatter (preferred if you want strict upgrade diffs), or relax `CLAUDE.md` to state “agents/scripts only”.

### F-06 (Medium) — `/at:run` orchestration is still prose (hard to regression test)

- Evidence: `skills/run/SKILL.md`
- Problem: previous audit flagged “untestable markdown orchestrator” as a reliability risk. While agentic orchestration is desirable, critical sequencing (especially resume/rerun behavior) is hard to validate.
- Recommendation:
  - Keep orchestration agentic, but introduce a tiny deterministic state engine that:
    - reads session progress + required artifacts
    - computes “next actionable step(s)”
    - supports `--from-phase` / `--rerun gate:<id>` deterministically

### F-07 (Low) — P3 surface area is already present in v0.1.0 (risk of premature bloat)

- Evidence: presence of audit/learning/telemetry/project_pack/upgrade scripts and skills
- Recommendation:
  - Keep them opt-in (current state is good), but consider:
    - a clear “core vs optional packs” doc boundary
    - a release discipline where core stabilizes before expanding optional modules

## Suggested Improvements (Prioritized)

### Quick wins (highest ROI)

1) Make enforcement hooks less heuristic:
   - use `session_id` when available; avoid transcript parsing as primary.
2) Add a deterministic self-audit command:
   - checks: referenced scripts exist, schemas/validators consistent, required version metadata present, hook configs valid.
3) Wire `scripts/validate/validate_task_artifacts.py` into `/at:run` before plan adherence:
   - yields clearer errors earlier; makes downstream gates less ambiguous.

### Medium-term (stability + UX)

4) Deterministic compliance writer (script) + optional narrative agent.
5) Deterministic rerun/resume support (`--from-phase`, rerun a single gate) driven by a small script/state engine.
6) Contract drift prevention (schema/validator glue tests).

### Long-term (agentic leverage without losing determinism)

7) Add an explicit remediation agent that reads gate reports and proposes *new plan tasks* (not ad-hoc fixes), with deterministic gates validating outcomes.
8) Improve context quality without expanding context size:
   - let planner include “code pointers” (file paths + grep patterns) that a deterministic script can embed safely.

## Artifacts Produced For This Audit

All artifacts live under `plan/audit/2026-02-01-current/`:
- `current_inventory.json` / `current_inventory.md`
- `compare_previous_plugin.json` / `compare_previous_plugin.md`
- `CURRENT_PLUGIN_AUDIT_REPORT.md` (this document)
