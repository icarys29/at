---
name: docs-keeper
version: "0.4.0"
updated: "2026-02-02"
description: >
  Corporate-grade Documentation Keeper: plan/sync/new/lint via the docs-keeper subagent.
argument-hint: "[plan|sync|lint|new <type>] [--session <id|dir>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /docs-keeper

Project-local docs keeper skill. Delegates all documentation edits to the `docs-keeper` subagent.

## Subcommands

- `plan [--session <id|dir>]`: compute deterministic plan (no edits)
- `lint`: run docs lint only (no edits)
- `new <type>`: create doc from templates and register it
- `sync [--session <id|dir>]`: update/create docs + update registry + regenerate registry MD + run lint

## Procedure

1) Resolve `SESSION_DIR` (use the most recent under `workflow.sessions_dir` if not provided).
2) Task: `docs-keeper` with the chosen mode and `SESSION_DIR`.

