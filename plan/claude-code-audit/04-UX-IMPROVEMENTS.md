# UX Improvements: Installation, Upgrade, and Daily Use

## Current State Assessment

### Installation Friction Points

1. **Multiple steps required:**
   ```bash
   claude --plugin-dir /path/to/at  # Or clone + symlink
   cd my-project
   /at:init-project
   # Edit .claude/project.yaml manually
   /at:doctor
   # Optionally install hooks
   /at:setup-policy-hooks
   /at:setup-audit-hooks
   /at:setup-learning-hooks
   /at:setup-docs-keeper-hooks
   /at:setup-ux-nudges-hooks
   # Optionally install language packs
   /at:install-language-pack python
   ```

2. **Config file editing required:**
   - `project.yaml` requires manual customization
   - Commands section needs project-specific values
   - No auto-detection of existing tooling

3. **No quick-start path:**
   - New users must understand sessions, gates, compliance
   - Documentation is comprehensive but overwhelming

### Upgrade Friction Points

1. **Version headers everywhere:**
   - Every script has `Version:` and `Updated:` headers
   - Every agent/skill has `version:` and `updated:` frontmatter
   - Manual sync required between `plugin.json`, `VERSION`, and headers

2. **No automatic migration:**
   - Schema changes require manual `project.yaml` updates
   - Hook changes require reinstallation

3. **No rollback mechanism:**
   - If upgrade breaks, no easy way to revert

### Daily Use Friction Points

1. **Command complexity:**
   - `/at:run deliver --tdd --session <id>` has many flags
   - Flag combinations aren't always clear

2. **Error messages are technical:**
   - "actions.json does not conform to the contract" without specific guidance
   - Hook failures show stack traces

3. **Session management overhead:**
   - Must remember session IDs to resume
   - Old sessions accumulate

## Improvement Recommendations

### 1. One-Command Installation

**Goal:** `claude install at && /at:setup`

**Implementation:**

```markdown
# /at:setup

## Procedure
1) Detect project type:
   - Read package.json (Node/TypeScript)
   - Read pyproject.toml / setup.py (Python)
   - Read go.mod (Go)
   - Read Cargo.toml (Rust)

2) Auto-detect tooling:
   - Linter: eslint / ruff / golangci-lint / clippy
   - Formatter: prettier / ruff format / gofmt / rustfmt
   - Type checker: tsc / mypy / N/A / rustc
   - Test runner: jest/vitest / pytest / go test / cargo test

3) Generate `project.yaml` with detected values:
   - Ask for confirmation: "Found: ruff, pytest, mypy. Correct? [Y/n]"

4) Create minimal overlay:
   - `.claude/project.yaml` (generated)
   - `.claude/rules/project/conventions.md` (placeholder)
   - `docs/DOCUMENTATION_REGISTRY.json` (minimal)

5) Offer optional features:
   - "Enable audit logging? [y/N]"
   - "Enable policy hooks (secrets protection)? [y/N]"
   - "Enable learning/memory? [Y/n]"

6) Run `/at:doctor` to verify setup
```

### 2. Interactive Project Import

**Goal:** `/at:import-repo` with smart defaults

**Flow:**
```
$ /at:import-repo

Analyzing repository...
- Language: Python (pyproject.toml)
- Package manager: uv
- Linter: ruff (found ruff.toml)
- Type checker: mypy (found mypy.ini)
- Test runner: pytest (found conftest.py)
- Docs: docs/ exists (12 markdown files)

Proposed configuration:
┌─────────────────────────────────────────┐
│ project:                                │
│   name: my-project                      │
│   primary_languages: [python]           │
│ commands:                               │
│   python:                               │
│     lint: uv run ruff check .           │
│     format: uv run ruff format .        │
│     typecheck: uv run mypy .            │
│     test: uv run pytest -q              │
└─────────────────────────────────────────┘

[A]ccept, [E]dit, or [C]ancel?
```

### 3. Simplified Command Interface

**Goal:** Fewer flags, smarter defaults

**Current:**
```
/at:run deliver --session 20260202-143021-a1b2c3 --dry-run
```

**Proposed:**
```
/at:deliver           # Most common case
/at:deliver --dry-run # Plan without executing
/at:resume            # Auto-resume latest session
/at:resume a1b2c3     # Resume by short ID
```

**Implementation:**
- Add aliases: `/at:deliver` → `/at:run deliver`
- Add `/at:resume` skill
- Support short session IDs (6 chars)

### 4. Friendly Error Messages

**Current:**
```
FAIL: actions.json does not conform to the contract.
File: /path/to/session/planning/actions.json
- .tasks[0].acceptance_criteria: Field is required
```

**Proposed:**
```
Plan validation failed: Missing acceptance criteria

Task "implement-auth" needs acceptance criteria.
Each task must define how to verify it's complete.

Example fix:
  "acceptance_criteria": [
    {
      "id": "ac-1",
      "statement": "Login endpoint returns 200 for valid credentials",
      "verifications": [
        {"type": "command", "command": "pytest tests/test_auth.py -k login"}
      ]
    }
  ]

Run `/at:run --dry-run` to check your plan without executing.
```

### 5. Session Management UX

**Current:**
```
/at:sessions                    # List all sessions
/at:session-progress            # Show current session
/at:cleanup-sessions            # Manual cleanup
```

**Proposed:**
```
/at:status                      # Quick status of current session
/at:history                     # Recent sessions with status
/at:history --archive           # Move completed sessions to archive/

Session list:
┌────────────┬──────────┬────────┬─────────────────────┐
│ ID         │ Workflow │ Status │ Last Updated        │
├────────────┼──────────┼────────┼─────────────────────┤
│ a1b2c3     │ deliver  │ ✓ done │ 2h ago              │
│ d4e5f6     │ triage   │ ◐ wip  │ 30m ago (active)    │
│ g7h8i9     │ review   │ ✗ fail │ 1d ago              │
└────────────┴──────────┴────────┴─────────────────────┘

Actions: [r]esume, [a]rchive, [d]elete, [q]uit
```

### 6. Guided Workflows

**Goal:** Progressive disclosure for new users

**Implementation:** Add `/at:guide` skill

```markdown
# /at:guide

Welcome to Agent Team (at)!

Quick start:
1. `/at:deliver <request>` — Implement a feature with full quality gates
2. `/at:ideate <topic>` — Brainstorm approaches without code changes
3. `/at:triage <bug>` — Investigate and document a bug

What would you like to do?
[1] Deliver a feature
[2] Brainstorm an approach
[3] Triage a bug
[4] Learn more about at
```

### 7. Automatic Upgrade Path

**Goal:** `at upgrade` with migration

**Implementation:**

```python
# scripts/upgrade/auto_upgrade.py

def upgrade_project(project_root: Path):
    """
    1. Check plugin version vs project overlay version
    2. Generate migration plan
    3. Apply non-breaking changes automatically
    4. Prompt for breaking changes
    5. Update version markers
    """

    current = get_project_overlay_version(project_root)
    target = get_plugin_version()

    if current == target:
        print("Already up to date.")
        return

    migrations = get_migrations(current, target)

    for m in migrations:
        if m.breaking:
            print(f"Breaking change: {m.description}")
            if not confirm("Apply this change?"):
                continue
        m.apply(project_root)

    update_overlay_version(project_root, target)
```

### 8. Better Help System

**Current:** `/at:help` exists but is basic

**Proposed:**

```
/at:help           # Quick reference card
/at:help deliver   # Detailed help for deliver workflow
/at:help gates     # Explain quality gates
/at:help errors    # Common errors and fixes
/at:help config    # project.yaml reference
```

Help output:
```
Agent Team (at) — Quick Reference

Workflows:
  /at:deliver <request>    Implement with quality gates
  /at:ideate <topic>       Brainstorm approaches
  /at:triage <bug>         Investigate issues
  /at:review               Review session artifacts

Utilities:
  /at:status              Current session status
  /at:resume [id]         Resume a session
  /at:doctor              Check configuration

Configuration:
  /at:setup               Initial project setup
  /at:upgrade             Upgrade to latest version

More: /at:help <topic>
```

### 9. Visual Progress Indicators

**Goal:** Show workflow progress in real-time

**Implementation:** Add progress markers to `/at:run` output

```
/at:deliver "Add user authentication"

[1/7] Creating session... ✓ (20260202-150000-abc123)
[2/7] Building context... ✓
[3/7] Planning...
      └─ Architecture brief... ✓
      └─ User stories... ✓
      └─ Action plan... ✓ (3 tasks)
[4/7] Validating plan... ✓
[5/7] Executing tasks...
      └─ implement-auth-middleware [████████░░] 80%
      └─ implement-login-endpoint  [waiting]
      └─ add-auth-tests           [waiting]
[6/7] Running gates...
      └─ Quality suite... ◐
      └─ Docs update... [waiting]
      └─ Compliance... [waiting]
[7/7] Generating report... [waiting]
```

### 10. Undo/Rollback Made Easy

**Current:**
```
/at:run --rollback 20260202-143021-a1b2c3 --checkpoint cp-001
```

**Proposed:**
```
/at:undo              # Undo last session's changes
/at:undo --preview    # Show what would be undone
/at:rollback abc123   # Rollback specific session
```

## Priority Matrix

| Improvement | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| One-command installation | High | Medium | P0 |
| Friendly error messages | High | Low | P0 |
| Session management UX | Medium | Low | P1 |
| Guided workflows | Medium | Medium | P1 |
| Automatic upgrade path | High | High | P1 |
| Visual progress | Low | Medium | P2 |
| Better help system | Medium | Low | P2 |
| Simplified commands | Low | Low | P2 |
