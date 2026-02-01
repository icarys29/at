---
name: onboard
version: "0.1.0"
updated: "2026-02-01"
description: Analyze a repo and propose/apply an at overlay onboarding (safe: overlay + docs only).
argument-hint: "[--apply] [--force] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:onboard

## Procedure
1) Always run the analyzer (proposal only):
   - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/onboarding/analyze_repo.py" $ARGUMENTS`
2) If user provided `--apply`, apply onboarding (with backups; overlay+docs only):
   - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/onboarding/apply_onboarding.py" $ARGUMENTS`

