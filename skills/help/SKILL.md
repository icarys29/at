---
name: help
version: "0.5.0"
updated: "2026-02-02"
description: "Display at plugin help: quickstart, workflows, and command index."
argument-hint: ""
allowed-tools: Read, Glob
---

# /at:help

Display comprehensive help for the at plugin.

## Procedure

### 1) Show quickstart
```
# at — Help

## Quickstart

1. `/at:init-project` (first time in a repo)
2. `/at:run "<request>"` (default workflow: deliver)
3. `/at:session-progress --session <id>` (check progress)

## Workflows (via /at:run)

- `deliver` — plan → implement/tests → gates → docs → final artifacts
- `triage` — root-cause analysis + remediation options
- `review` — evidence-backed review report
- `ideate` — architecture brief + options exploration
```

### 2) List available commands

Read skill frontmatter from `skills/*/SKILL.md` files using Glob and Read tools.

For each skill, extract:
- `name` from frontmatter
- `description` from frontmatter
- `argument-hint` from frontmatter

### 3) Output command index

Format:
```
## Commands

- `/at:run` `[deliver|triage|review|ideate] [--tdd] [--session <id>] <request>` — Orchestrate the at workflow kernel
- `/at:doctor` — Validate project configuration
- `/at:docs` `[status|plan|sync|new|lint]` — Documentation management
...
```

## Output

Concise help to stdout. No artifacts written.
