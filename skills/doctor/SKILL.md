---
name: doctor
description: Validate that the current repo overlay is usable for at (config, docs registry policy, sessions dir).
argument-hint: "[--json]"
allowed-tools: Read, Bash
---

# /at:doctor

## Procedure
1) Run: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" $ARGUMENTS`
2) If it fails, follow the remediation hints (usually: run `/at:init-project` and edit `.claude/project.yaml`).
