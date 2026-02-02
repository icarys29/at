---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/sub-agents
---

# Claude Code Subagent Template (consistent agent definition)

Subagents are specialized assistants with their own tool access and system prompt.

## Locations

- Project: `.claude/agents/<agent-name>.md`
- Personal: `~/.claude/agents/<agent-name>.md`
- Plugin: `agents/<agent-name>.md`

## Frontmatter template (Claude Code-supported + plugin conventions)

Keep it minimal. If you are editing **this plugin** (`at`), include `version` and `updated` as required by `CLAUDE.md`.

```yaml
---
# required / strongly recommended
name: <kebab-case-agent-name>
description: <1–2 lines: when to use this agent>
model: sonnet
tools: Read, Write, Edit, Grep, Glob, Bash

# optional (Claude Code)
disallowedTools: Task
permissionMode: acceptEdits
skills: skill-a, skill-b
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "uv run \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/enforce_file_scope.py\""
          timeout: 10

# plugin-specific (required in this repo)
version: "0.3.1"
updated: "2026-02-02 00:00:00"
---
```

## Body template (ultra clear)

```md
# <Agent Name>

## Mission
<One sentence: the single job this agent does (SRP).>

## When to use
- <trigger 1>
- <trigger 2>

## When NOT to use
- <non-goal 1>

## Inputs (expected)
- <file paths / session artifacts / IDs the orchestrator provides>

## Outputs (required)
- <exact artifacts to write + where>
- <final report format: bullets / YAML / JSON>

## Hard boundaries
- <file-scope constraints>
- <no-delegation constraints>
- <what tools to avoid unless explicitly necessary>

## Procedure
1) Read inputs.
2) Do the work.
3) Validate: <tests/lint/schema checks>.
4) Report: <what you changed + evidence>.
```
