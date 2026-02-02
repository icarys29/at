# Agent Team (`at`) — Maintainer Guide (CLAUDE.md)

`at` is a corporate-grade workflow kernel for Claude Code. It turns a request into a **repeatable, contract-driven session** with:

- deterministic session artifacts (plans, task outputs, reports)
- minimal, task-scoped context (context pack + per-task context slices)
- binary gates (scope, quality, docs, compliance)
- optional hooks (policy enforcement, audit logging, UX nudges)

This document is for maintainers and contributors to the plugin itself.

## What “done” means

For deliver workflows, “done” means:
- tasks execute within declared file scope
- required verifications run and produce evidence
- gates pass (or the workflow stops as BLOCKED with an actionable remediation path)

## Design invariants (non‑negotiable)

- **Sessions are first-class**: every `/at:run` creates or resumes a `SESSION_DIR` and writes artifacts there.
- **Orchestrator does not modify repo code**: it reads/writes session artifacts only; repo edits happen via subagents.
- **No nested subagents**: subagents must not invoke other subagents; orchestration lives in `/at:run`.
- **Least context**: code-writing subagents operate on per-task context slices, not repo-wide dumps.
- **Fail-the-gate semantics**: if a gate fails, stop and report remediation (don’t paper over failures).
- **Scope enforcement**: code tasks must declare `file_scope.writes[]`; hooks can enforce writes at tool-time.
- **Overlay-owned config**: repo-specific policy/commands live under `.claude/` (project overlay), not in plugin code.
- **Determinism first**: scripts produce stable outputs; evidence is written as JSON + a concise MD summary.
- **No network required at runtime**: workflows must not depend on network availability.

## User-facing commands (public API)

All top-level commands are implemented as skills under `skills/*/SKILL.md` and exposed as `/at:<command>`.

Core workflows:
- `/at:run` — workflow kernel (`deliver|triage|review|ideate`)
- `/at:ideate` — structured ideation (session-only; no repo edits)
- `/at:brainstorm` — alias for ideation

Project setup and governance:
- `/at:init-project` — bootstrap `.claude/` overlay + docs scaffolding
- `/at:doctor` — validate repo overlay + prerequisites
- `/at:docs` — docs status/plan/sync/new/lint
- `/at:verify` — CI-friendly verify (quality + docs lint)

Operational tools:
- `/at:sessions`, `/at:session-progress`, `/at:session-diagnostics`, `/at:session-auditor`
- `/at:telemetry-session-kpis`, `/at:telemetry-rollup`

Hooks installers (opt-in):
- `/at:setup-policy-hooks`, `/at:setup-audit-hooks`, `/at:setup-docs-keeper-hooks`, `/at:setup-learning-hooks`, `/at:setup-ux-nudges-hooks`
- matching uninstall skills

## Repo layout (plugin source)

- `.claude-plugin/plugin.json` — Claude Code manifest (canonical)
- `plugin.json` — convenience manifest (kept in sync for local tooling)
- `VERSION` — convenience version file (must match manifest version)
- `hooks/` — default hooks config (plugin-scoped)
- `skills/` — user-invocable commands (`/at:*`)
- `agents/` — subagent definitions
- `scripts/` — deterministic implementation (sessions/context/validation/gates/docs/audit/learning)
- `schemas/` — JSON schemas for session artifacts
- `templates/` — overlay templates (project.yaml, docs templates, rules, language packs)
- `references/` — templates + condensed upstream conventions

## Versioning & change discipline (required)

Version sources (must stay consistent):
- `.claude-plugin/plugin.json` → `version` (authoritative)
- `plugin.json` → `version` (mirror)
- `VERSION` file (mirror)

Per-file version metadata:
- Python scripts: `Version:` + `Updated:` in the header docstring
- Agent/skill markdown: `version:` + `updated:` in YAML frontmatter

### How to bump version (canonical)

1) Update `.claude-plugin/plugin.json` (`version`) and `plugin.json` to match.
2) Update `VERSION` to match.
3) Run: `uv run scripts/dev/add_version_headers.py --include-templates`
4) Sanity check: `uv run python -m compileall -q scripts`

## Script authoring rules (determinism + safety)

- Prefer explicit inputs/outputs; avoid implicit global state.
- Emit JSON (machine) + MD (human) artifacts.
- Enforce path safety (no `..`, no absolute paths escaping the project root).
- Respect `policies.forbid_secrets_globs` and never embed forbidden files in context artifacts.
- Keep hooks fast and fail-open unless they are explicitly a guardrail (policy/scope).

## Local development

- Run Claude Code with this plugin: `claude --plugin-dir .`
- Run Python scripts via `uv run ...` (even stdlib-only) for reproducibility.
- Keep skill/agent markdown concise (≤ 500 lines); move long material into `references/` or `skills/<id>/references/`.
