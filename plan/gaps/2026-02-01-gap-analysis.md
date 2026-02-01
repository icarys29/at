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

# Gap Analysis — Former vs Current `at` Plugin

Date: 2026-02-01

## Scope

- **Former plugin**: `at` v0.7.42 (updated 2026-01-31), located at `/home/dav/claude/claude-agent-team-plugin`.
- **Current plugin**: `at` v0.1.0 (updated 2026-02-01), this repo at `/home/dav/claude/at`.

Summary deltas (inventory snapshot):
- Former: 32 skills, 20 agents, richer audit/session analysis, LSP-backed docs/verification, repo import, TDD/verify utilities.
- Current: 29 skills, 10 agents, `uv run` determinism, docs registry v2 + docs-keeper gates/hooks, language packs, explicit E2E support, phase/gate reruns.

## Capability Gap Analysis (Former vs Current)

### 1) Plugin packaging + compatibility

**Capability**: “standard Claude Code plugin layout + discoverability”

- Former: Uses the expected `.claude-plugin` manifest pattern and richer manifest metadata.
  - Advantage: predictable discovery/metadata and easier portability across machines.
  - Disadvantage: larger surface area and older conventions can drift with upstream changes.
- Current: Uses a root-level manifest style and relies heavily on `uv run`.
  - Advantage: simple for local `claude --plugin-dir .` usage and script determinism.
  - Disadvantage: less aligned with upstream “manifest location” expectations; higher risk of install/discovery friction in teams.

### 2) `/at:run` workflow coverage

**Capability**: one entry point for `deliver|triage|review|ideate`

- Former: `/at:run` supports `deliver|triage|review|ideate` plus `--tdd`, `--dry-run`, `--rollback`.
  - Advantage: complete workflow menu; fewer “invent a process” gaps.
  - Disadvantage: larger orchestrator surface area to maintain.
- Current: `/at:run` is deliver-centric; ideation is split into `/at:ideate`, `/at:brainstorm`, `/at:architecture-brief`.
  - Advantage: clearer separation of concerns (architecture/story/planning vs execution).
  - Disadvantage: missing triage/review workflows; lacks deliver dry-run/TDD switches, so the “kernel” promise is only partially met.

### 3) Deterministic reruns vs dry-run

**Capability**: rerun without re-doing everything

- Former: had a deliver dry-run path (plan/report only; no repo changes).
  - Advantage: safe preview for high-risk changes.
  - Disadvantage: less targeted than rerunning a single gate.
- Current: adds rerun-by-phase/gate (`--from-phase` / `--gate`) and checkpoint restore ergonomics.
  - Advantage: faster debugging/remediation when a deterministic step fails.
  - Disadvantage: lacks a first-class “plan-only deliver preview” UX.

### 4) Session artifact discipline

**Capability**: sessions as the unit of work/evidence

- Both: strong session directories, deterministic artifacts, and checkpoint/rollback support.
- Former advantage: more “meta” tooling around sessions (session auditor, richer audit analytics).
- Current advantage: additional deterministic operational helpers (gate reruns, task board).
- Tradeoff: current is cleaner for “workflow as a pipeline”; former is better for “workflow as something you diagnose/coach over time”.

### 5) Planning contract (`actions.json`) + enforcement

**Capability**: plan schema validation, file scope enforcement, acceptance criteria, parallel safety

- Both: plan validation + parallel conformance + changed-files attribution + file-scope enforcement hooks.
- Former advantage: broader workflow owner ecosystem implemented via agents and gates.
- Current advantage: stronger emphasis on verifications + user stories + deterministic docs requirements computation.
- Current disadvantage: schema includes `lsp` verification type but implementation treats LSP verifications as “not implemented / skipped”, creating a “paper contract” risk.

### 6) LSP-based verification

**Capability**: language-intelligent checks (beyond grep/command)

- Former: LSP server wiring + an LSP gate/agent.
  - Advantage: catches refactors/API drift semantically; enables LSP-driven docs analysis.
  - Disadvantage: heavier setup (LSP servers, perf, more failure modes).
- Current: no real LSP enforcement.
  - Advantage: fewer moving parts.
  - Disadvantage: cannot validate symbol-level claims; any “lsp” verification in plans gives false confidence.

### 7) Quality gate (format/lint/typecheck/test/build)

**Capability**: deterministic quality suite with evidence

- Both: run configured commands and emit structured reports with logs; both can run project-local enforcements.
- Former advantage: targeted remediation workflows (“resolve failing command”) and god-class integration.
  - Disadvantage: more opinionated and more config surface.
- Current advantage: language packs can provide structured defaults (opt-in); E2E config is cleanly separated.
  - Disadvantage: no “single failing command” remediation workflow equivalent.

### 8) E2E as a first-class concern

**Capability**: explicit E2E setup + execution + gating

- Former: E2E primarily as an optional quality command behavior (skip if env/files missing).
  - Advantage: minimal extra config.
  - Disadvantage: E2E is easy to neglect and hard to reason about consistently.
- Current: adds `e2e_mode` (off/optional/required), `.claude/at/e2e.json`, `/at:setup-e2e`, `/at:e2e`, and an E2E gate.
  - Advantage: “done means end-to-end done” becomes enforceable.
  - Disadvantage: another config surface area teams must maintain.

### 9) Compliance determinism

**Capability**: compliance report that’s stable and auditable

- Former: leaned more on agent-written reports.
  - Advantage: nuanced narrative possible.
  - Disadvantage: more variance across runs.
- Current: deterministic compliance report generation (with optional narrative checker).
  - Advantage: repeatable “decision” artifact, better for CI and audits.
  - Disadvantage: nuanced edge cases still require human/agent interpretation (now clearly separated from the decision).

### 10) Documentation system (largest delta)

**Capability**: docs-as-contract + drift prevention

- Former: strong automation (bootstrap/sync/validate/audit) and LSP-backed analysis; registry formats drifted historically (e.g., `docs/REGISTRY.json` vs `docs/DOCUMENTATION_REGISTRY.json`).
  - Advantage: can generate/audit docs aggressively.
  - Disadvantage: more complexity and higher drift/cognitive overhead risk.
- Current: consolidates on docs registry v2 (doc types + templates + coverage rules), deterministic docs planning + linting, minimal docs edits, and docs-keeper hooks (drift warning + pre-commit/PR gate).
  - Advantage: predictable, corporate-grade “minimum necessary docs” with less bloat.
  - Disadvantage: fewer “generate everything from code” capabilities; relies more on humans for content.

### 11) Project packs + architecture enforcement

**Capability**: enforce architectural boundaries, not just describe them

- Former: interactive project-pack interviewer and enforcement runner, plus god-class detection as an enforcement signal.
  - Advantage: guided setup chooses constraints intelligently.
  - Disadvantage: interactive flows are less reproducible and harder to standardize.
- Current: deterministic installers for project packs and scaffolding for hex boundary checks + enforcement runner.
  - Advantage: reproducible and CI-friendly.
  - Disadvantage: no guided “interview” UX; no god-class detection equivalent.

### 12) Language guidance

**Capability**: per-language rules and quality defaults

- Former: language rule templates + tooling config templates (ruff/mypy/tsconfig/golangci/etc.).
  - Advantage: accelerates standing up real tooling.
  - Disadvantage: may conflict with repo conventions.
- Current: language packs provide structured metadata + concise rules; overlay-only by default (does not rewrite project tooling).
  - Advantage: safer onboarding and consistent planner hints.
  - Disadvantage: does not scaffold the actual toolchain configs; “quality reality” may lag.

### 13) Hooks & safety guardrails

**Capability**: secrets/destructive command blocking + scope enforcement + observability hooks

- Former: broader hook set including Task invocation validation and extra UX nudges (debug detection, compaction suggestions) but required Node for some hooks.
  - Advantage: more proactive coaching/guardrails.
  - Disadvantage: more runtime deps and hook complexity.
- Current: Python-only managed hooks (audit/policy/learning/docs-keeper), modern session lifecycle hooks, and docs gating.
  - Advantage: fewer dependencies and stronger docs drift prevention.
  - Disadvantage: missing Task invocation validation and missing “compact/debug” nudges.

### 14) Audit + session observability

**Capability**: diagnose “what happened and why” across sessions

- Former: full audit subsystem (parsing, scoring, recommendations, trace detail, session auditor).
  - Advantage: excellent for debugging and improving team workflows.
  - Disadvantage: heavier and can become sensitive/expensive if traces are enabled.
- Current: lightweight audit reporting plus reliance on session artifacts.
  - Advantage: simpler and safer by default.
  - Disadvantage: less actionable when workflows degrade or agents behave inconsistently.

### 15) Telemetry/KPIs

**Capability**: measure workflow efficiency/outcomes

- Former: per-session KPIs with older reporting patterns.
- Current: per-session KPI + separate rollup producing stable JSON/MD.
  - Advantage: easier automation and aggregation.
  - Disadvantage: lacks a higher-level “session auditor” coaching loop.

### 16) Learning/memory

**Capability**: persistent per-project learning and updates

- Both: learning status + update workflows.
- Former advantage: “continuous-learning” skill for extraction.
- Current advantage: clean install/uninstall for learning hooks (session-start context capture).
- Current disadvantage: no direct equivalent to the former continuous-learning extractor.

### 17) Onboarding existing repos + upgrades

**Capability**: bring messy repos under control safely

- Former: repo-importer/import wizard + more comprehensive upgrade flow.
  - Advantage: smoother onboarding for established codebases.
  - Disadvantage: more logic and edge cases to maintain.
- Current: strong “bootstrap overlay + install packs” primitives, but overlay upgrade is conservative.
  - Advantage: safer building blocks.
  - Disadvantage: missing a true onboarding wizard and robust overlay upgrade management (schema/rules/hooks drift handling).

### 18) Developer productivity utilities

- Former-only: `verify`, `tdd-workflow`, `retrospective`, `resolve-failed-quality`, `strategic-compact`, `help`, god-class detector tooling, session auditor tooling.
- Current-only: first-class architecture brief + ideation entry points; explicit E2E setup/run; docs-keeper hooks install; language/project pack installers; telemetry rollup; self-audit; deterministic gate reruns; granular hook uninstall commands.

## Missing Functionality (Current vs Former)

- Missing “core workflow parity”: triage + review workflows, deliver dry-run, TDD mode.
- Missing “semantic enforcement”: LSP gate and LSP-backed verifications/docs analysis.
- Missing “diagnostics depth”: session auditor and richer audit scoring/recommendations.
- Missing “onboarding muscle”: repo import wizard and robust overlay upgrade mechanism.
- Missing “power tools”: verify, resolve-failed-quality, retrospective, strategic-compact, god-class detection.
- Missing “guardrail completeness”: Task invocation validation hook and “debug/compact” nudges.

## What Current Does Better (objectively)

- Stronger docs system design: single-source docs registry v2 + deterministic docs plan/lint + drift/commit gating.
- Cleaner enforcement scaffolding: deterministic installers for language/project packs; CI-friendly architecture boundary enforcement.
- Better E2E ergonomics: explicit config + dedicated command + gate + project-safe setup scaffolding.
- Better determinism tooling: rerun-by-phase/gate and “pipeline-like” workflow mechanics.
- Fewer runtime deps in hooks (no Node), more consistent managed hook install/uninstall.

## Recommendation (as of 2026-02-01)

- Recommend **former plugin (v0.7.42)** if you need the full “workflow kernel” now (triage/review, LSP-backed verification/docs, deep audit/session analysis, onboarding/import, verify/TDD utilities) and you value completeness over rebuild cleanliness.
- Recommend **current plugin (v0.1.0)** if your real usage is primarily “deliver + strong docs governance + E2E + deterministic enforcement”, and you accept (or will implement) the missing workflow/diagnostic/LSP/onboarding pieces.

## Improvements to Make the Current Plugin the Clear Winner (prioritized)

- P0: restore workflow parity (triage + review; decide on deliver dry-run + TDD contract).
- P0: remove “paper contracts” (either implement LSP verifications/gate or disallow them in plans).
- P0: onboarding + upgrades (repo import wizard or doctor-driven onboarding, plus real overlay migrations with backups).
- P1: targeted remediation utilities (resolve one failing quality command; verify before PR; controlled retrospective behind confirmation).
- P1: observability upgrades (session diagnostics + richer audit analytics with safe defaults).
- P2: optional power features (god-class detection as an installable enforcement; opt-in UX nudges).

