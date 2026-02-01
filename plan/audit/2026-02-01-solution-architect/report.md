# Audit — SRP Architecture Brief Phase

Date: 2026-02-01

## Motivation

The `action-planner` was optimized for **task decomposition + parallel safety**, but did not explicitly guarantee:
- architectural intent extraction (beyond restating the request)
- pattern reuse (finding “similar implementations”)
- consistent constraint enforcement (rules/docs as first-class anchors)
- deterministic guidance for which docs/verification commands to load per task

This can lead to plans that are mechanically valid but architecturally shallow.

## Change Summary

Introduced a new, SRP-separated phase and subagent:

- Subagent: `solution-architect` (plugin agent)
  - Inputs: `SESSION_DIR/inputs/request.md`, `SESSION_DIR/inputs/context_pack.md`
  - Outputs:
    - `SESSION_DIR/planning/ARCHITECTURE_BRIEF.md` (concise, evidence-backed)
    - `SESSION_DIR/planning/ARCHITECTURE_BRIEF.json` (machine-readable anchors)
- Skill: `/at:architecture-brief`
  - Generates the brief without executing implementation work.
- Workflow integration:
  - `/at:run` now runs `solution-architect` **before** `action-planner`.
  - Per-task contexts embed the brief when present to keep implementor/tests aligned.

## Why this enforces patterns and constraints better

- Forces an explicit “north star” artifact in the session that can be:
  - referenced by the planner
  - embedded into each task context slice (without bloating the global context pack)
- Encourages evidence-backed decisions by requiring:
  - rule/doc anchors (paths or registry doc IDs)
  - repo pattern anchors (path + grep pattern)
- Keeps determinism:
  - no repo edits (session-only)
  - the brief is optional but becomes the default in `/at:run`

## Remaining Gaps / Follow-ups

- The planner is not yet *required* (by a deterministic gate) to incorporate brief anchors into tasks.
  - A future P0 improvement would be to validate that each code task includes at least one `context.code_pointers[]` or doc anchor derived from the brief for non-trivial changes.
- Multi-language repos may want per-task language identification so the architect and planner can pick language-specific verifications more precisely.

