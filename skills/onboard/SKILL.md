---
name: onboard
version: "0.4.0"
updated: "2026-02-02"
description: "Analyze a repo and propose/apply an at overlay onboarding (safe: overlay + docs only)."
argument-hint: "[--apply] [--force] [--project-dir <path>]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:onboard

## Procedure
1) Run the analyzer (proposal only; no repo code edits):
   - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/onboarding/analyze_repo.py" $ARGUMENTS`
2) Read and summarize the generated report:
   - `.claude/at/onboarding_report.md`
   - Highlight:
     - existing overlay/docs state
     - detected languages + recommended language packs
     - planned creates
     - suggested next steps
3) Guided confirmation (wizard UX):
   - If an overlay already exists, recommend `/at:upgrade-project` unless the user explicitly wants onboarding to overwrite files (`--force`).
   - Ask whether to:
     - apply onboarding now (`--apply`)
     - install recommended hooks (policy/audit/docs-keeper) via the dedicated setup commands
4) If user provided `--apply` (or confirms apply), apply onboarding (with backups; overlay+docs only):
   - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/onboarding/apply_onboarding.py" $ARGUMENTS`
