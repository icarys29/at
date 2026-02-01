# Audit — Brainstorm Integration (obra/superpowers inspired)

Date: 2026-02-01

## Internet Source Reviewed

- `obra/superpowers` brainstorming skill (`skills/brainstorming/SKILL.md`)

Notable behaviors:
- structured ideation flow (clarify prompt, explore alternatives, validate understanding)
- incremental output (chunked) and “ask before continuing”
- writes a persistent design artifact (their convention: `docs/plans/YYYY-MM-DD--design.md`)

## Fit/Gaps vs `at`

`at` constraints:
- session artifacts are first-class; orchestration should not mutate repo code
- deterministic gates + contract-driven subagents
- minimal context; avoid bloat

Potential conflicts if copied verbatim:
- writing/committing design docs into repo during ideation would violate “session-only until implementation” discipline
- interactive “ask before continuing” can break contract validation if no artifacts are produced

## Integration Design (best of both worlds)

Implemented an ideation workflow that preserves at’s determinism while capturing superpowers’ structured ideation value:

1) **Architecture brief (evidence-backed anchors)** via `solution-architect`
2) **Brainstorm options + recommendation** via `brainstormer`
3) Always writes session artifacts (even if questions remain), enabling reliable gating and reruns.

## What was implemented

- New subagent: `brainstormer`
  - Outputs: `planning/IDEATION.{md,json}`
  - Includes: constraints anchors, open questions + assumptions, options, recommendation, and handoff hints (`doc_ids`, `code_pointers`, verifications)
- New skills:
  - `/at:ideate` — creates session `workflow=ideate`, runs `solution-architect` then `brainstormer`
  - `/at:brainstorm` — alias of `/at:ideate`
- Documentation:
  - Added ideation entrypoint mention to project context and canonical workflow list.

## Why this improves reliability and efficiency

- Keeps ideation outputs deterministic and session-scoped.
- Improves planning quality without overloading the `action-planner` role.
- Provides concrete anchors that reduce “LLM improvisation”:
  - pattern anchors (path + grep pattern)
  - registry-driven doc selection hints
  - stable verification hints

