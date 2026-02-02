---
name: uninstall-hooks
version: "0.4.0"
updated: "2026-02-02"
description: Uninstall at-managed policy hooks from project/team/user settings (best-effort).
argument-hint: "[--scope project|team|user] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:uninstall-hooks

## When to use
- You want to remove at-installed policy hooks from this project.

## Inputs / Outputs
- Inputs: `$ARGUMENTS`
- Outputs: updates the selected settings file

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/uninstall_policy_hooks.py" $ARGUMENTS`
