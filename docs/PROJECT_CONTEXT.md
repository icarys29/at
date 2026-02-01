# Project Context

<!-- Keep every section concise: required and sufficient information only. No filler. -->

## Purpose

This repository is the **Agent Team (`at`) Claude Code plugin**: a deliver workflow that combines agentic work with deterministic scripts/gates to produce reproducible, auditable outcomes.

- Primary users: developers running `/at:run` inside Claude Code.
- What success looks like: consistent session artifacts, reliable validation gates, and docs that stay accurate as the plugin evolves.

## Runtime + Deliverables

- Type: plugin + workflow scripts + agent prompts
- Primary runtime: Python 3.10+ (scripts), Claude Code agents (markdown prompts)
- Supported platforms: dev environments where Claude Code runs (macOS/Linux/Windows)

## Architecture Overview

Authoritative contract: `CLAUDE.md`.

- `skills/`: user-facing workflows (e.g., deliver `/at:run`)
- `agents/`: subagent prompts (planner, implementor, tests, docs, quality, compliance)
- `scripts/`: deterministic steps (session management, context building, validation gates, quality suite)
- `schemas/`: JSON schemas for artifacts (plan, reports)

## Public Surface Area

- Primary entrypoint: `/at:run` (deliver workflow)
- Primary outputs: session-backed artifacts under `.session/<session_id>/`

## Deliver Workflow (always-on docs maintenance)

High-level flow (inputs → scripts/agents → outputs):

1) Request → `scripts/session/create_session.py` → `SESSION_DIR/`
2) Context pack → `scripts/context/build_context_pack.py` → `SESSION_DIR/inputs/context_pack.md`
3) Plan (agentic) → `action-planner` → `SESSION_DIR/planning/actions.json`
4) Plan gates → `scripts/validate/validate_actions.py` → pass/fail with remediation
5) Docs requirements (deterministic) → `scripts/docs/docs_requirements_for_plan.py` → `SESSION_DIR/documentation/docs_requirements_for_plan.{json,md}`
6) Per-task context slices → `scripts/context/build_task_contexts.py` → `SESSION_DIR/inputs/task_context/*.md` (+ manifest)
7) Implement/test tasks (agentic) → `implementor` / `tests-builder` → `SESSION_DIR/{implementation,testing}/tasks/*.yaml`
8) Gates → quality/compliance/changed-files → session reports
9) Docs update (agentic, always-on) → `docs-keeper` → repo `docs/*` + regenerated registry MD
10) Docs gate (deterministic) → `scripts/validate/docs_gate.py` → `SESSION_DIR/documentation/docs_gate_report.{json,md}`
11) Task board (deterministic) → `scripts/session/task_board.py` → `SESSION_DIR/status/task_board.{json,md}`

## Local Development

- Self-audit: `uv run scripts/maintenance/self_audit.py`
- Quality gates (single script): `uv run scripts/quality/run_quality_suite.py --session <SESSION_DIR>`

## Documentation Registry

This repo uses a deterministic docs registry at `docs/DOCUMENTATION_REGISTRY.json` (v2):

- Registry is the single source of truth for managed docs (`docs[]`) and generated artifacts (`generated_artifacts[]`).
- Document taxonomy is explicit (`doc_types[]`) and templates live under `docs/_templates/`.
- Coverage rules (`coverage_rules[]`) drive deterministic “what docs must change / be created” decisions.
- Each doc entry includes `when` to support planner-driven context selection.
- `docs/DOCUMENTATION_REGISTRY.md` is generated from JSON and must remain in sync (drift is gate-enforced).

## Constraints

- Prefer agentic work for creation/analysis; use scripts as deterministic gates and reproducible evidence.
- Keep documentation corporate-grade but concise; ADRs only for decisions likely to matter in 3+ months.
