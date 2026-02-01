# Phased Rebuild Plan (at)

This folder contains the step-by-step rebuild plan for the Agent Team (`at`) Claude Code plugin.

Source analysis + inventories:
- `plan/audit/previous_plugin_lessons_report.md`
- `plan/audit/previous_plugin_keep_drop_matrix.json`

Local reference library:
- `references/` (templates + Claude Code condensed docs + debugging methodology)

Requirements:
- `plan/requirements/README.md`

## Phases

- **P0 — Foundations**: repo skeleton, schemas/contracts, shared libs, versioning discipline, minimal docs.
- **P1 — Kernel**: sessions + planning contract + context pack + task contexts + core agents + core hooks.
- **P2 — Gates**: deterministic gates (plan adherence, parallel conformance, quality suite, compliance, docs) + rollback + policy hooks.
- **P3 — Advanced**: audit hooks + analytics, learning/memory, telemetry KPIs, project packs/enforcement, upgrade/import utilities.

## Default Parallelization (MANDATORY)

In the rebuilt plugin, **parallel execution is ON by default** for code tasks:
- `planning/actions.json` must include `parallel_execution.enabled=true` unless the planner *explicitly* disables it.
- When `parallel_execution.enabled=true`, every `implementor` / `tests-builder` task **must** declare `file_scope.writes[]`.
- Within a parallel group, `file_scope.writes[]` must not overlap across tasks.

This is a core UX feature: most work can be safely parallelized when write scopes are explicit and enforced.

## Template Compliance (MANDATORY)

All build work must follow the repo templates and upstream Claude Code conventions:

- **Agents**: follow `references/agents-template.md`
  - Keep frontmatter minimal; restrict tool access.
  - In this repo, include plugin version metadata (`version`, `updated`) once the versioning system exists.
  - Keep agent files short (target ≤ 500 lines); move long material to `references/` or skill `references/`.
- **Skills**: follow `references/skills-template.md`
  - Keep `skills/<id>/SKILL.md` short (target ≤ 500 lines).
  - Put long specs in `skills/<id>/references/` and load them on-demand.
  - Prefer stable command names; treat names as API surface area.
- **Hooks**: follow `references/claude-code/hooks-guidelines.md`
  - Keep hooks fast and deterministic.
  - Prefer enforcing invariants (scope/schema/artifacts) over “doing work”.
  - Remember component-scoped hooks limitations:
    - agents/skills: only `PreToolUse`, `PostToolUse`, `Stop`
    - use plugin/global hooks for `SubagentStop`, `SessionStart`, etc.
- **Plugin manifest**: follow `references/claude-code/plugins.md`
  - Keep default directory layout unless there is a concrete reason.
  - If using custom `paths.*` in `plugin.json`, entries must start with `./` and are relative to plugin root.

## Simplification Decisions (apply throughout)

- **Python-only core**: avoid Node-based hooks in v1; rewrite optional UX hooks in Python if we keep them.
- **One docs registry name**: standardize on `docs/DOCUMENTATION_REGISTRY.json` (and eliminate `docs/REGISTRY.json` drift).
- **One schema per artifact**: schemas + validators are the single source of truth.
- **Consolidate duplicate commands**: keep one canonical name and treat the other as an alias (e.g., `setup-policy-hooks` vs `policy-hooks-deployer`).
