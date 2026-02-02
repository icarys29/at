---
name: setup
version: "0.5.0"
updated: "2026-02-02"
description: Interactive setup wizard for at - auto-detects tooling and generates project.yaml with minimal user input.
argument-hint: "[--force] [--minimal]"
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# /at:setup

One-command project setup for Agent Team (at).

## When to use
- First time setting up at in a project
- After cloning a repo that doesn't have at configured
- To regenerate configuration with new tooling

## When NOT to use
- Project already has `.claude/project.yaml` (use --force to override)
- You want manual control (use /at:init-project instead)

## Procedure

### 1) Check existing configuration
```bash
if [ -f ".claude/project.yaml" ]; then
  # Warn user and exit unless --force
fi
```

### 2) Detect project type and tooling

Read these files to detect the project:
- `package.json` → Node/TypeScript project
- `pyproject.toml` or `setup.py` → Python project
- `go.mod` → Go project
- `Cargo.toml` → Rust project
- `pom.xml` or `build.gradle` → Java project

For each detected language, probe for tooling:

**Python:**
- Linter: Check for `ruff.toml`, `.ruff.toml`, `pyproject.toml [tool.ruff]` → `ruff check .`
- Formatter: Check ruff → `ruff format .`
- Type checker: Check `mypy.ini`, `pyproject.toml [tool.mypy]` → `mypy .`
- Test runner: Check `pytest.ini`, `conftest.py`, `pyproject.toml [tool.pytest]` → `pytest -q`

**TypeScript/JavaScript:**
- Linter: Check `.eslintrc*`, `eslint.config.*` → `eslint .`
- Formatter: Check `.prettierrc*` → `prettier --check .`
- Type checker: Check `tsconfig.json` → `tsc --noEmit`
- Test runner: Check for jest/vitest config → `npm test` or `vitest run`

**Go:**
- Linter: Check `.golangci.yml` → `golangci-lint run`
- Formatter: `go fmt ./...`
- Test runner: `go test ./...`

**Rust:**
- Linter: `cargo clippy`
- Formatter: `cargo fmt --check`
- Test runner: `cargo test`

### 3) Present detected configuration

Show the user what was detected:
```
Detected project configuration:

Project type: Python
Package manager: uv (found uv.lock)

Tooling detected:
  ✓ Linter: ruff (found ruff.toml)
  ✓ Formatter: ruff format
  ✓ Type checker: mypy (found pyproject.toml [tool.mypy])
  ✓ Test runner: pytest (found conftest.py)
  ✗ Build: not detected

Proposed commands:
  lint: uv run ruff check .
  format: uv run ruff format .
  typecheck: uv run mypy .
  test: uv run pytest -q
```

### 4) Ask for confirmation

Use AskUserQuestion:
```
Is this configuration correct?
- [Accept] Use these settings
- [Edit] Modify before saving
- [Minimal] Create minimal config (skip tooling)
```

### 5) Optional features

Ask about optional features:
```
Enable optional features?
- [x] Learning/memory (recommended) - remembers patterns across sessions
- [ ] Audit logging - detailed tool usage logs
- [ ] Policy hooks - block secrets access
- [ ] Docs enforcement - require documentation updates
```

### 6) Generate configuration

Write `.claude/project.yaml` with detected values.
Create minimal overlay structure:
- `.claude/project.yaml`
- `.claude/rules/project/conventions.md` (placeholder)
- `docs/DOCUMENTATION_REGISTRY.json` (minimal)

### 7) Run doctor

Execute `/at:doctor` to verify the setup works.

### 8) Show next steps

```
Setup complete!

Your at configuration is ready in .claude/project.yaml

Next steps:
1. Review .claude/project.yaml and adjust commands if needed
2. Run /at:doctor to verify configuration
3. Start your first workflow: /at:run deliver "your request"

For help: /at:help
```

## Arguments

- `--force`: Overwrite existing configuration
- `--minimal`: Skip tooling detection, create minimal config

## Output

- `.claude/project.yaml` - Main configuration
- `.claude/rules/project/conventions.md` - Project conventions placeholder
- `docs/DOCUMENTATION_REGISTRY.json` - Documentation registry (if not exists)
