# Current Plugin Audit Report (at)

- Date: 2026-02-01
- Scope: this repo working tree at `plugin.json` version `0.1.0` (`main`)
- Comparison baseline: prior `at` plugin snapshot v`0.7.42` (see `plan/audit/previous_plugin_*`)

## Executive Summary

The rebuild is aligned with the ambitions in `CLAUDE.md`: **session-backed delivery**, **strict contracts**, and **deterministic evidence** (reports/gates) wrapped around **agentic semantic work** (planning + implementation + tests + docs).

On the “scripts vs agentic” question: the current split is directionally correct **if** you treat scripts as:

- deterministic scaffolding (sessions/context/checkpoints),
- deterministic enforcement (hooks),
- deterministic gates (validators + quality suite + docs gate),

and treat agents as:

- semantic decision-making (plan, code changes, test strategy),
- documentation authoring/updating (corporate-grade but concise).

The primary risk in earlier revisions was not “too many scripts”, but **heuristic enforcement** (transcript inference) and **contract drift** (multiple sources of truth). Those were the highest priority fixes, and have now been implemented.

Additionally, deliver now includes **always-on documentation updates** (via `docs-keeper`) with a **registry-driven `when` field** to help planning agents decide which docs to embed for each task.

## Snapshot (Current vs Previous)

See `plan/audit/2026-02-01-current/compare_previous_plugin.md` and `plan/audit/2026-02-01-current/current_inventory.json`.

- Previous plugin snapshot (v0.7.42): 20 agents, 32 skills, 96 Python files, 7 JS files
- Current plugin (v0.1.0): 6 agents, 20 skills, 55 Python scripts, 0 JS files

Key differences:
- Current is Python-only, simpler surface area, and relies on a smaller set of “kernel” agents.
- Deterministic gates and session evidence are explicit and first-class.

## Ambitions & Goals Alignment

### Strong alignment (implemented)

- **Session-first workflow:** `scripts/session/create_session.py` creates deterministic `SESSION_DIR` layout and `session.json`.
- **Agentic planning, deterministic validation:** `agents/action-planner.md` + `scripts/validate/validate_actions.py` (+ hook-time validation).
- **Least-context execution:** `scripts/context/build_context_pack.py` and `scripts/context/build_task_contexts.py` generate bounded per-task context slices.
- **Strict scope enforcement:** `scripts/hooks/enforce_file_scope.py` blocks out-of-scope writes.
- **Binary gates + evidence:** task artifact validation, plan adherence, parallel conformance, quality suite, docs gate, changed-files enforcement, compliance report.
- **Rollback safety:** checkpoint create/restore is available and tied to the deliver workflow.

### Added (docs always-on; requested)

- **Docs are always updated as part of deliver:** `agents/docs-keeper.md` is now part of the deliver gate sequence (before the docs gate).
- **Registry-driven doc selection:** `docs/DOCUMENTATION_REGISTRY.json` includes required `when` fields; `docs/DOCUMENTATION_REGISTRY.md` is generated from JSON.
- **Deterministic enforcement:** `scripts/validate/docs_gate.py` now fails when:
  - any doc entry is missing `when`, or
  - `docs/DOCUMENTATION_REGISTRY.md` drifts from the JSON registry.

## Scripts vs Agentic Capabilities (Audit)

### What scripts should do (and mostly do)

- **Scaffolding:** sessions, context pack building, checkpoints.
- **Enforcement:** hooks that block invalid plan writes / out-of-scope writes / contract violations.
- **Gates:** deterministic checks that emit evidence artifacts and stop on failures.

### What agents should do (and mostly do)

- **Planning:** interpret user request into tasks with safe parallel file scopes and explicit acceptance criteria.
- **Implementation & tests:** make changes and record per-task artifacts.
- **Docs (always-on):** update project docs to match delivered work, keep docs concise, and maintain a planner-actionable registry.

### Practical conclusion

The repository does not “rely too heavily on scripts” in the problematic sense. The right framing is:

- Scripts are the *deterministic rails* and *auditable evidence*.
- Agents are the *semantic engines* and *creative workhorses*.

The biggest constraint to agentic leverage is not script count, but **how much the plan/context/doc registry can reduce entropy** in what agents decide.

## Findings & Remediations

This section maps the original audit findings to changes made. Evidence is in the repo itself (see referenced paths), plus the improvements commit `dbd8241` and subsequent docs work.

### F-01 (High) — Hook enforcement relied on transcript inference (fail-open risk)

- Status: Remediated (see commit `dbd8241`)
- Outcome: enforcement uses deterministic session/task signals where possible and degrades safely.

### F-02 (High) — SubagentStop contract enforcement could fail open

- Status: Remediated (see commit `dbd8241`)
- Outcome: contract enforcement is reliably applied for the at subagents.

### F-03 (High) — Contract drift risk (schemas vs bespoke validators)

- Status: Partially addressed (see commit `dbd8241`)
- Outcome: deterministic self-audit exists and guards plugin integrity; schema/validator “glue tests” remain a medium-term improvement if drift resurfaces.

### F-04 (Medium) — Compliance decision is deterministic but was an agent

- Status: Remediated (see commit `dbd8241`)
- Outcome: compliance report is now deterministic (`scripts/compliance/generate_compliance_report.py`), with an optional narrative agent remaining.

### F-05 (Medium) — Version metadata discipline inconsistent

- Status: Remediated (see commit `dbd8241`)
- Outcome: per-file version headers are enforced via tooling and self-audit.

### F-06 (Medium) — Deliver orchestration was prose-only (hard to regression test)

- Status: Remediated (see commit `dbd8241`)
- Outcome: deterministic rerun support exists (`scripts/workflow/run_deterministic.py`) and deliver documents the gate list.

### F-07 (Low) — Optional subsystem surface area might bloat early

- Status: Mitigated
- Outcome: optional packs remain opt-in and are kept outside the core “deliver” swimlane.

### F-08 (High, newly identified during follow-up) — Documentation updates were not explicit in deliver

- Status: Remediated (this working tree)
- Outcome:
  - deliver runs `docs-keeper` (always-on) before `docs_gate.py`;
  - docs registry includes required `when` field for planner selection;
  - registry Markdown is generated from JSON and drift is gate-enforced.

## Recommended Improvements (and implementation status)

See `plan/audit/2026-02-01-current/RECOMMENDED_IMPROVEMENTS.md` for the tracked backlog.

Highlights:
- P0/P1 reliability items implemented in `dbd8241`.
- Documentation “always-on + planner-actionable registry (`when`/`tags` + deterministic drift check)” implemented in this working tree.

## Artifacts Produced For This Audit

All artifacts live under `plan/audit/2026-02-01-current/`:

- `CURRENT_PLUGIN_AUDIT_REPORT.md` (this report)
- `RECOMMENDED_IMPROVEMENTS.md` (backlog with status)
- `findings.json` (structured findings)
- `current_inventory.json` / `current_inventory.md` (inventory)
- `compare_previous_plugin.json` / `compare_previous_plugin.md` (comparison)
- `deliver_workflow_diagram.{md,txt}` (ASCII workflow + IO)
- `deliver_workflow_swimlane.txt` (swimlane view)

