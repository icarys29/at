---
name: resolve-failed-quality
version: "0.5.0"
updated: "2026-02-02"
description: "Resolve a failing quality command by iterating: rerun the failing command → minimal fix → rerun until pass."
argument-hint: "<path/to/quality_report.json|--session <id|dir>> [<command_id>]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:resolve-failed-quality

Use when `SESSION_DIR/quality/quality_report.json` has a failing command and you want a focused fix loop without rerunning the entire workflow.

## Procedure

1) Resolve `SESSION_DIR` (required):
   - If the first argument looks like a path to `quality_report.json`, treat it as `REPORT_PATH` and set `SESSION_DIR=<REPORT_PATH>/../..`.
   - Otherwise require `--session <id|dir>` and resolve it by running:
     - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --session "<id|dir>"`
     - Capture the printed `SESSION_DIR`.

2) Determine `COMMAND_ID`:
   - If user provided a second positional arg, treat it as the command id.
   - Otherwise, pick the first failing command in `SESSION_DIR/quality/quality_report.json` (`status in failed|timeout|error`).

3) Delegate to the fixer agent (repo edits happen here, not in the skill):
   - Task: `quality-fixer`
   - Provide:
     - `SESSION_DIR=<resolved>`
     - `command_id=<resolved>`

## Notes
- If the fix requires external prerequisites (tooling/env), stop and report what’s missing instead of making speculative changes.
- For pure reruns without fixing, use `/at:fix-quality`.
