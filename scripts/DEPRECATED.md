# Deprecated Scripts

These scripts are marked for removal in a future version. Their functionality has been moved to agent instructions or simplified alternatives.

## Scheduled for Removal

### Validation Scripts (moved to agent instructions)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `validate/validate_actions.py` | Agent self-validation | Schema rules in action-planner.md |
| `validate/actions_validator.py` | Agent self-validation | Library used by validate_actions.py |
| `validate/plan_adherence.py` | Agent self-check | Comparing what agent wrote |
| `validate/parallel_conformance.py` | Agent planning rules | Action-planner validates during planning |
| `validate/validate_changed_files.py` | Scope enforcement | Hook already enforces this |
| `validate/validate_task_artifacts.py` | Agent output contract | Agent validates own outputs |
| `validate/gates_summary.py` | Agent inline | Simple aggregation |
| `validate/docs_gate.py` | docs-keeper workflow | Merged into docs workflow |
| `validate/e2e_gate.py` | quality suite | Thin wrapper |
| `validate/user_stories_gate.py` | Agent validation | Coverage validation |
| `validate/verifications_gate.py` | quality suite | Merged |
| `validate/run_verifications.py` | quality suite | Merged |

### Compliance Scripts (simplified)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `compliance/generate_compliance_report.py` | Agent inline | Trivial aggregation of ok fields |

### Workflow Scripts (merged)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `workflow/run_review.py` | /at:run skill | Thin orchestration |
| `workflow/run_triage.py` | /at:run skill | Thin orchestration |
| `workflow/generate_dry_run_report.py` | Agent report | Agent can generate |

### Docs Scripts (simplified)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `docs/docs_requirements_for_plan.py` | Coverage rules | Agent instructions |
| `docs/docs_status.py` | Agent report | Agent can read and report |
| `docs/code_index.py` | LSP tool | Direct LSP usage |

### Session Scripts (agent tasks)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `session/session_diagnostics.py` | Agent diagnosis | Reasoning task |
| `session/session_auditor.py` | Agent reasoning | Analysis task |
| `session/retrospective.py` | Agent reasoning | Analysis task |

### Quality Scripts (merged)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `quality/rerun_quality_command.py` | quality suite | Thin wrapper |
| `quality/verify.py` | quality suite | Merged |

### Maintenance Scripts (moved)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `maintenance/self_audit.py` | Agent task | Reasoning task |
| `maintenance/help.py` | Skill content | Help in SKILL.md |

### Learning Scripts (simplified)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `learning/learning_status.py` | Agent report | Simple state reading |
| `learning/continuous_learning.py` | Agent task | Reasoning task |

### Enforcement Scripts (niche)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `enforcement/install_god_class_check.py` | Optional pack | Niche feature |
| `enforcement/god_class_audit.py` | Optional pack | Niche feature |

### Planning Scripts (inline)

| Script | Replacement | Notes |
|--------|-------------|-------|
| `planning/archive_planning_outputs.py` | Inline file ops | Simple operations |

## Simplified Replacements

These scripts have simplified replacements:

| Original | Replacement | Reduction |
|----------|-------------|-----------|
| `hooks/enforce_file_scope.py` (325 lines) | `hooks/enforce_file_scope_simple.py` (~80 lines) | 75% |
| `context/build_context_pack.py` (430 lines) | `templates/context_pack.md.tpl` + thin wrapper | 80% |

## Migration Timeline

- **v0.4.0**: Deprecation warnings added
- **v0.5.0**: Scripts removed, replaced with agent instructions

## Keeping Scripts

These scripts provide real value and should be kept:

- `session/create_session.py` - Filesystem setup
- `checkpoint/*.py` - Git operations
- `quality/run_quality_suite.py` - Subprocess execution
- `audit/*.py` - Structured logging
- `init_project.py` - Project setup
- `doctor.py` - Configuration validation
- `docs/generate_registry_md.py` - Simple transformation
- `docs/allocate_doc_id.py` - ID allocation
- `upgrade/*.py` - Migration logic
