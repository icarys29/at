---
name: uninstall-hooks
description: Uninstall at-managed policy hooks from project scope (best-effort).
argument-hint: "[--scope project|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-hooks

## When to use
- You want to remove at-installed policy hooks from this project.

## Inputs / Outputs
- Inputs: `$ARGUMENTS`
- Outputs: updates `<project>/.claude/settings.local.json`

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/uninstall_policy_hooks.py" $ARGUMENTS`
