---
name: ideate
version: "0.1.0"
updated: "2026-02-01"
description: >
  Structured ideation for a request: generate an architecture brief and brainstorm options grounded in repo patterns and project constraints.
argument-hint: "[--session <id|dir>] <request>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:ideate

## Outputs (session artifacts)
- `planning/ARCHITECTURE_BRIEF.{md,json}`
- `planning/IDEATION.{md,json}`

## Procedure
1) Create or resume a session (workflow=ideate):
   - If user provided `--session`, resume; otherwise create a new session.
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow ideate [--resume <id|dir>]`
   - Capture the printed `SESSION_DIR`.
2) Write the request to `SESSION_DIR/inputs/request.md`.
3) Build the context pack:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_context_pack.py" --session "${SESSION_DIR}"`
4) Produce the architecture brief (agentic):
   - Task: `solution-architect`
   - Output: `SESSION_DIR/planning/ARCHITECTURE_BRIEF.{md,json}`
5) Brainstorm options and recommendation (agentic):
   - Task: `brainstormer`
   - Inputs: request + context pack + (optional) architecture brief
   - Output: `SESSION_DIR/planning/IDEATION.{md,json}`
6) Print the session directory and key artifact paths.

