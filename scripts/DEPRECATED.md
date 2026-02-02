# Removed Scripts — Migration Guide

> **Version:** 0.5.0

This guide documents scripts that were removed in v0.5.0 and their migration paths.

## Timeline

- **v0.4.0**: Deprecation warnings added to 28 scripts
- **v0.5.0** (current): Scripts removed, functionality replaced by agent instructions or Claude Code native features

## Migration Summary

| Category | Count | Replacement Strategy |
|----------|-------|---------------------|
| Validation scripts | 12 | Agent self-validation + hooks |
| Workflow scripts | 3 | Merged into `/at:run` skill |
| Session analysis | 3 | Agent reasoning tasks |
| Quality scripts | 2 | Merged into quality suite |
| Docs scripts | 3 | Agent inline + LSP |
| Maintenance scripts | 2 | Skill content + agent tasks |
| Learning scripts | 2 | Agent reasoning tasks |
| Enforcement scripts | 2 | Optional project pack |
| Planning scripts | 1 | Inline file operations |

---

## Category: Validation Scripts (12)

These scripts perform checks that can be expressed as agent instructions or handled by hooks.

### `validate/validate_actions.py`

**Current:** Validates `planning/actions.json` against schema and rules.

**Migration:** Agent self-validates during planning. Schema rules live in `agents/action-planner.md`.

**Before:**
```bash
uv run scripts/validate/validate_actions.py --session "$SESSION_DIR"
```

**After:** Action-planner agent validates its own output before writing. No external script needed.

---

### `validate/actions_validator.py`

**Current:** Library module used by validate_actions.py.

**Migration:** Removed along with validate_actions.py.

---

### `validate/plan_adherence.py`

**Current:** Compares planned verifications against actual task outputs.

**Migration:** Agent self-check. Verifications are evaluated by the agent inline.

**Before:**
```bash
uv run scripts/validate/plan_adherence.py --session "$SESSION_DIR"
```

**After:** Agent reads task artifacts and verifies acceptance criteria were met. Use LSP for semantic checks.

---

### `validate/parallel_conformance.py`

**Current:** Checks that parallel task groups don't have overlapping write scopes.

**Migration:** Action-planner validates this during planning phase.

**Before:**
```bash
uv run scripts/validate/parallel_conformance.py --session "$SESSION_DIR"
```

**After:** Action-planner ensures `parallel_execution.groups` have non-overlapping `file_scope.writes[]`.

---

### `validate/validate_changed_files.py`

**Current:** Validates git changes match declared file scopes.

**Migration:** Scope enforcement hook (`enforce_file_scope.py`) blocks out-of-scope writes at tool-time.

**Before:**
```bash
uv run scripts/validate/validate_changed_files.py --session "$SESSION_DIR"
```

**After:** Hook prevents scope violations proactively. Post-hoc validation unnecessary.

---

### `validate/validate_task_artifacts.py`

**Current:** Checks that task YAML artifacts exist with required fields.

**Migration:** Agent validates own outputs per contract in agent markdown files.

**Before:**
```bash
uv run scripts/validate/validate_task_artifacts.py --session "$SESSION_DIR"
```

**After:** Implementor/tests-builder agents write artifacts as part of their reply contract.

---

### `validate/gates_summary.py`

**Current:** Aggregates gate results into summary.

**Migration:** Agent inline aggregation — trivial JSON/MD generation.

**Before:**
```bash
uv run scripts/validate/gates_summary.py --session "$SESSION_DIR"
```

**After:** Agent reads gate artifacts and produces summary inline.

---

### `validate/docs_gate.py`

**Current:** Checks documentation registry and drift.

**Migration:** Merged into docs-keeper workflow.

**Before:**
```bash
uv run scripts/validate/docs_gate.py --session "$SESSION_DIR"
```

**After:** Use `/at:docs lint` or let `/at:run` invoke docs-keeper automatically.

---

### `validate/e2e_gate.py`

**Current:** Thin wrapper for E2E test execution.

**Migration:** Merged into quality suite.

**Before:**
```bash
uv run scripts/validate/e2e_gate.py --session "$SESSION_DIR"
```

**After:** Configure `e2e` in `.claude/project.yaml` quality commands. Quality suite runs it.

---

### `validate/user_stories_gate.py`

**Current:** Validates user story coverage.

**Migration:** Agent validation using traceability matrix.

**Before:**
```bash
uv run scripts/validate/user_stories_gate.py --session "$SESSION_DIR"
```

**After:** Story-writer agent produces traceability; action-planner verifies coverage.

---

### `validate/verifications_gate.py`

**Current:** Thin wrapper for run_verifications.py.

**Migration:** Merged into quality suite.

---

### `validate/run_verifications.py`

**Current:** Runs acceptance verifications from actions.json.

**Migration:** Merged into quality suite; LSP-based verifications use lsp-verifier agent.

**Before:**
```bash
uv run scripts/validate/run_verifications.py --session "$SESSION_DIR"
```

**After:** Quality suite handles verification commands. For LSP-type, use lsp-verifier agent.

---

## Category: Workflow Scripts (3)

Thin orchestration scripts merged into `/at:run`.

### `workflow/run_review.py`

**Current:** Generates review context for reviewer agent.

**Migration:** `/at:run review` handles this inline.

**Before:**
```bash
uv run scripts/workflow/run_review.py --session "$SESSION_DIR"
```

**After:**
```
/at:run review --session <id>
```

---

### `workflow/run_triage.py`

**Current:** Generates triage context for root-cause-analyzer.

**Migration:** `/at:run triage` handles this inline.

**Before:**
```bash
uv run scripts/workflow/run_triage.py --session "$SESSION_DIR"
```

**After:**
```
/at:run triage --session <id>
```

---

### `workflow/generate_dry_run_report.py`

**Current:** Generates dry-run preview report.

**Migration:** Agent generates report inline after planning.

**Before:**
```bash
uv run scripts/workflow/generate_dry_run_report.py --session "$SESSION_DIR"
```

**After:**
```
/at:run deliver --dry-run "<request>"
```
Agent writes the dry-run report directly.

---

## Category: Session Analysis Scripts (3)

Reasoning tasks better suited to agents.

### `session/session_diagnostics.py`

**Current:** Generates diagnostic report for a session.

**Migration:** Agent reasoning task — reads artifacts and diagnoses.

**Before:**
```bash
uv run scripts/session/session_diagnostics.py --session "$SESSION_DIR"
```

**After:** Use `/at:session-progress` which includes diagnostic reasoning.

---

### `session/session_auditor.py`

**Current:** Generates scorecard and recommendations.

**Migration:** Agent reasoning task.

**Before:**
```bash
uv run scripts/session/session_auditor.py --session "$SESSION_DIR"
```

**After:** Use `/at:session-auditor` which invokes the agent directly (or agent inline for v0.5.0).

---

### `session/retrospective.py`

**Current:** Generates retrospective report.

**Migration:** Agent reasoning task.

**Before:**
```bash
uv run scripts/session/retrospective.py --session "$SESSION_DIR"
```

**After:** Use `/at:retrospective` which invokes agent reasoning directly.

---

## Category: Quality Scripts (2)

Merged into the main quality suite.

### `quality/rerun_quality_command.py`

**Current:** Reruns a single quality command.

**Migration:** Quality suite with `--command` filter.

**Before:**
```bash
uv run scripts/quality/rerun_quality_command.py "<command_id>" --session "$SESSION_DIR"
```

**After:**
```bash
uv run scripts/quality/run_quality_suite.py --session "$SESSION_DIR" --only "<command_id>"
```

---

### `quality/verify.py`

**Current:** CI-friendly verification runner.

**Migration:** Merged into quality suite.

**Before:**
```bash
uv run scripts/quality/verify.py
```

**After:**
```
/at:verify
```
Or run quality suite directly.

---

## Category: Docs Scripts (3)

### `docs/docs_requirements_for_plan.py`

**Current:** Computes docs requirements before planning.

**Migration:** Coverage rules in agent instructions.

**Before:**
```bash
uv run scripts/docs/docs_requirements_for_plan.py --session "$SESSION_DIR"
```

**After:** Docs-keeper uses coverage rules from `scripts/docs/coverage_rules.py` directly.

---

### `docs/docs_status.py`

**Current:** Registry health overview.

**Migration:** Agent reads registry and reports directly.

**Before:**
```bash
uv run scripts/docs/docs_status.py
```

**After:**
```
/at:docs status
```
Agent reads `docs/DOCUMENTATION_REGISTRY.json` and generates status inline.

---

### `docs/code_index.py`

**Current:** Generates code index for docs generation.

**Migration:** Use LSP tool directly for code analysis.

**Before:**
```bash
uv run scripts/docs/code_index.py --session "$SESSION_DIR"
```

**After:** Agent uses LSP `documentSymbol` and `workspaceSymbol` operations for code analysis.

---

## Category: Maintenance Scripts (2)

### `maintenance/self_audit.py`

**Current:** Self-audits plugin configuration.

**Migration:** Agent reasoning task.

**Before:**
```bash
uv run scripts/maintenance/self_audit.py
```

**After:** Use `/at:doctor` for configuration checks. Agent reasoning for deeper audit.

---

### `maintenance/help.py`

**Current:** Generates help/command index.

**Migration:** Help content lives in SKILL.md files.

**Before:**
```bash
uv run scripts/maintenance/help.py
```

**After:**
```
/at:help
```
Skills are self-documenting via frontmatter.

---

## Category: Learning Scripts (2)

### `learning/learning_status.py`

**Current:** Shows learning/memory status.

**Migration:** Agent reads state directly.

**Before:**
```bash
uv run scripts/learning/learning_status.py
```

**After:**
```
/at:learning-status
```
Agent reads `.claude/learning/state.json` and reports.

---

### `learning/continuous_learning.py`

**Current:** Extracts learnings from session.

**Migration:** Agent reasoning task.

**Before:**
```bash
uv run scripts/learning/continuous_learning.py --session "$SESSION_DIR" --apply --yes
```

**After:**
```
/at:continuous-learning --session <id>
```
Agent extracts patterns and updates learning artifacts.

---

## Category: Enforcement Scripts (2)

Niche features moved to optional project pack.

### `enforcement/install_god_class_check.py`

**Current:** Installs god-class detection hook.

**Migration:** Optional feature in project packs.

**Before:**
```bash
uv run scripts/enforcement/install_god_class_check.py
```

**After:** Install the "enforcement" project pack which includes this feature.

---

### `enforcement/god_class_audit.py`

**Current:** Audits codebase for god classes.

**Migration:** Optional feature in project packs.

---

## Category: Planning Scripts (1)

### `planning/archive_planning_outputs.py`

**Current:** Archives planning outputs for ideate sessions.

**Migration:** Inline file operations.

**Before:**
```bash
uv run scripts/planning/archive_planning_outputs.py --session "$SESSION_DIR"
```

**After:** Agent moves files directly using Edit/Write tools.

---

## Compliance Scripts (1)

### `compliance/generate_compliance_report.py`

**Current:** Generates compliance report from gate artifacts.

**Migration:** Agent inline aggregation.

**Before:**
```bash
uv run scripts/compliance/generate_compliance_report.py --session "$SESSION_DIR"
```

**After:** Agent reads gate artifacts and produces compliance decision inline. Trivial `ok` field aggregation.

---

## Scripts Being Kept

These scripts provide real value and will NOT be deprecated:

| Script | Reason |
|--------|--------|
| `session/create_session.py` | Filesystem setup, env vars |
| `checkpoint/*.py` | Git operations for rollback |
| `quality/run_quality_suite.py` | Subprocess execution, log capture |
| `audit/*.py` | Structured logging to JSONL |
| `init_project.py` | Project overlay setup |
| `doctor.py` | Configuration validation |
| `docs/generate_registry_md.py` | Deterministic transformation |
| `docs/allocate_doc_id.py` | ID allocation with collision avoidance |
| `docs/docs_lint.py` | Registry integrity checks |
| `docs/docs_plan.py` | Deterministic docs planning |
| `upgrade/*.py` | Version migration logic |
| `context/build_context_pack.py` | Context assembly |
| `context/build_task_contexts.py` | Per-task context slices |
| `hooks/*.py` (non-deprecated) | Policy enforcement, scope checks |

---

## Preparing for v0.5.0

1. **Update your workflows** to use `/at:run` workflows instead of calling deprecated scripts directly.

2. **Test agentic alternatives** before the removal:
   - `/at:docs status` instead of `docs_status.py`
   - `/at:run review` instead of `run_review.py`
   - `/at:session-progress` instead of `session_diagnostics.py`

3. **Enable hooks** for proactive enforcement instead of post-hoc validation:
   - `/at:setup-policy-hooks` — block forbidden operations
   - Scope enforcement via `AT_FILE_SCOPE_WRITES` env var

4. **Use Claude Code native features**:
   - LSP tool for code analysis instead of `code_index.py`
   - TaskCreate/TaskUpdate for tracking instead of custom task boards

---

## Questions?

If you have questions about migrating from a deprecated script, use `/at:help` or check the skill documentation in `skills/*/SKILL.md`.
