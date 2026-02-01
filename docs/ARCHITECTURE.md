# Architecture (at) — Plugin Overview

- Last updated: 2026-02-01

## 1) Architecture summary (concise)

- Style: workflow orchestration + deterministic validation gates
- Primary runtime(s): Claude Code agents + Python scripts (3.10+)
- Data stores: session filesystem under `.session/<session_id>/` (JSON/MD/YAML artifacts)
- Communication: local process execution (`uv run ...`) + Claude Code subagents

## 2) Architecture patterns in use

- **Session-backed evidence** — every deliver run writes structured artifacts to `SESSION_DIR/*` for reproducibility.
- **Agentic + deterministic split** — agents produce plans/changes; scripts validate invariants and produce audit-friendly reports.
- **File-scope enforcement** — plan declares allowed writes per task; hooks enforce scope during execution.

## 3) Boundaries & dependencies (corporate-grade)

- Boundary: `agents/` owns prompting + role contracts; it must not embed repo-specific implementation logic that belongs in scripts.
- Boundary: `scripts/` owns deterministic validation, report generation, and artifact IO.
- Boundary: `skills/` owns workflow composition (ordering of agents + scripts).
- Dependency direction: `skills/` → `agents/`/`scripts/`; scripts may import from `scripts/lib/` only.

## 4) Key decisions (ADR index)

- ADRs live under `docs/adr/`.
- Add an ADR only for decisions that materially affect future evolvability (avoid ADR spam).

