# Audit — Language Packs (P0→P2)

Date: 2026-02-01

## Objective

Restore and improve **language-specific guidance/constraints** (as the previous plugin did) in a way that is:
- easy to use (predictable defaults)
- easy to maintain (data-driven)
- easy to extend to new languages
- safe (no surprising toolchain assumptions)

## Findings (before this change)

- Language guidance was primarily **embedded in agent definitions** and/or absent in per-task contexts, making it harder to:
  - keep guidance consistent across agents
  - add languages without editing agent prompts
  - present deterministic verification defaults to the planner
- Quality gates were deterministic, but “what to run” relied heavily on project config and did not have a portable fallback.

## Implemented Architecture

### Layer A — Language Rules (human-readable, embedded)

- Source templates: `templates/rules/at/lang/<lang>.md`
- Installed into projects: `.claude/rules/at/lang/<lang>.md`
- Usage:
  - included in `SESSION_DIR/inputs/context_pack.md` (rules section)
  - embedded into each per-task context slice (limited to 2 primary languages to control bloat)

### Layer B — Language Packs (structured, deterministic metadata)

- Source templates: `templates/languages/<lang>/pack.json`
- Installed into projects: `.claude/at/languages/<lang>.json`
- Usage:
  - summarized in `SESSION_DIR/inputs/context_pack.md` (“Language Packs (summary)”)
  - provides deterministic “suggested verifications” as planner hints
  - optional quality-suite defaults (opt-in)

### Installation UX

- New skill: `skills/install-language-pack/SKILL.md` (`/at:install-language-pack`)
- Deterministic installer: `scripts/languages/install_language_pack.py`
- Bootstrap behavior:
  - `scripts/init_project.py` installs language packs for `.claude/project.yaml: project.primary_languages[]`
  - default bootstrap installs `python` if `primary_languages` is missing/empty

## Enforcement + Determinism Decisions

- No automatic mutation of `.claude/project.yaml`.
- Language pack “suggested quality suite” commands are **hints** and are not auto-executed unless:
  - a task explicitly references them as a verification, or
  - the quality suite enables `commands.allow_language_pack_defaults=true` (off by default).

## Benefits (value added)

- Adds language-specific constraints without locking them into agent prompt text.
- Keeps planning deterministic by surfacing suggested verifications in the context pack.
- Enables future language onboarding by adding a new `templates/languages/<lang>/pack.json` + `templates/rules/at/lang/<lang>.md` (no agent edits required).
- Improves maintainability: language evolution happens in one place (pack + rules), not across multiple agents.

## Risks / Potential Flaws

- Packs cannot guarantee tool availability; commands may fail if the repo doesn’t use the suggested toolchain.
  - Mitigation: pack defaults are opt-in (`commands.allow_language_pack_defaults=false` by default).
- Multi-language repos may want per-task language selection rather than “top 1–2 primary languages”.
  - Current behavior is intentionally conservative to avoid context bloat and unpredictable inference.

## P0/P1/P2 Recommendations Status

- P0 — Per-language rules templates + embed into per-task contexts: DONE
- P1 — `pack.json` templates + deterministic installer + init-project bootstrap: DONE
- P2 — Deterministic “verification defaults” surfaced to planner + optional quality defaults (opt-in): DONE

## Suggested Next Improvements (post P0→P2)

- Add a `task.language` field to `planning/actions.json` (or infer from `file_scope.writes[]`) to select the correct language rules/verification hints per task.
- Add pack schema validation (minimal) to ensure installed packs remain compliant.
- Expand curated packs (e.g., Java/Kotlin, C#, Ruby) as needed with the same mechanism.

