# Audit — Running E2E Outside Deliver (profiles + safe secrets)

Date: 2026-02-01

## Problem

Teams need to run E2E:
- outside the deliver workflow (on demand)
- across multiple environments (local, CI, staging)
- without exposing credentials to the model or committing them

## What was implemented

### 1) E2E profiles in `.claude/at/e2e.json`

Template supports:
- `enabled`
- `id` (defaults to `e2e`)
- `default_profile`
- `profiles.<name>` with:
  - `command`
  - `env_file` (nullable)
  - `requires_env[]`
  - `requires_files[]`

### 2) Quality runner supports E2E-only runs + profile selection

`scripts/quality/run_quality_suite.py` now supports:
- `--only e2e` to run just E2E (no full suite)
- `--e2e-profile <name>` to select profile configuration
- E2E is appended even when `commands.quality_suite` is used (deduped by id)

### 3) Dedicated skill: `/at:e2e`

Runs:
- create/resume session
- run E2E only (`--only e2e`)
- run `e2e_gate` + `gates_summary` for evidence

### 4) Safer secrets posture

- Model tool reads of `e2e/.env` remain blocked by `policies.forbid_secrets_globs`.
- The deterministic runner may load `env_file` internally and pass env to the subprocess.
- Policy hook blocks common `Bash` patterns that would print `e2e/.env` contents to the transcript.

## Resulting UX

- Setup once: `/at:setup-e2e`
- Run on demand (any time): `/at:e2e --profile local` (or `ci`)
- Enforce required E2E in deliver by setting `workflow.e2e_mode: required`

