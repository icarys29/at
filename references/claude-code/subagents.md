---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/sub-agents
---

# Subagents (Claude Code)

## What subagents are

Subagents are specialized assistants with:
- Their own system prompt
- Their own tool allow/deny configuration
- Their own context window (separate from the main thread)

They’re useful to run focused work (e.g., investigation, refactors, test-writing) without polluting the main agent’s context.

## Where subagents live (discovery precedence)

Common locations include:
- Project: `.claude/agents`
- User: `~/.claude/agents`

(Plugins can also ship subagents via their own `agents/` directory.)

## Subagent file format (high-level)

Subagents are Markdown with YAML frontmatter fields such as:
- `name`, `description`
- `model`
- `tools` and/or `disallowedTools` (which tools the agent can use)
- `permissionMode` (how edits are handled, if applicable)
- Optional: `skills`, `hooks`

## Best practices (official guidance)

- Make subagents **focused** with a single, clear responsibility.
- Write a **detailed description** so the orchestrator knows when to use the subagent.
- **Limit tool access** to what the subagent truly needs.
- Check subagents into version control so teams share behavior consistently.

## Chaining & nesting (important constraint)

- **Subagents cannot spawn other subagents** (no “nested” delegation). If you need multiple subagents, chain them from the main orchestrator skill.

## Skills in subagents

- Subagents don’t inherit skills from the parent conversation.
- If a subagent needs skill content, preload it via frontmatter (`skills:`). The full skill text is injected into the subagent context (not “called” dynamically).
