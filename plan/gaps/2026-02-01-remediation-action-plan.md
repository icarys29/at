---
status: draft
created: 2026-02-01
updated: 2026-02-01
scope:
  - "skills/**"
  - "agents/**"
  - "scripts/**"
  - "hooks/**"
  - "templates/**"
  - "schemas/**"
  - "docs/**"
---

# Remediation Action Plan — Evolving Current `at` Beyond Former Plugin

Date: 2026-02-01

This plan closes the most important gaps relative to the former `at` plugin **without copying it verbatim**. The goal is to preserve and amplify the current rebuild’s strengths:

- deterministic, script-backed workflow phases (`uv run …`)
- session-backed evidence
- docs registry v2 + docs-keeper governance and hooks
- language packs and CI-friendly project packs/enforcements
- minimal dependencies (Python-first; avoid Node in core)

## Parallelization plan (what can run concurrently)

This action plan is designed to be parallelizable. Items are grouped into “waves” with explicit dependencies.

### Wave 0 — Parallel-ready foundations (no deps)

These can start immediately, in parallel, provided owners coordinate on shared hotspots:

- **WS-A**: `A1` (triage/review workflows for `/at:run`)
- **WS-B**: `B1` (truthful LSP contract), `B2` (verification runner for file/grep/command)
- **WS-C**: `C2` (audit-report improvements; still trace-safe)
- **WS-E**: `E1` (targeted quality remediation runner)
- **WS-G**: `G1` (canonical `.claude-plugin/plugin.json`), `G2` (YAML frontmatter validation + fixes)

### Wave 1 — Depends on Wave 0 outputs

- After `A1`: `A2` (deliver dry-run), `A3` (TDD strategy directive)
- After `B2`: `C1` (session diagnostics report)
- After `G2`: `D1` (onboarding analyzer: propose/apply)
- After `E1`: `E2` (verify runner)

### Wave 2 — Onboarding/upgrade critical path

- After `D1`: `D2` (overlay migrations: plan/apply/rollback)
- After `D2`: `F1` (optional god-class enforcement as installable check)

### Coordination hotspots (high merge-conflict risk)

Assign a single owner (or merge-sequence) for these files/directories to avoid rework:

- `skills/run/SKILL.md` (workflow parsing + flags + dry-run)
- `scripts/maintenance/self_audit.py` (contract checks will expand across multiple workstreams)
- `schemas/project.schema.json` and `templates/project.yaml` (config shape changes used by multiple items)
- `scripts/validate/*` (verifications, LSP gate integration, gates summary)

## Success criteria (objective)

Current `at` is “better than former” when:

1) The **kernel workflows** are complete and reliable: `deliver`, `triage`, `review`, `ideate` (with clear stop/resume semantics).
2) The plan contract cannot claim checks that won’t run (no “paper verifications”).
3) Diagnosing failures is fast (session diagnostics + actionable remediation).
4) Onboarding existing repos is safe and deterministic (guided but reproducible).
5) Advanced capabilities remain **opt-in** and don’t add fragility to default usage.

## Strategy: parity where it matters, innovation where current is stronger

- Treat former plugin behaviors as **user stories**, not implementation templates.
- Prefer **deterministic scripts + explicit artifacts** over interactive “wizard state” wherever possible.
- Prefer improving **session artifacts** for observability (low sensitivity) over relying on audit traces (high sensitivity).
- Keep “strictness” configurable:
  - allow onboarding in a “lenient” mode (fail-open where appropriate)
  - allow corporate-grade enforcement in “strict” mode (fail-the-gate)

## Workstreams & Remediation Backlog

### WS-A — Complete the kernel workflows (P0)

**A1. Make `/at:run` support all workflows (`deliver|triage|review|ideate`)**

- Goal: restore the “workflow kernel” promise while retaining the current architecture-brief + user-stories separation.
- Design (better than former):
  - Keep `deliver` as the “full pipeline”.
  - `triage` writes RCA artifacts + optionally produces a remediation `actions.json`, but **does not** default to implementation.
  - `review` produces an evidence-backed review report and can optionally run the quality suite (configurable).
  - `ideate` stays plan-less by default but can optionally emit a candidate `actions.json` behind a flag.
- Deliverables:
  - Update `skills/run/SKILL.md` to accept `deliver|triage|review|ideate` as leading argument (back-compat: when omitted → deliver).
  - Add missing agents referenced by schema: `agents/root-cause-analyzer.md`, `agents/reviewer.md` (minimal, deterministic, artifact-driven).
  - Add deterministic runner scripts (or reuse existing ones) for triage/review artifacts:
    - `scripts/workflow/run_triage.py` (or extend `run_deterministic.py`)
    - `scripts/workflow/run_review.py`
- Verification:
  - Extend `scripts/maintenance/self_audit.py` to ensure any schema owner has a corresponding agent definition.
  - Create session fixture runs for triage/review that produce expected artifacts.

**A2. Add deliver dry-run (plan-only)**

- Goal: safe preview for risky repos/requests (no repo edits).
- Design (better than former):
  - Implement as a deterministic phase path:
    - create/resume session → context pack → architecture brief → user stories → actions.json → validate actions → compute docs requirements → STOP
  - Write `final/dry_run_report.{md,json}` including gates run, planned tasks, expected file scopes, required docs, and what would have run next.
- Deliverables:
  - `scripts/workflow/generate_dry_run_report.py` (current repo doesn’t have this; former did).
  - `/at:run --dry-run` flag (or `/at:plan` alias skill if you want a simpler surface).
- Verification:
  - Report must be stable for same inputs (no timestamps except `generated_at`).
  - Must not create checkpoint or dispatch implement/test tasks.

**A3. Add a “TDD strategy” that does not complicate the orchestrator**

- Goal: provide “tests first” workflow without baking in excessive special cases.
- Design (better than former):
  - Introduce a planner directive (flag or config) that influences `action-planner` output:
    - requires `tests-builder` tasks to precede implementor tasks where appropriate
    - acceptance criteria include “tests written first” verifications where applicable
  - Keep orchestrator logic unchanged (it just executes the DAG).
- Deliverables:
  - `workflow.strategy: default|tdd` in `.claude/project.yaml` (optional).
  - Update `agents/action-planner.md` to respect it.
- Verification:
  - `validate_actions.py` ensures task dependencies enforce tests-first when strategy=tdd.

### WS-B — Eliminate contract gaps: verifications & LSP (P0)

**B1. Fix the `lsp` verification contract**

- Problem: schema allows `lsp` verifications, but current validation explicitly skips them.
- Goal: make the system truthful.
- Options (choose one; recommended is #1):
  1) **Implement LSP verifications as an opt-in agent-run step**, and gate on recorded evidence.
  2) Disallow `lsp` verifications in `validate_actions.py` until implemented.
- Recommended design (better than former):
  - Add `.claude/project.yaml`:
    - `lsp.enabled: true|false` (default false)
    - `lsp.mode: fail|warn|skip` (controls gate behavior)
  - Add a minimal `agents/lsp-verifier.md` (tools include `LSP`, plus Read/Write).
  - Add deterministic artifact contract:
    - `SESSION_DIR/quality/lsp_verifications.json` (machine)
    - `SESSION_DIR/quality/lsp_verifications.md` (human)
  - Update `plan_adherence.py` / gate summary to treat LSP verifications as:
    - FAIL only when `lsp.mode=fail` and LSP checks fail
    - WARN when `lsp.mode=warn`
    - SKIP when `lsp.enabled=false`
- Verification:
  - A plan containing `lsp` verifications must be rejected (or explicitly marked skip/warn) according to config.

**B2. Add a “verification runner” that produces evidence for *all* verification types**

- Goal: acceptance criteria verifications are actionable and auditable.
- Design:
  - Keep scripts for `file|grep|command`.
  - Reserve `lsp` for the LSP verifier agent.
  - Store evidence under `SESSION_DIR/quality/verification_evidence/*`.
- Deliverables:
  - `scripts/validate/run_verifications.py` (runs file/grep/command verifications deterministically from `actions.json`).
  - Gate: `scripts/validate/verifications_gate.py` (binary).
- Verification:
  - Fixtures: passing + failing plans produce stable evidence and actionable failures.

### WS-C — Better observability without sensitive audit logs (P1)

**C1. Session diagnostics report (artifact-first, audit-optional)**

- Goal: replace the former’s “session auditor” value with a lower-risk, deterministic alternative.
- Design (better than former):
  - Prefer reading session artifacts:
    - `planning/actions.json`
    - task summaries
    - gates summary
    - telemetry KPIs
  - Only consult `.claude/audit_logs` when explicitly enabled and available.
- Deliverables:
  - `scripts/session/session_diagnostics.py` producing:
    - `SESSION_DIR/status/session_diagnostics.json`
    - `SESSION_DIR/status/session_diagnostics.md`
  - Skill: `/at:session-diagnostics [--session <id|dir>]`
- Verification:
  - Deterministic output given same session artifacts.

**C2. Expand audit reporting safely (still lightweight)**

- Goal: keep current `audit-report` simple but more useful than counters.
- Design:
  - Add timing/latency summaries by tool name and hook event.
  - Add “top failures” list (exit codes / blocked reasons) without embedding raw tool inputs by default.
- Deliverables:
  - Extend `scripts/audit/analyze_audit_logs.py` (new report fields).
  - Keep trace capture opt-in and separated.

### WS-D — Onboarding & upgrades (P0/P1)

**D1. Repo onboarding: doctor-driven proposal instead of invasive import**

- Goal: help existing repos adopt `at` safely and reproducibly.
- Design (better than former):
  - A deterministic “onboarding analyzer” script writes proposals, not changes:
    - proposed `.claude/project.yaml` language blocks / quality commands (best-effort detection)
    - recommended language packs to install
    - docs registry v2 seed suggestions
  - Application is explicit (`--apply`) and uses backups.
- Deliverables:
  - `scripts/onboarding/analyze_repo.py` → `onboarding_report.{json,md}`
  - `scripts/onboarding/apply_onboarding.py` (writes overlay + backups)
  - Skill: `/at:onboard [--apply]`
- Verification:
  - Idempotent apply; diff is limited to overlay + docs (never production code).

**D2. Overlay migrations with backups (real upgrade tool)**

- Goal: move beyond the current minimal `upgrade-project` while staying safe.
- Design:
  - Schema-versioned migrations (each migration is a deterministic function).
  - Always produce:
    - backup tar/dir
    - migration report
    - dry-run preview
- Deliverables:
  - `scripts/upgrade/migrate_overlay.py` with subcommands:
    - `plan` (dry-run)
    - `apply`
    - `rollback`
  - Extend `/at:upgrade-project` to call this.

### WS-E — Targeted remediation tools (P1)

**E1. “Resolve one failing quality command” (deterministic loop)**

- Goal: shorten time-to-green without uncontrolled edits.
- Design (better than former):
  - Read `SESSION_DIR/quality/quality_report.json`
  - Select one failing command id and run only that remediation (format-only by default; lint/test fixes require explicit plan tasks)
  - Record what changed and re-run only the failing command
- Deliverables:
  - Skill `/at:fix-quality <command_id> [--session <id|dir>]` (or extend existing quality suite tooling).
  - Script `scripts/quality/rerun_quality_command.py`

**E2. “Verify before PR” (project-specific, composable)**

- Goal: a repeatable pre-PR checklist based on project config + enforcements + docs lint.
- Design:
  - Composable runner reads `.claude/project.yaml` and optional `.claude/at/enforcement.json`
  - Outputs one report + exit code for CI
- Deliverables:
  - `scripts/quality/verify.py` (not necessarily called “verify”; avoid copying former naming unless desired).

### WS-F — Optional advanced enforcement (P2)

**F1. God-class detection as an installable enforcement check (optional)**

- Goal: regain SRP pressure without coupling it to default workflows.
- Design (better than former):
  - Keep it as an overlay-installed check:
    - `.claude/at/enforcement.json` includes `type=python` pointing to a project-local script
  - Provide a small installer under `scripts/enforcement/install_god_class_check.py` that copies a deterministic checker into `.claude/at/scripts/`.
- Deliverables:
  - Installer + template config snippet
  - Quality suite integrates enforcement report already (keep).

### WS-G — Packaging + contract hygiene (P0/P1)

**G1. Align plugin manifest with upstream conventions**

- Goal: improve install/portability.
- Design:
  - Introduce `.claude-plugin/plugin.json` (canonical for Claude Code).
  - Keep root `plugin.json` only if needed internally; ensure version stays consistent.
- Deliverables:
  - Manifest migration + docs update + self-audit check for consistency.

**G2. Validate YAML frontmatter across skills/agents**

- Goal: prevent subtle “command not loadable” failures.
- Deliverables:
  - Extend `scripts/maintenance/self_audit.py` to parse YAML frontmatter and fail if invalid.
  - Fix any unquoted strings that contain `:` (or other YAML gotchas).

## Milestones (phased)

### Milestone 1 — Kernel parity, truthful contracts (P0)

- `/at:run` supports `deliver|triage|review|ideate` with deterministic artifacts.
- `--dry-run` deliver path exists.
- `lsp` verifications are either implemented behind config or rejected (no silent skip).
- Self-audit verifies schema↔agent parity and YAML frontmatter validity.

### Milestone 2 — Diagnostics + onboarding (P1)

- Session diagnostics report exists.
- Onboarding analyzer exists (plan/apply with backups).
- Overlay migrations framework exists (plan/apply/rollback).

### Milestone 3 — Productivity + optional power (P2)

- Targeted quality remediation runner exists.
- Verify runner exists for PR/CI.
- Optional god-class enforcement is available as an installable check.

## Risk management

- LSP integration risk: keep opt-in, and never let plans claim LSP checks without explicit configuration.
- Onboarding risk: propose first, apply explicitly; always back up; never touch production code.
- Strictness risk: provide “lenient” onboarding defaults, allow projects to tighten later.
- Sensitivity risk: prefer session artifacts; keep traces off-by-default and separated.

## Next step

Turn this plan into an executable backlog by creating a tracking file (e.g., `plan/gaps/REMEDIATION_BACKLOG.json`) mapping each work item to:

- priority (P0/P1/P2)
- owner component (skill/agent/script/hook/schema/template)
- acceptance tests / artifacts
- migration notes
