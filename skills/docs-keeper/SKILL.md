---
name: docs-keeper
version: "0.5.0"
updated: "2026-02-02"
description: >
  Corporate-grade Documentation Keeper: plan/sync/new/lint via the docs-keeper subagent.
argument-hint: "[plan|sync|lint|new <type>] [--session <id|dir>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:docs-keeper

This is the deterministic control surface for documentation maintenance. It delegates all documentation edits to the `docs-keeper` subagent.

## Subcommands

- `plan [--session <id|dir>]`
  - Compute the deterministic docs plan (no repo edits).
- `lint`
  - Run docs lint only (no repo edits).
- `new <type>`
  - Create a new doc from templates and register it (edits via subagent).
  - `<type>` must be one of: `context|architecture|adr|ard|pattern|runbook`
- `sync [--session <id|dir>]`
  - Apply plan: update/create docs + update registry + regenerate registry MD + run lint.

## Procedure

1) Resolve `SESSION_DIR`:
   - If `--session` provided, use it.
   - Otherwise use the most recent session under `workflow.sessions_dir` (default `.session/`).
2) Delegate:
   - Task: `docs-keeper`
   - Provide mode + args + `SESSION_DIR` in the task input.

