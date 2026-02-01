---
status: stable
last_updated: 2026-02-01
---

# References

This directory contains **non-auto-loaded** reference material used by agents and skills on-demand.

## Directories

| Directory | Purpose |
|----------|---------|
| `debugging/` | Systematic debugging methodology and techniques |
| `claude-code/` | Condensed notes from Anthropic’s official Claude Code documentation (plugins, skills, subagents, hooks, memory/rules) |
| `anthropic-api/` | Condensed notes from Anthropic’s official API documentation (Messages API, auth, errors) |
| `agents-template.md` | Consistent subagent definition template (frontmatter + body) |
| `skills-template.md` | Consistent skill/command definition template (frontmatter + body) |

## Usage

These references are not automatically loaded into context. Agents should read them only when relevant, e.g.:

```markdown
If you need to add a new plugin command, follow the official conventions
(see `references/claude-code/plugins.md` and `references/claude-code/skills.md`).
```
