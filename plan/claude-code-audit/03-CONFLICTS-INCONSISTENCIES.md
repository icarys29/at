# Conflicts and Inconsistencies

## Architectural Conflicts

### 1. Dual Validation Paths

**Conflict:** Actions.json is validated in multiple places:
- `scripts/validate/validate_actions.py` — Called explicitly in workflow
- `scripts/hooks/validate_actions_write.py` — Called on PostToolUse Write
- `scripts/validate/actions_validator.py` — Library code used by both

**Impact:**
- Validation runs twice (redundant)
- If rules diverge, behavior is unpredictable
- Maintenance burden (keep both in sync)

**Resolution:** Keep only the explicit call in the workflow. Remove the PostToolUse hook or make it a simple "notify" rather than validate.

### 2. Session Resolution Complexity

**Conflict:** Multiple methods to resolve the current session:
- `lib/session.py` → `resolve_session_dir()` — Uses args or finds most recent
- `lib/active_session.py` → `resolve_session_dir_from_hook()` — Uses env vars or Claude session ID
- Hook scripts parse transcripts to find session references

**Impact:**
- Hooks and scripts may resolve to different sessions
- Race conditions in parallel execution
- Fragile transcript parsing (`_read_tail`, regex matching)

**Resolution:** Establish a single source of truth:
1. Set `AT_SESSION_DIR` environment variable at session creation
2. All scripts/hooks read from this variable
3. Remove transcript parsing heuristics

### 3. Context Pack vs Task Contexts

**Conflict:** Two overlapping context mechanisms:
- `build_context_pack.py` → Global context for all agents
- `build_task_contexts.py` → Per-task context slices

**Overlap:**
- Both include project config
- Both include docs registry
- Both include rules

**Impact:**
- Agents receive duplicate information
- Context size bloats unnecessarily
- Inconsistent information if sources change mid-session

**Resolution:** Define clear boundaries:
- Context pack: Project-wide, session-stable (config, rules, registry summary)
- Task context: Task-specific only (file scope, acceptance criteria, relevant code pointers)

### 4. Scope Enforcement: Hook vs Instruction

**Conflict:** File scope is enforced two ways:
1. `enforce_file_scope.py` hook blocks out-of-scope writes at tool time
2. Agent instructions say "only write within `file_scope.writes[]`"

**Impact:**
- Redundant enforcement
- Hook adds latency to every Write/Edit
- Hook failure modes are opaque to the agent

**Resolution:** Choose one:
- **Option A:** Trust agent instructions, remove hook (simpler)
- **Option B:** Keep hook, remove instruction duplication (harder to debug)

Recommendation: Option A for most users, Option B as opt-in for high-compliance environments.

## Schema/Config Inconsistencies

### 5. Version Field Inconsistency

**Issue:** Session artifacts use `"version": 1` but the plugin uses `"version": "0.3.1"` (string).

**Examples:**
- `session.json` → `"version": 1` (integer)
- `actions.json` → `"version": 1` (integer)
- `plugin.json` → `"version": "0.3.1"` (string, semver)

**Impact:** Minor confusion, but consistent patterns are better.

**Resolution:** Define versioning strategy:
- Plugin: Semver string (`"0.3.1"`)
- Artifact schemas: Integer (`1`, `2`, etc. for breaking changes)
- Document this in `docs/CONTRACTS.md`

### 6. Path Format Inconsistency

**Issue:** Paths are stored in different formats:
- `actions.json` → Repo-relative POSIX paths (`src/foo.ts`)
- Hooks → Resolve to absolute paths, then convert back
- Session artifacts → Sometimes session-relative, sometimes project-relative

**Examples from code:**
```python
# enforce_file_scope.py
repo_rel_posix = str(repo_rel).replace("\\", "/")

# build_context_pack.py
cfg_norm = normalize_repo_relative_posix_path(cfg_rel) or cfg_rel

# session artifacts
"path": str(path.relative_to(session_dir)).replace("\\", "/")
```

**Impact:** Path comparison bugs, especially on Windows.

**Resolution:**
1. Define canonical path format: `repo-relative POSIX` for all artifact paths
2. Create a single `normalize_path()` utility
3. Always resolve + normalize at boundaries (input/output)

### 7. Optional vs Required Fields

**Issue:** `project.yaml` schema is permissive (`additionalProperties: true`), but scripts expect specific structures.

**Example:**
```python
# run_quality_suite.py
commands = cfg.get("commands") if isinstance(cfg.get("commands"), dict) else {}
explicit = commands.get("quality_suite")
```

If `commands.quality_suite` is missing, behavior degrades silently.

**Impact:** Users don't know what's required vs optional.

**Resolution:**
1. Tighten schema with clear `required` arrays
2. Add `/at:doctor` checks for common misconfigurations
3. Generate `project.yaml` comments documenting each field

## Workflow Inconsistencies

### 8. Gate Failure Handling

**Issue:** Different gates handle failure differently:
- `quality_report.json` → Returns exit code 1 on failure
- `docs_gate.py` → Returns exit code 1 on failure
- `compliance_report.json` → Returns exit code based on aggregation

But the orchestrator (`/at:run`) doesn't consistently check exit codes.

**Impact:** Gate failures may be missed.

**Resolution:**
1. Define gate contract: All gates return exit 0 (pass) or 1 (fail)
2. Orchestrator checks exit codes and stops on failure
3. Add `--continue-on-failure` flag for lenient mode

### 9. Remediation Loop Ambiguity

**Issue:** `workflow.max_remediation_loops: 2` exists, but remediation behavior is unclear.

From `SKILL.md`:
```markdown
- If remediation loops are exhausted, stop and optionally use `--rollback`.
```

But:
- What triggers a remediation loop?
- What does the `remediator` agent actually change?
- How is loop count tracked?

**Impact:** Users don't understand when/why remediation happens.

**Resolution:**
1. Document remediation triggers (gate X fails → remediate)
2. Track loop count in `session.json`
3. Add `status/remediation_history.json` with timestamps and actions

### 10. TDD Strategy Enforcement

**Issue:** `workflow.strategy=tdd` is documented but enforcement is unclear.

From `action-planner.md`:
```markdown
- If `workflow.strategy=tdd`:
  - Create `tests-builder` tasks that produce failing/expected tests **before** implementation tasks.
  - Every `implementor` task must include `depends_on[]` referencing at least one `tests-builder` task id.
```

But:
- Is this validated by `validate_actions.py`? (Not clearly)
- What if the agent doesn't follow TDD order?

**Impact:** TDD mode may not actually enforce test-first.

**Resolution:**
1. Add explicit TDD validation to `actions_validator.py`
2. Create a test case for TDD plan validation
3. Document TDD requirements in the schema comments

## Documentation Conflicts

### 11. CLAUDE.md vs Maintainer Guide

**Issue:** Two versions of the project description:
- `CLAUDE.md` (root) — User/developer instructions
- `.claude-plugin/CLAUDE.md` — Plugin-specific (if it exists)

The system-reminder shows a "Maintainer Guide" version that differs from the root CLAUDE.md.

**Impact:** Confusion about which is authoritative.

**Resolution:** Single CLAUDE.md at root; move maintainer content to `docs/CONTRIBUTING.md`.

### 12. Skill vs Agent Naming

**Issue:** Some names are inconsistent:
- Skill: `/at:ideate` → Agent: `ideation` (not `ideate`)
- Skill: `/at:brainstorm` → Agent: `brainstormer` (different suffix)
- Skill: `/at:run review` → Agent: `reviewer` (consistent!)

**Impact:** Minor confusion when mapping skills to agents.

**Resolution:** Standardize naming:
- Skills: verb form (`/at:ideate`, `/at:review`)
- Agents: `-er` suffix (`ideator`, `reviewer`, `implementor`)

### 13. Hook Configuration Locations

**Issue:** Hooks can be configured in multiple places:
- `hooks/hooks.json` — Plugin default
- `.claude/settings.json` — Project override
- `~/.claude/settings.json` — User override

**Documentation gap:** The precedence is not clearly documented.

**Resolution:** Add `docs/HOOKS.md` explaining:
1. Hook discovery order
2. How to override plugin defaults
3. How to disable specific hooks

## Data Flow Issues

### 14. Artifact Coupling

**Issue:** Artifacts have implicit dependencies:
```
context_pack.md → requires → request.md, project.yaml, rules/*
task_context/*.md → requires → actions.json, context_pack.md
compliance_report.json → requires → all gate reports
```

But these dependencies aren't declared or validated.

**Impact:** Running scripts out of order produces confusing errors.

**Resolution:**
1. Add `depends_on` to each script's docstring
2. Add `--check-prerequisites` flag
3. Create `scripts/lib/artifact_deps.py` with dependency graph

### 15. Parallel Execution State

**Issue:** `parallel_execution.groups` in actions.json defines parallel tasks, but state tracking is unclear.

Questions:
- How does the orchestrator know which tasks are running?
- How are task results aggregated?
- What happens if a parallel task fails?

**Impact:** Parallel execution may have race conditions or incomplete error handling.

**Resolution:**
1. Add `status/parallel_execution_state.json`
2. Track task status: `pending`, `running`, `completed`, `failed`
3. Define failure semantics (fail-fast vs continue)
