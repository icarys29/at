# Previous Plugin Review → Optimization Opportunities (at)

- Date: 2026-02-01
- Previous plugin reference: `/home/dav/claude/claude-agent-team-plugin` (plugin version `0.7.42`, updated 2026-01-31)
- Current plugin: this repo (`at`, plugin version `0.1.0`)

## Executive Summary

The previous plugin’s most valuable differentiator is **project rules as first-class input to planning** and **deterministic architecture enforcement via a project-local enforcement runner**.

Current `at` is already strong on:
- session artifacts + strict plan validation
- file-scope enforcement hook
- always-on documentation maintenance + docs registry (v2)
- deterministic gates and evidence

Where current `at` is weaker than the previous plugin (and worth porting):
1) `.claude/rules/**` is not surfaced to the action planner (rules aren’t consistently applied by default).
2) Architecture enforcement is not “productized” (no standard boundary checker + config scaffold).
3) Version header bumping is referenced but missing as a tool, making upgrades less auditable.

## What the previous plugin did notably well

### 1) Rules in the context pack (planning gets invariants)

The previous plugin’s context pack builder explicitly included:
- `.claude/rules/at/global.md` (+ language rule packs)
- all `.claude/rules/project/*.md` files (user-owned invariants)

Impact: the planner consistently sees architecture/security/testing rules and can encode them into task acceptance criteria and file scopes.

### 2) Project-local enforcement runner + architecture boundary checker

The previous plugin supported:
- `.claude/at/enforcement.json` declaring checks with `mode` (fail/warn)
- `.claude/at/scripts/run_enforcements.py` executing checks deterministically
- `.claude/at/scripts/check_architecture_boundaries.py` enforcing import/dependency direction across python/go/typescript using a JSON config

Impact: this is **real architecture enforcement**, not just “document the architecture”.

### 3) Version bump script (auditability)

The previous plugin shipped `scripts/dev/add_version_headers.py`, which stamps:
- Python file headers (`Version:`/`Updated:`)
- agent/skill frontmatter (`version`/`updated`)

Impact: predictable release discipline and easier diffs across upgrades.

## Gaps in current `at` (compared to previous)

### GAP-A — Rules are not consistently injected into planning context

Current `scripts/context/build_context_pack.py` includes:
- request
- `.claude/project.yaml` (if present)
- `CLAUDE.md`
- docs registry summaries

But it does **not** include `.claude/rules/**`, so repo-specific invariants are easy to miss during planning.

### GAP-B — Enforcement exists only as a minimal “run commands” stub

Current `scripts/project_pack/install_project_pack.py` installs:
- `.claude/at/enforcement.json` (only simple shell commands)
- `.claude/at/scripts/run_enforcements.py` (only `command` checks)

No scaffold for boundary enforcement or a structured “check type” interface (python script + args + timeout + mode).

### GAP-C — Versioning discipline tool missing

Current `CLAUDE.md` recommends a version bump script, but the repo does not provide it.

## Recommendations (prioritized)

### P0 — Make principles enforceable by default (planning + execution)

1) **Include `.claude/rules/**` in the context pack**
   - Include at least: `.claude/rules/at/global.md` and any `.claude/rules/project/*.md` (bounded/truncated).
   - Optional: embed a short “Rules Summary” excerpt into per-task contexts to ensure implementors don’t miss invariants.

2) **Upgrade project pack to support architecture boundary enforcement**
   - Ship a portable `check_architecture_boundaries.py` and config scaffold `.claude/at/architecture_boundaries.json`.
   - Upgrade `run_enforcements.py` contract to support `python` checks with `script` + `args` + `timeout_ms`, plus `mode: fail|warn`.

### P1 — Make upgrades auditable

3) **Port a simplified `scripts/dev/add_version_headers.py`**
   - Stamp scripts + agents + skills consistently.
   - Keep current “Version: 0.1.0 / Updated: YYYY-MM-DD” discipline but automate it.

## Suggested integration path for current `at`

- Implement P0 items first (rules in planning + boundary enforcement scaffold).
- Wire enforcement results into the existing quality suite report with an actionable summary.
- Add the version bump utility after enforcement is stable.

