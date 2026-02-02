---
name: docs
version: "0.5.0"
updated: "2026-02-02"
description: >
  Unified docs entry point: status/plan/sync/new/lint. Wraps docs-keeper (for edits) plus deterministic scripts.
argument-hint: "[status|plan|sync|new <type>|lint] [--session <id|dir>] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:docs

Single umbrella command for documentation workflows:
- Deterministic scripts do lint/plan (no repo edits)
- `docs-keeper` subagent performs docs edits (minimal, registry-driven)

## Commands

- `status` (default)
  - Registry health overview (no edits).
- `lint`
  - Run docs lint (registry + consistency checks; no edits).
- `plan [--session <id|dir>]`
  - Compute a deterministic docs plan for a session (no edits).
- `sync [--session <id|dir>]`
  - Apply plan: update/create docs + update registry + regenerate registry MD + run lint (edits via `docs-keeper`).
- `new <type> [--session <id|dir>]`
  - Create a new doc from templates and register it (edits via `docs-keeper`).
  - `<type>` must be one of: `context|architecture|adr|ard|pattern|runbook`

## Procedure

1) Parse the first token of `$ARGUMENTS` as `CMD`:
   - If missing: `CMD=status`
2) Branch:

### `status`

Read the documentation registry and report health:
- Read `docs/DOCUMENTATION_REGISTRY.json`
- Count docs by type and tier
- Check for missing files, missing required fields
- Output summary to stdout

### `lint`
- Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_lint.py" <remaining args>`

### `plan`
- Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/docs/docs_plan.py" <remaining args>`

### `sync`
1) Resolve `SESSION_DIR`:
   - If `--session` provided, use it.
   - Otherwise use the most recent session under `workflow.sessions_dir` (default `.session/`).
2) Delegate docs edits:
   - Task: `docs-keeper`
   - Provide:
     - `mode=sync`
     - `SESSION_DIR=<resolved>`

### `new <type>`
1) Resolve `SESSION_DIR` (same rules as `sync`).
2) Delegate:
   - Task: `docs-keeper`
   - Provide:
     - `mode=new`
     - `type=<type>`
     - `SESSION_DIR=<resolved>`

## Notes

- Docs edits must remain within `docs/` (the docs-keeper agent enforces this via its scope contract when hooks are enabled).
- For tight, predictable docs updates, prefer running `/at:run` so docs are updated as part of the deliver gates.
