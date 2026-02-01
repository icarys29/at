# P0 — Foundations

## Outcome

Establish the smallest possible repo skeleton and contracts so we can build the kernel without rework:
- canonical repo structure
- canonical schemas + shared libs
- canonical naming decisions (docs registry, hooks strategy)
- minimal docs for contributors and future automation

## References (read first; keep context lean)

- Template: `references/skills-template.md`
- Template: `references/agents-template.md`
- Claude Code: `references/claude-code/plugins.md`
- Claude Code: `references/claude-code/keep-it-simple.md`
- Claude Code: `references/claude-code/memory-and-rules.md` (for overlay rules strategy)

## Scope (include)

- `plugin.json` (manifest skeleton)
- directory layout: `agents/`, `skills/`, `scripts/`, `schemas/`, `hooks/`, `templates/`, `docs/`, `references/`, `plan/`
- shared Python libs (`scripts/lib/*`) used by all later scripts
- core schemas (at minimum `schemas/actions.schema.json`)
- contributor docs: `CLAUDE.md` (canonical), `README.md`

## Non-goals (exclude)

- No full workflow orchestration yet (that’s P1).
- No audit/learning/telemetry subsystems (P3).
- No CI setup unless needed for deterministic checks.

## Work Items (can be parallelized)

### P0-01 Repo skeleton + manifest

Deliverables:
- `plugin.json` (name `at`, version `0.1.0` or similar)
- empty folders created with placeholder files where needed (so Claude Code loads the plugin)

Acceptance:
- Claude Code can load the plugin directory without errors.
- `plugin.json` follows `references/claude-code/plugins.md` (default layout; `paths.*` start with `./` if used).

### P0-02 Canonical contracts (schemas)

Deliverables:
- `schemas/actions.schema.json` (plan contract; include `parallel_execution` support)
- (optional now, required by P1) `schemas/task_artifact.schema.json` for per-task YAML artifacts

Acceptance:
- Schema files are consistent with the intended kernel contract (see `plan/audit/previous_plugin_lessons_report.md`).

### P0-03 Shared libs (DRY foundation)

Deliverables (stdlib-only):
- `scripts/lib/simple_yaml.py` (minimal YAML for `.claude/project.yaml`)
- `scripts/lib/path_policy.py` (safe repo-relative path normalization + forbid-globs)
- `scripts/lib/io.py` (read/write helpers, timestamps)
- `scripts/lib/project.py` (detect project dir, load config)

Acceptance:
- Each lib has one responsibility and is used by later scripts (avoid future duplication).

### P0-04 Templates

Deliverables:
- `templates/project.yaml` (overlay template; defaults include parallel execution enabled)
- baseline rule templates (if any) under `templates/rules/` (designed for `.claude/rules/**`; prefer small, composable rule files; use `@imports` when helpful)
- docs scaffolding template for `docs/DOCUMENTATION_REGISTRY.json`

Acceptance:
- Template paths and names match the simplification decisions (one docs registry).

### P0-05 Versioning discipline

Deliverables:
- `VERSION`
- (optional early) `scripts/dev/add_version_headers.py` to stamp version metadata consistently

Acceptance:
- Clear “how to bump versions” process documented in `CLAUDE.md`.

### P0-06 References library (templates + upstream conventions)

Deliverables:
- `references/skills-template.md` and `references/agents-template.md`
- `references/claude-code/*` (paraphrased upstream docs for plugins/skills/subagents/hooks/memory)
- `references/debugging/*` (methodology for future triage/root-cause work)

Acceptance:
- Action plans and implementation work consistently reference these templates instead of inventing new formats.

## Exit Criteria

- Repo has a stable skeleton + canonical schemas + shared libs.
- Decisions from `plan/phases/README.md` are reflected in templates and docs.
