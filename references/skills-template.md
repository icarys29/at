---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/slash-commands
---

# Claude Code Skills (template)

Skills extend Claude Code and also create **custom slash commands** (e.g. `/review`). Existing `.claude/commands/*.md` files keep working, but skills add supporting-file folders + more configuration.

## Folder layout

Create a skill as a folder containing `SKILL.md`:

- Project: `.claude/skills/<skill-id>/SKILL.md`
- Personal: `~/.claude/skills/<skill-id>/SKILL.md`
- Plugin: `skills/<skill-id>/SKILL.md`

Suggested structure:

```
<skill-id>/
  SKILL.md
  references/   # long docs/specs (load only when needed)
  templates/    # markdown/json templates the skill can reuse
  scripts/      # helper scripts (bash/python/node)
```

## SKILL.md frontmatter (Claude Code-supported)

Keep frontmatter minimal. Optional fields below are only the ones Claude Code documents.

```yaml
---
# required (or defaults from folder name)
name: <kebab-case-skill-name>      # becomes /<name>; if omitted, uses <skill-id> folder name
description: >                     # used for discovery + routing; keep high-signal
  <what it does>. Use when <specific triggers>.

# optional
argument-hint: "[--flag] <arg>"    # shown in help/autocomplete
disable-model-invocation: false    # true = only invoked manually (not automatically)
user-invocable: true              # show in /help; allow manual invocation
allowed-tools: Read, Grep, Glob    # restrict tools while the skill runs
model: sonnet                      # override model for this skill
context: fork                      # run the skill in a forked subagent context
agent: <subagent-name>             # which subagent to use when context: fork
hooks:                             # hook overrides for the skill run (advanced)
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "uv run scripts/hooks/enforce_file_scope.py"
          timeout: 10
---
```

## SKILL.md body template (ultra concise)

```md
# <Skill Name>

## When to use
- <trigger 1>
- <trigger 2>

## When NOT to use
- <non-goal 1>

## Inputs / Outputs
- Inputs: <bullets>
- Outputs: <exact format / artifacts>

## Procedure
1) <step 1>
2) <step 2>
3) Validate: <how to confirm success>
4) Report: <what to return>

## Optional resources (load only if needed)
- Reference: `references/<doc>.md`
- Template: `templates/<x>.md`
- Script: `scripts/<x>.py`
```

## Notes

- Prefer short skills; push deep detail to `references/` and read it only when needed.
- Use `$ARGUMENTS` (all args) and `${CLAUDE_SESSION_ID}` (current session id) when helpful.
- If `$ARGUMENTS` is not present, Claude Code appends arguments as `ARGUMENTS: <value>`.
