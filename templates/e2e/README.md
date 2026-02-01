# E2E Test Environment

This directory holds **local-only** configuration for end-to-end tests.

## Setup (required)

1) Create your local env file:
   - Copy: `cp e2e/.env.example e2e/.env`
2) Fill required values.
3) Ensure `e2e/.env` is gitignored (never commit credentials).

## Required environment variables

| Variable | Description | Required |
|---|---|---|
| `E2E_BASE_URL` | Base URL for the test target (e.g. `http://localhost:3000`) | Yes |

<!-- Add project-specific variables below -->

## How E2E is used by `at`

- `at` never reads `e2e/.env` via model tools (secrets stay local).
- The deterministic E2E runner may load `e2e/.env` (if configured) to run your configured E2E command.
- Configure E2E command + profiles in `.claude/at/e2e.json` (recommended profiles: `local`, `ci`).

## Manual execution

```bash
# Prefer the deterministic runner (so the model never has to read secrets):
uv run scripts/quality/run_quality_suite.py --only e2e --e2e-profile local
```
