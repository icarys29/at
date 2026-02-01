---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/slash-commands
---

# Skills / Commands (Claude Code)

## What skills are

Skills are reusable, written instructions exposed as slash commands (e.g. `/foo`). They are stored as Markdown files and can accept arguments.

## Where skills live

Recommended locations:
- Project: `.claude/skills/<skill-name>/SKILL.md`
- Personal: `~/.claude/skills/<skill-name>/SKILL.md`
- Plugin: `<plugin>/skills/<skill-name>/SKILL.md`

Legacy compatibility:
- `.claude/commands/<command>.md` still works and supports the same frontmatter.
- If a legacy command and a skill share the same name, the skill takes precedence.
- Plugin-provided items can be namespaced to avoid conflicts.

## Skill format (high-level)

Skills are Markdown with a YAML frontmatter block that can define:
- `description` (used in discovery/help)
- `argument-hint` (shown in autocomplete/help)
- `allowed-tools` (tool allowlist while running the skill; can be granular for `Bash(...)`)
- `model` (override model for the skill)
- `user-invocable` / `disable-model-invocation` (discoverability / routing controls)
- `context: fork` + `agent: <subagent>` (run the command in a forked subagent context)
- `hooks` (component-scoped hooks for the skill run; event support is limited)

Skill bodies often use `$ARGUMENTS` to include user-provided arguments in a consistent place.

## Best practices (from official docs; mapped to KISS)

- Keep skills concise and focused.
- Keep the main skill file short (push long material into `references/` and load on demand).
- Move long reference material into separate files and have the skill instruct the model to read them on-demand.
- Prefer stable interfaces (skill names and argument conventions) once teammates rely on them.
