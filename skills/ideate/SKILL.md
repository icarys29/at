---
name: ideate
version: "0.5.0"
updated: "2026-02-02"
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
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow ideate [--session <id|dir>]`
   - Capture the printed `SESSION_DIR`.
2) Write the request to `SESSION_DIR/inputs/request.md`.
3) Build the context pack:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_context_pack.py" --session "${SESSION_DIR}"`
3.5) Archive previous ideation outputs (if rerunning ideate):
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/planning/archive_planning_outputs.py" --session "${SESSION_DIR}"`
4) Produce the architecture brief (agentic):
   - Task: `solution-architect`
   - Output: `SESSION_DIR/planning/ARCHITECTURE_BRIEF.{md,json}`
4.5) Generate user stories (agentic):
   - Task: `story-writer`
   - Output: `SESSION_DIR/planning/USER_STORIES.{md,json}`
5) Brainstorm options and recommendation (agentic):
   - Task: `brainstormer`
   - Inputs: request + context pack + (optional) architecture brief
   - Output: `SESSION_DIR/planning/IDEATION.{md,json}`
6) Print the session directory and key artifact paths.
