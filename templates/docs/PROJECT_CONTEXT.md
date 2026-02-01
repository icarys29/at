# Project Context

<!-- Keep every section concise: required and sufficient information only. No filler. -->

## Purpose

Describe what this repository is and why it exists.

- Product / domain:
- Primary users (humans/services):
- What success looks like:

## Runtime + Deliverables

- Type: library | service | CLI | monorepo
- Deploy/runtime environment:
- Supported platforms:

## Architecture Overview

Keep this high signal. Reference `CLAUDE.md` for the authoritative architectural contract.

- Key modules/packages:
- Key boundaries (if any):
- Primary data flow:

## External Integrations

List IO edges (DBs, APIs, message buses, filesystems).

- Integration:
  - Ownership:
  - Connectivity/auth:
  - Failure modes:

## Public Surface Area

What should be treated as user-facing contract?

- Public APIs / endpoints:
- Config surface:
- CLI commands (if any):

## Local Development

Put the commands that humans actually run (they should match `.claude/project.yaml`).

- Format:
- Lint:
- Typecheck:
- Test:
- Build:

## Documentation Registry

This repo uses a portable **docs registry** at `docs/DOCUMENTATION_REGISTRY.json`:
- `documents[]`: canonical docs with tiers (1 critical / 2 important / 3 optional)
- `coverage_rules[]`: optional mapping from **changed files** → **required docs to review/update**

If you add a new canonical doc, add it to the registry.

## Non-Goals / Constraints

- Constraints (security, compliance, performance):
- Explicit non-goals:

