# Documentation System Audit Report (at)

- Date: 2026-02-01
- Scope: documentation system as implemented in this repo (registry, docs-keeper, rules, gates, context embedding)
- Primary goal: ensure sub-agents receive the right documentation context automatically, while preventing drift and remaining safe/predictable for team use.

## Executive Summary

The system is directionally strong: the registry is authoritative, generated artifacts are deterministic, drift is gate-enforced, and planning-time enforcement ensures `doc_ids` are selected (with a deterministic floor via coverage rules). This is a good foundation for “docs as part of delivery”.

However, there is a critical integration flaw: **file-scope enforcement can block docs-keeper from editing repo docs** (or push it into Bash-based edits), which undermines the promise of always-on documentation maintenance. Fixing that should be the top priority.

Second, several “deterministic” checks are currently *opaque* (they report only counts). This will cost teams time and erode trust even if the system is correct.

## Current Architecture (as implemented)

### 1) Registry (source of truth)

- `docs/DOCUMENTATION_REGISTRY.json` (v2): doc types, templates, docs, and coverage rules.
- `docs/DOCUMENTATION_REGISTRY.md`: generated view from JSON (`scripts/docs/generate_registry_md.py`), drift-checked.

### 2) Deterministic rule evaluation (planning + delivery)

- Coverage rules engine: `scripts/docs/coverage_rules.py`
  - Legacy rules: `match` + `actions`
  - Advanced rules: `priority` + `match_any` groups with optional keyword predicates
- Planning-time enforcement: `scripts/validate/actions_validator.py`
  - For each code task, coverage rules are evaluated using planned `file_scope.writes[]` plus task summary text.
  - Required doc ids must be present in `task.context.doc_ids[]` when `docs.require_registry=true`.

### 3) Docs planning + linting (deterministic artifacts)

- `scripts/docs/docs_plan.py`: uses task artifacts + planning summaries to compute required docs/types; writes `SESSION_DIR/documentation/docs_plan.{json,md}`.
- `scripts/docs/docs_lint.py`: validates registry, drift, orphans, and broken links.
- `scripts/validate/docs_gate.py`: writes session-backed docs gate artifacts under `SESSION_DIR/documentation/`.

### 4) Context embedding (for subagents)

- `scripts/context/build_context_pack.py`: includes registry summary and coverage rule summary (for planner).
- `scripts/context/build_task_contexts.py`: embeds selected docs (by `doc_ids`) into each code task context (with optional `doc_sections`).

### 5) Automation (hooks + deliver wiring)

- Drift warning (non-blocking): `scripts/hooks/docs_post_task_drift.py`
- Pre-commit/PR gate (blocking): `scripts/hooks/docs_pre_commit_gate.py` → runs `docs_lint.py`

## Strengths (what’s working well)

- Deterministic registry and deterministic generated Markdown view prevent “silent drift”.
- Docs enforcement is integrated into the plan contract: tasks can’t proceed without required doc ids when registry is required.
- Per-task context embedding is explicit and bounded by `doc_ids` (with optional section extraction), enabling least-context-by-default.
- The system is mostly language-agnostic: rules are path/keyword driven and registry defines the taxonomy and templates.

## Findings (prioritized)

### DOCSYS-01 (Critical) — Docs-keeper edits can be blocked by file-scope enforcement

Today, the `PreToolUse` scope hook (`scripts/hooks/enforce_file_scope.py`) authorizes repo edits only when it can map the edit to a task listed in `SESSION_DIR/inputs/task_context_manifest.json`. That manifest is generated from `planning/actions.json` tasks and currently covers only `implementor`/`tests-builder` tasks.

Docs-keeper is executed as a workflow step but is not represented as a planned task with declared write scopes, so edits under `docs/` are likely to be denied (or force a “Bash redirect” workaround).

**Impact:** docs automation becomes unreliable and/or less safe, directly harming both drift prevention and context quality.

### DOCSYS-02 (High) — Lint/gate outputs lack actionable details

Orphan docs and broken links are surfaced as counts. Teams need “first N examples” to fix quickly and to trust the system.

### DOCSYS-03 (High) — Keyword matching is naive substring matching

The keyword system is valuable, but substring matching (`"auth"` matching `"author"`) can produce surprising enforcement failures. This is solvable deterministically with tokenization/word-boundary logic.

### DOCSYS-04 (Medium) — Requirements report can diverge from enforcement

`docs_requirements_for_plan.py` is helpful, but it currently does not incorporate the same keyword-derived signals used in enforcement, so it can mislead the planner.

### DOCSYS-05 (Medium) — No deterministic ID allocation for new docs

Agent guidance says “allocate deterministic IDs”, but there is no deterministic helper to do so. This becomes a real issue with parallelism and team usage.

### DOCSYS-06 (Medium) — Drift warning hook may be noisy during deliver

Warning occurs on SubagentStop, often before docs-keeper runs, which trains engineers to ignore it.

### DOCSYS-07 (Low) — Embedded docs can crowd out context

Defaults for `doc_sections` are human-driven (planner). A deterministic or recommended default for Tier 1/2 docs would reduce token bloat.

## Recommended Improvements (roadmap)

### P0 — Reliability (must fix)

1) Make docs-keeper edits first-class in scope enforcement
   - Add a planned docs task (owner `docs-keeper`) with strict `file_scope.writes` for:
     - `docs/`
     - `docs/DOCUMENTATION_REGISTRY.json`
     - `docs/DOCUMENTATION_REGISTRY.md`
   - Ensure `build_task_contexts.py` emits a context + manifest entry for that task so `enforce_file_scope.py` authorizes it deterministically.

2) Make lint/gate outputs actionable
   - Include lists (first N) for broken links and orphan docs in JSON + MD outputs.

### P1 — Trust and usability

3) Improve keyword matching deterministically
   - Word-boundary or token-based phrase matching (still offline/deterministic).
   - Add “why required” context in validation errors (matched_keywords + matched_paths excerpt).

4) Align docs_requirements_for_plan with enforcement
   - Same keyword text input + include triggered rules and matched keywords.

5) Add deterministic ID allocator
   - Script `scripts/docs/allocate_doc_id.py` that:
     - reads registry
     - finds next suffix per prefix (`ADR-####`, etc.)
     - optionally reserves it in registry to avoid collisions.

### P2 — Context quality (agent performance)

6) Deterministic “recommended docs” (beyond required floor)
   - Provide a deterministic ranking using doc `when` + tags vs task summary text, emitting suggestions for planner (non-binding).
   - Keep conservative defaults to avoid bloat (recommend 1–3 docs).

7) Defaults for doc section embedding
   - Encourage / default to `doc_sections` for Tier 1/2 docs to keep contexts short.

## Conclusion

The system is close to “corporate-grade”: deterministic registry + drift enforcement + plan-time doc selection is exactly the right shape. The critical missing piece is **making docs-keeper compatible with scope enforcement** without relying on Bash escape hatches. Once addressed, the rest of the improvements focus on making the system more transparent and less surprising for teams.

