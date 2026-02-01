---
name: setup-policy-hooks
description: Install at policy hooks into project scope (secrets + destructive command blocking, plus scope/contract enforcement).
argument-hint: "[--scope project|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:setup-policy-hooks

## When to use
- You want opt-in safety hooks in the current project.

## Inputs / Outputs
- Inputs: `$ARGUMENTS`
- Outputs: updates `<project>/.claude/settings.local.json`

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/install_policy_hooks.py" $ARGUMENTS`
2) Verify: `.claude/settings.local.json` contains `hooks.PreToolUse` entries managed by `at-policy-hooks`.
