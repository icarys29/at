---
status: stable
last_updated: 2026-01-31
sources:
  - https://code.claude.com/docs/en/skills
  - https://code.claude.com/docs/en/sub-agents
  - https://code.claude.com/docs/en/hooks
---

# Keep It Simple (KISS/YAGNI/SRP/DRY) for Claude Code Extensions

This is a small synthesis of official Claude Code best practices, organized around maintainability principles.

## KISS

- Prefer default layouts and conventions (plugin directories, `skills/`, `agents/`, `hooks/`).
- Keep skills and prompts short; move deep detail into references that can be loaded on-demand.
- Keep hooks fast; hooks should enforce invariants, not implement features.

## YAGNI

- Don’t add new commands/subagents/hooks without a concrete, repeatable gap (and an example showing current behavior fails).
- Prefer extending existing agents/skills over creating new ones.

## SRP

- Subagents should be single-purpose with explicit inputs/outputs.
- Orchestrators orchestrate; implementors implement; validators validate.

## DRY

- Avoid copy/pasting long prompt blocks across skills/agents; extract shared instructions into reference files or rule imports.
- Centralize shared scripts/utilities rather than re-implementing logic per-skill.
