# Requirements (at)

This folder contains long-lived requirements artifacts for the rebuild:

- Capability checklist: `plan/requirements/CAPABILITY_TABLES.md`
- User stories: `plan/requirements/USER_STORIES.md`

These documents are designed to stay stable as the repo evolves and to serve as:
- a build checklist (what must exist + how to verify it)
- a traceability reference (user stories → capabilities → implementation)

Progress tracking:
- Mark completed capability rows as `[x]` in `plan/requirements/CAPABILITY_TABLES.md`.
- Maintain per-story `Status:` in `plan/requirements/USER_STORIES.md` (Not started / In progress / Done).

## Templates / Conventions

When implementing skills/agents/hooks referenced by these requirements, follow:
- Skill template: `references/skills-template.md`
- Agent template: `references/agents-template.md`
- Hook guidelines: `references/claude-code/hooks-guidelines.md`
