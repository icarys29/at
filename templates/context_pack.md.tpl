# Context Pack (at)

Generated for session: `${SESSION_ID}`

## Request

@import ${SESSION_DIR}/inputs/request.md

## Project Configuration

@import .claude/project.yaml

## Project Instructions

@import CLAUDE.md

## Rules (always-on)

These are repo-specific invariants. The action planner must reflect them in task breakdown, file scopes, and acceptance criteria.

@import .claude/rules/at/global.md
@import .claude/rules/project/*.md

## Language Rules

@import .claude/rules/at/lang/${PRIMARY_LANGUAGE}.md

## Documentation Registry (summary)

The docs registry defines which documentation exists and when to include it in task contexts.

@import docs/DOCUMENTATION_REGISTRY.json

## Usage Notes

- Use `doc_ids[]` from the registry to select documentation for task contexts
- Respect `when` field to determine relevance
- Prefer tier 1-2 docs for most tasks
- Include tier 3+ only when specifically relevant
