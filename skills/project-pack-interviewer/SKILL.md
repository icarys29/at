---
name: project-pack-interviewer
version: "0.4.0"
updated: "2026-02-02"
description: "Guided wizard to install a project pack (enforcement runner + optional architecture boundaries + default-on god-class check)."
argument-hint: "[--project-dir <path>] [--style none|hex] [--domain-path <path> --application-path <path> --adapters-path <path>] [--no-god-class-check] [--enforcement-mode warn|fail] [--sessions-dir <dir>] [--force]"
allowed-tools: Read, Write, Edit, Bash
---

# /at:project-pack-interviewer

## Goal
Install a project pack safely, with guided questions, without requiring the user to memorize flags.

## Procedure

1) Determine defaults:
   - `project_dir`: current directory unless user passes `--project-dir`.
   - `sessions_dir`: read from `.claude/project.yaml` when present; else default `.session`.
   - `enforcement_mode`: default `warn`.

2) If user did not pass explicit flags in `$ARGUMENTS`, ask (one at a time):
   - Architecture style: `none` or `hex` (default: `none`).
   - If `hex`:
     - `domain_path` (e.g. `src/domain`)
     - `application_path` (e.g. `src/application`)
     - `adapters_path` (e.g. `src/adapters`)
   - Disable god-class enforcement? (default: no)
     - If no (keep enabled): optionally ask whether to customize thresholds:
       - `max_methods` (default 25) and `max_lines` (default 400)
   - Enforcement mode: `warn` or `fail` (default: `warn`)
   - Overwrite existing files? (`--force`) (default: no)

3) Run the installer:
   - `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/project_pack/install_project_pack.py" <assembled args>`

4) Report what was created/merged/skipped and the next step:
   - If you installed checks, recommend running `/at:verify` to see enforcement results.
