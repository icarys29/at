---
name: learning-status
version: "0.5.0"
updated: "2026-02-02"
description: Show the current learning/memory status for this project.
argument-hint: ""
allowed-tools: Read
---

# /at:learning-status

Show the current automatic learning/memory status for this project.

## Procedure

### 1) Read learning state

Read `.claude/learning/state.json` if it exists.

### 2) Read learning status

Read `.claude/learning/STATUS.md` if it exists.

### 3) Output status

If learning is enabled:
```
# Learning Status

- enabled: `true`
- state_path: `.claude/learning/state.json`

## Current State
{contents of state.json or STATUS.md}

## Recent Learnings
{list recent entries from .claude/learning/learnings/}
```

If learning is not enabled or no state exists:
```
# Learning Status

- enabled: `false` (no state found)

To enable learning:
  /at:setup-learning-hooks
```

## Output

Status to stdout. No artifacts written.
