# CLAUDE.md — Agent Team (`at`) Claude Code plugin

This repo rebuilds the **Agent Team (`at`)** Claude Code plugin from scratch, based on the intent and operating model of the previous implementation.

## Purpose (what this plugin is)

`at` is a **workflow-kernel** for Claude Code: it turns a user request into a **repeatable, contract-driven session** with:
- deterministic session artifacts (plans, task outputs, reports)
- minimal, task-scoped context (context packs + per-task context slices)
- binary gates (plan validation, scope conformance, quality, compliance, docs)
- optional audit/policy hooks and persistent per-project learning/memory

The goal is **high UX + high reliability**: “done” means gates pass (or the workflow stops as blocked with actionable remediation).

## Non-negotiables (design invariants)

- **Sessions are first-class**: every run creates/resumes a `SESSION_DIR` and writes artifacts there.
- **Orchestrator does not modify repo code**: it only reads/writes under `SESSION_DIR`; all repo changes happen via subagents.
- **No nested subagents (Claude Code limitation)**: subagents **cannot** spawn other subagents; all orchestration/dispatch lives in `/at:run`.
- **Skills are injected, not invoked**: if a subagent needs “skill content”, attach it via the subagent frontmatter (`skills:`) so the full text is injected into its context.
- **Least context**: code-writing subagents must operate from **per-task context slices**, not repo-wide context dumps.
- **Fail-the-gate semantics**: if a gate fails, stop and report the exact remediation path.
- **Scope enforcement**: implement/test tasks declare `file_scope.writes[]`, and (when enabled) hooks enforce writes at tool-time.
- **Portable overlays**: per-repo specifics live in an overlay (e.g. `.claude/project.yaml`, `.claude/rules/**`, docs registry), not in plugin code.
- **Minimal dependencies**: prefer Python stdlib + small internal helpers; avoid heavy deps that reduce portability.

## Canonical workflows (expected UX)

All top-level commands are implemented as skills under `skills/*/SKILL.md` and exposed as `/at:<command>`.

- `/at:run` orchestrates the workflow (default `deliver`; also `triage`, `review`, `ideate`)
- `/at:init-project` bootstraps a repo overlay (config, rules, docs scaffolding)
- `/at:doctor` validates preconditions and can propose auto-remediation
- Session tools: `/at:sessions`, `/at:session-progress`, resume by session id/dir
- Controls: `/at:setup-policy-hooks`, `/at:setup-audit-hooks`, `/at:uninstall-hooks`, `/at:prune-audit-logs`
- Learning/memory: `/at:learning-status`, `/at:learning-update`, `/at:retrospective`

## Local reference library (templates + upstream conventions)

Use the repo’s reference library under `references/` to keep skills/agents/hooks aligned and DRY:

- Skill template: `references/skills-template.md`
- Agent template: `references/agents-template.md`
- Claude Code (plugins/skills/subagents/hooks): `references/claude-code/README.md`
- Hook implementation guidelines: `references/claude-code/hooks-guidelines.md`
- KISS/YAGNI/SRP/DRY: `references/claude-code/keep-it-simple.md`

## Repo layout (target structure)

Keep the repo structured so each concern is isolated and testable:

- `plugin.json`: plugin manifest (name/version/metadata)
- `hooks/hooks.json`: Claude Code hooks config (scope enforcement, audit, session lifecycle)
- `agents/*.md`: subagent definitions (frontmatter + instructions)
- `skills/*/SKILL.md`: command definitions (orchestrators, utilities, installers)
- `scripts/**/*.py`: deterministic implementation (session mgmt, context, validation, gates, learning, audit)
- `schemas/*.json`: schemas for `planning/actions.json`, `.claude/project.yaml`, and other artifacts
- `templates/**`: repo overlay templates (`project.yaml`, baseline rules, docs scaffolding, optional skills)
- `docs/**`: plugin docs (contracts, gates, configuration, troubleshooting)

## Versioning + headers (copy the previous plugin’s discipline)

The previous plugin enforced a strict versioning system to make upgrades/diffs auditable:

- One authoritative plugin version in `plugin.json`.
- A root `VERSION` file kept in sync.
- **Per-file version metadata**:
  - Python scripts begin with an `at:` docstring header including `Version:` and `Updated:`.
  - Agent/Skill markdown files include `version` and `updated` in frontmatter.

When you rebuild this repo’s implementation, keep the same discipline and add an automated “version bump” script early (the prior plugin used `scripts/dev/add_version_headers.py`) so updates are consistent.

### How to bump the plugin version (canonical)

1) Update `plugin.json` (`version`).
2) Update `VERSION` to match `plugin.json`.
3) Run `uv run scripts/dev/add_version_headers.py` to stamp `Version:`/`Updated:` across scripts and frontmatter (agents/skills).
4) Run a quick sanity check: `uv run python -m compileall -q scripts`.

## Determinism rules (how to write scripts)

- Prefer **explicit inputs/outputs** (paths, json/yaml) over implicit global state.
- Write machine-readable artifacts (`.json`) alongside human reports (`.md`).
- Do not require network access at runtime.
- Be strict about **path safety**: reject absolute paths / `..` traversal; ensure doc registry paths resolve under project root.
- Treat secrets carefully: respect `policies.forbid_secrets_globs` in config; never embed forbidden files into context artifacts.
- **Python scripts MUST be “self-sufficient uv/Astral scripts”** (invoked as `uv run ...` with dependencies declared/pinned) for:
  - One-command run (`uv run ...`) with dependencies handled automatically
  - Reproducible installs via lockfile/pinned deps
  - Faster dependency resolution/install than `pip` in many workflows
  - Cleaner automation/CI (less environment drift)
  - If a script has non-stdlib deps, declare them in the script metadata and pin versions (e.g. `package==1.2.3`).

## Local development expectations

- Run Claude Code with this plugin locally: `claude --plugin-dir .`
- Run Python scripts via `uv run ...` (even stdlib-only), so execution is consistent across automation and CI.
- Keep hook scripts fast and robust (they run frequently and must degrade gracefully).

## When modifying or adding capabilities

- Start with the user-facing contract (skill + docs) and only then add scripts/schemas.
- Prefer extending schemas + validators over adding “smart” heuristics in the orchestrator.
- If you add a new workflow phase or gate, also add:
  - a deterministic artifact contract (what it writes)
  - documentation in `docs/`
  - validation wiring (so failures are actionable)
