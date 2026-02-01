---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/memory
---

# Memory & Rules (Claude Code)

## “Memory” sources (conceptual)

Claude Code can load durable instructions from multiple sources, including:
- User memory (`~/.claude/CLAUDE.md`)
- Project memory (`CLAUDE.md` at the project root, and project-local variants)
- Conditional rules (`.claude/rules/**/*.md`)

Exact precedence can change over time; prefer the official doc if behavior seems surprising.

## `CLAUDE.md` and `@imports`

You can split large instruction files using `@imports` lines that include other files. Notable constraints:
- Imports are not evaluated inside code spans or code blocks
- There is a maximum import depth (to avoid recursion)

## `.claude/rules` (modular, enforceable rules)

Rules are Markdown files under `.claude/rules`. They are useful for:
- Keeping top-level memory/instructions short
- Applying rules to specific file globs (via frontmatter like `paths`)

## Best practices (KISS/DRY)

- Prefer small, composable rule files over one huge instruction document.
- Use `@imports` to keep content DRY while still readable.
- Keep rules concrete and testable (avoid vague style-only guidance that can’t be checked).
