---
name: architecture-brief
version: "0.5.0"
updated: "2026-02-02"
description: Generate a concise, evidence-backed architecture brief for a request (patterns, constraints, docs anchors) without executing implementation.
argument-hint: "[--session <id|dir>] <request>"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Task
---

# /at:architecture-brief

## Procedure
1) Create or resume a session:
   - If user provided `--session`, resume; otherwise create a new session.
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/session/create_session.py" --workflow deliver [--session <id|dir>]`
   - Capture the printed `SESSION_DIR`.
2) Write the request to `SESSION_DIR/inputs/request.md`.
3) Build the context pack:
   - Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/context/build_context_pack.py" --session "${SESSION_DIR}"`
4) Produce the architecture brief (agentic):
   - Task: `solution-architect`
   - Inputs: `SESSION_DIR/inputs/request.md`, `SESSION_DIR/inputs/context_pack.md`
   - Output files: `SESSION_DIR/planning/ARCHITECTURE_BRIEF.{md,json}`
5) Print the session directory and the brief paths.
