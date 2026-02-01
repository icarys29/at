# Audit — User Stories + E2E Enforcement

Date: 2026-02-01

## Problem

Deliver was missing two “completion integrity” pillars:
- **User stories** as a deterministic definition of “what must be true”
- **End-to-end verification** as a final proof that the request was actually delivered

Without these, the workflow can become “unit-test green” while still failing to satisfy real user intent.

## Reference (previous plugin)

The previous plugin (0.7.42) treated this as a first-class ideation + quality concern:
- Ideation produced `analysis/user_stories.md` + `analysis/e2e_test_suggestions.md`
- Quality gate supported E2E commands with `requires_env` / `requires_files` and skip logic
- Shipped an `e2e/` scaffold with `.env.example` and guidance

## What was implemented (current plugin)

### 1) User stories are now a deliver artifact (agentic, SRP-separated)

- New subagent: `story-writer`
- Outputs:
  - `planning/USER_STORIES.md`
  - `planning/USER_STORIES.json`
- `/at:run` runs it before `action-planner` so planning is anchored to explicit stories.

### 2) User stories are enforced deterministically (gate)

- New gate: `scripts/validate/user_stories_gate.py`
- When `workflow.require_user_stories=true`:
  - requires `planning/USER_STORIES.json`
  - requires story coverage via `task.user_story_ids[]` across code tasks

### 3) E2E is configured safely via project overlay (no YAML mutation)

- Template: `templates/claude/at/e2e.json` → installed as `.claude/at/e2e.json`
- Guided scaffolding: `/at:setup-e2e` installs:
  - `e2e/README.md`
  - `e2e/.env.example`
  - `.claude/at/e2e.json`
  - ensures `.gitignore` includes `e2e/.env`
- Security posture:
  - model tools remain blocked from reading `e2e/.env` (secrets stay local)
  - the deterministic runner may load `e2e/.env` to populate env for the E2E command

### 4) E2E is enforced deterministically (gate)

- Quality suite can run a configured E2E command (via `.claude/at/e2e.json`).
- New gate: `scripts/validate/e2e_gate.py`
- Policy via `.claude/project.yaml`:
  - `workflow.e2e_mode: off|optional|required`

## Why this is more reliable

- Story coverage becomes machine-checkable and self-healing (remediation can add missing story links/tasks).
- E2E verification becomes an explicit gate rather than an informal suggestion.

## Remaining gaps / follow-ups

- No automatic generation of E2E tests themselves (that remains an implementation/testing task).
- Some repos need multiple E2E profiles (staging vs local); consider supporting multiple entries in `.claude/at/e2e.json` later.

