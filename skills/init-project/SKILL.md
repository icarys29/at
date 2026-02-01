---
name: init-project
description: Bootstrap a repo overlay (`.claude/project.yaml`, baseline rules, docs scaffolding) for at.
argument-hint: "[--force]"
allowed-tools: Read, Write, Bash
---

# /at:init-project

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/init_project.py" $ARGUMENTS`
2) Review created files and adjust `.claude/project.yaml` commands to match your repo.
