---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/hooks-reference
---

# Hooks (Claude Code)

## What hooks are

Hooks run user-defined commands at well-defined lifecycle moments (e.g. before/after tool use). They are commonly used for:
- Enforcing policy (file scope, schema checks)
- Fast validation (lint, formatting gates)
- Capture/telemetry (careful: sensitive)

## Where hooks are configured

Hooks can be configured from multiple scopes, including:
- User/project settings (`~/.claude/settings.json`, `<project>/.claude/settings.json`, `<project>/.claude/settings.local.json`)
- Plugin hooks (via the plugin manifest’s `hooks` field, usually pointing at `hooks/hooks.json`)
- Component-scoped hooks in skill/agent frontmatter (limited event support)

## Events (overview)

See the official hooks reference for the complete list. Commonly used events include:
- `PreToolUse`, `PostToolUse`, `PostToolUseFailure`
- `PermissionRequest`
- `SessionStart`, `SessionEnd`
- `Stop`, `SubagentStop`

## Matchers (high-level)

Matchers are supported for some events (not all). Commonly, matchers are used to scope tool-related hooks to specific tools like `Write` / `Edit` / `Bash`.

## Safety / best practices (KISS + security)

- Hooks execute arbitrary commands: keep them fast and deterministic.
- Prefer hooks that **enforce invariants** rather than hooks that “do work”.
- Treat hook inputs/paths as untrusted: quote variables and avoid shell injection hazards.
