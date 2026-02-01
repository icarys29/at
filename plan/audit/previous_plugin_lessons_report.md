# Previous Plugin Analysis → Rebuild Lessons (at)

- Source reviewed: previous plugin snapshot (captured as artifacts in `plan/audit/`; plugin.json version: 0.7.42)
- Output artifacts (this repo): `plan/audit/`

## Executive Summary

The prior `at` plugin is a strong foundation: it established a **session-backed, contract-driven workflow** with strict scope, deterministic gates, and minimal context via task slices. The biggest rebuild opportunity is to **reduce surface area** (fewer skills/agents/scripts), **eliminate drift** (single source of truth for contracts), and **make determinism the default** (uv-scripted hooks + gate scripts), while keeping agentic execution for planning/implementation.

## What Worked Well (keep the patterns)

- **Sessions as the unit of work**: everything under a single `SESSION_DIR` with stable artifact names.
- **Schema-first planning**: `schemas/actions.schema.json` as the plan contract + deterministic validation (`scripts/validate/validate_actions.py`).
- **Task-level context slicing**: context pack + `inputs/task_context/<task>.md` to enforce “least context”.
- **File-scope enforcement**: `file_scope.writes[]` + hook-time enforcement (`scripts/hooks/enforce_file_scope.py`).
- **Binary gates with machine-readable evidence**: JSON reports for plan adherence, parallel conformance, quality, docs, LSP.
- **Artifact validation as a hook component**: `SubagentStop` hook verifies required final reply contract + artifact presence and prevents infinite loops (circuit breaker).
- **Portable hook delivery via `uv run --script`**: skill-installed hooks (policy/audit) are self-contained and deterministic.

## What Hurt Reliability / Adoption (fix in rebuild)

- **Contract drift**: multiple “truths” emerged (e.g., inconsistent task artifact schemas; validators not wired or stale). Rebuild needs one authoritative schema per artifact + tests or at least deterministic validators wired into the workflow.
- **Docs registry coupling risk**: the old plugin audit called out that forcing a fully populated docs registry can block onboarding. Keep `docs.require_registry` configurable and provide pragmatic fallbacks for new repos.
- **Too many overlapping skills/agents**: duplicates (e.g., `setup-*` vs `*-deployer`), deprecated agents still present, multiple docs agents. In rebuild: consolidate aggressively.
- **Mixed runtime dependencies**: Node-based hook scripts are optional UX sugar but add fragility. Prefer Python-only hooks unless proven valuable.
- **Duplication inside scripts (DRY violations)**: repeated YAML parsing, repeated path normalization/glob matching, repeated JSON/MD report writers.
- **Untestable orchestration logic**: workflow logic living only in Markdown specs is hard to regression-test. Keep the agentic orchestrator, but add a small deterministic “state/progress” engine (or at least deterministic phase checks) early.

## Lessons From the Prior Internal Audit (2026-01-25)

A prior adversarial audit is archived locally at `plan/audit/upstream/PLUGIN_AUDIT_2026-01-25.md`. Key takeaways to keep in the rebuild:

- Make docs registry enforcement **optional** (avoid chicken-and-egg).
- Provide **rollback** (git checkpoint) before implementation.
- Enforce agent “final reply contracts” by validating **files**, not natural language (hooks help, but file validation is more robust).
- Add **phase resume** (`--from-phase`) and **dry-run** support.
- Provide **LSP fallbacks** (`fail|warn|skip`) so CI/dev environments aren’t blocked.

## Rebuild Principles (DRY / SRP / YAGNI)

### DRY
- One artifact → one schema → one validator. No duplicate validators or divergent examples.
- Centralize: YAML parsing, path policy, glob matching, report writers (JSON+MD), timestamping.
- Prefer generated docs from schemas/templates over hand-copied examples in many agents.

### SRP
- Orchestrator (skill) orchestrates only: runs deterministic scripts + dispatches subagents.
- Subagents implement only their assignment; they do not spawn other subagents (Claude Code constraint).
- Hooks are tiny “components”: one hook script = one responsibility (scope enforcement, artifact validation, policy enforcement, audit logging).

### YAGNI / Keep It Simple
- Ship an end-to-end **deliver** workflow with a minimal set of agents + gates first.
- Defer advanced subsystems until the core is stable: audit analytics, project packs/enforcement, upgrade tooling, telemetry dashboards, repo import wizards.
- Avoid Node hooks in v1 unless they measurably improve outcomes.

## Proposed Build Order (step-by-step)

Use this phased plan to rebuild without reintroducing bloat:

- **P0 (Foundations)**: repo skeleton, versioning discipline, shared libs, schemas, minimal docs.
- **P1 (Kernel)**: sessions + planning contract + context pack/slices + basic execution scaffold (planner → implementor → tests). Add artifact validation hook.
- **P2 (Gates)**: deterministic plan adherence + parallel conformance + quality suite runner + compliance + docs gate. Add rollback + policy hooks.
- **P3 (Advanced)**: audit hooks + analysis, learning/memory, telemetry KPIs, project-pack enforcement, upgrade/import utilities.

## Core Kernel Contract (what we should rebuild first)

The rebuild should keep a small, explicit contract surface area. The minimum “deliver kernel” is:

- **Session structure (deterministic)**:
  - `session.json` (workflow, created_at, state, pointers)
  - `inputs/request.md`
  - `inputs/context_pack.md` (best-effort for non-deliver; required for deliver)
  - `status/session_progress.{json,md}` (phase status + next step)
- **Plan contract (schema + validator)**:
  - `planning/actions.json` validated against a JSON Schema
  - The schema must own: `tasks[]`, `file_scope`, `acceptance_criteria`, and optional `parallel_execution`
- **Task execution contract (per-task artifacts)**:
  - `inputs/task_context/<task_id>.md` + `inputs/task_context_manifest.json`
  - `implementation/tasks/<task_id>.yaml` and `testing/tasks/<task_id>.yaml`
  - These artifacts should have their own tiny schema and be validated (prefer file-based validation over “final reply” parsing).
- **Gate artifacts (deterministic evidence)**:
  - `quality/plan_adherence_report.{json,md}`
  - `quality/parallel_conformance_report.{json,md}` (only when parallel enabled)
  - `quality/quality_report.{json,md}` (quality suite runner)
  - `compliance/COMPLIANCE_VERIFICATION_REPORT.md` (agentic, but validate decision marker)
  - `documentation/docs_summary.{json,md}` + `documentation/docs_gate_report.{json,md}` (can be phase 2)

## Deterministic Python Strategy (uv + portability)

The previous plugin already used a good pattern for hook assets:
- `#!/usr/bin/env -S uv run --script` + a `# /// script` metadata block (no third-party deps, pinned Python requirement).

Recommended rebuild approach:
- Keep **core gate scripts** deterministic, pure-CLI, explicit I/O, and runnable with:
  - `uv run ...` when `uv` is present
  - fallback to `uv run` (or `python3`) when it is not
- Standardize on a single wrapper convention used everywhere (skills + docs):
  - `PY_BIN` detection pattern (or a shared helper) so every script is invoked consistently.
- Do **not** make the plugin depend on third-party Python libraries for core operation (stdlib-only is a major portability win).

## Hook “Components” (how to leverage Claude Code hooks cleanly)

Treat each hook as an installable, minimal “component”:

- **Scope enforcement (PreToolUse: Write/Edit)**:
  - Enforce `file_scope.writes[]` for the active task to prevent accidental out-of-scope edits.
- **Artifact contract enforcement (SubagentStop)**:
  - Validate “required artifacts exist” + “artifact files parse/validate”.
  - Include a circuit breaker to avoid infinite remediation loops.
- **Plan safety (PostToolUse: Write)**:
  - When `planning/actions.json` is written, validate immediately against the schema and block invalid writes.
- **Policy enforcement (PreToolUse: Read/Write/Edit/Bash)** (optional but recommended early):
  - Block `.env`/secrets access and dangerous destructive commands via `policies.forbid_secrets_globs`.
- **Audit logging (PreToolUse/PostToolUse/SessionStart/SessionEnd/SubagentStop)** (phase 3):
  - Write JSONL logs under `.claude/audit_logs/` (opt-in, because it’s sensitive).

## Simplification Decisions to Apply in the Rebuild

Concrete simplification targets (DRY + SRP + YAGNI):

- **Pick one docs registry**: the old repo mixes `docs/DOCUMENTATION_REGISTRY.json` and `docs/REGISTRY.json`. Choose one canonical name/format and delete the other.
- **Eliminate Node hook scripts** in v1: keep hooks Python-only unless a Node hook proves essential.
- **Consolidate duplicate skills**:
  - Keep only one of `setup-audit-hooks` vs `audit-hooks-deployer` (alias the other name).
  - Keep only one of `setup-policy-hooks` vs `policy-hooks-deployer`.
  - Merge `import-repo` and `repo-importer` into a single import wizard (or drop entirely in early phases).
- **Remove dead/unused scripts** in the old repo (e.g., `scripts/validate/validate_agent_artifact.py`) and prevent reintroduction by wiring validators into the workflow and/or adding a tiny smoke test suite.

## Inventory + Keep/Drop Recommendations

All raw inventory is stored in:
- `plan/audit/previous_plugin_inventory.json`
- `plan/audit/previous_plugin_entrypoints_full.json`
- `plan/audit/previous_plugin_keep_drop_matrix.json`

### Phase distribution (recommended)

Python: DROP=3, P0=7, P0-DEV=2, P1=12, P1-OPT=2, P2=9, P2-OPT=24, P3-OPT=37

Agents: DROP=2, P1=3, P2=3, P2-OPT=5, P3-OPT=7

Skills: P1=5, P2-OPT=8, P3-OPT=19

### Python scripts (all)

| Phase | Category | Path | Purpose | Used by | Notes |
|---|---|---|---|---|---|
| DROP | inception | scripts/inception/__init__.py |  |  |  |
| DROP | inception | scripts/inception/apply_inception.py | Apply inception patterns |  |  |
| DROP | validate | scripts/validate/validate_agent_artifact.py | Validate agent output artifacts |  | Appears unused + schema drift vs current task artifacts; remove in rebuild. |
| P0 | lib | scripts/lib/__init__.py |  |  |  |
| P0 | lib | scripts/lib/docs_config.py | Documentation configuration dataclass |  |  |
| P0 | lib | scripts/lib/enforcer_conventions.py | Plugin script: enforcer_conventions |  |  |
| P0 | lib | scripts/lib/io.py | I/O utilities for file operations and timestamps |  |  |
| P0 | lib | scripts/lib/path_policy.py | Path policy utilities |  |  |
| P0 | lib | scripts/lib/project.py | Project detection and configuration utilities |  |  |
| P0 | lib | scripts/lib/simple_yaml.py | Simple YAML parser |  |  |
| P0-DEV | dev | scripts/dev/add_version_headers.py | Add version headers to all plugin files |  |  |
| P0-DEV | dev | scripts/dev/cleanup_bytecode.py | Clean up Python bytecode files |  |  |
| P1 | context | scripts/context/__init__.py |  |  |  |
| P1 | context | scripts/context/build_context_pack.py | Build context pack for agent workflows | skills |  |
| P1 | context | scripts/context/build_task_contexts.py | Build per-task context slices from actions.json | run |  |
| P1 | hooks | scripts/hooks/enforce_file_scope.py | Enforce file scope restrictions on Write/Edit tools | hooks |  |
| P1 | hooks | scripts/hooks/on_subagent_stop.py | Subagent stop hook for artifact validation | hooks |  |
| P1 | scripts_root | scripts/doctor.py | Plugin health check and diagnostics | skills,run |  |
| P1 | scripts_root | scripts/init_project.py | Initialize project with plugin | skills |  |
| P1 | session | scripts/session/__init__.py |  |  |  |
| P1 | session | scripts/session/create_session.py | Create new workflow session | skills |  |
| P1 | session | scripts/session/list_sessions.py | List existing sessions | skills |  |
| P1 | session | scripts/session/session_progress.py | Track and report session progress | skills |  |
| P1 | validate | scripts/validate/validate_actions.py | Validate actions.json structure | run |  |
| P1-OPT | workflow | scripts/workflow/__init__.py |  |  |  |
| P1-OPT | workflow | scripts/workflow/generate_dry_run_report.py | Generate dry run report | run |  |
| P2 | quality | scripts/quality/__init__.py |  |  |  |
| P2 | quality | scripts/quality/run_quality_suite.py | Run quality gate commands | skills |  |
| P2 | validate | scripts/validate/__init__.py |  |  |  |
| P2 | validate | scripts/validate/check_subagent_capability.py | Check subagent capabilities |  |  |
| P2 | validate | scripts/validate/docs_gate.py | Documentation gate validation | run |  |
| P2 | validate | scripts/validate/lsp_gate.py | LSP-based verification gate | run |  |
| P2 | validate | scripts/validate/parallel_conformance.py | Validate parallel execution conformance | run |  |
| P2 | validate | scripts/validate/plan_adherence.py | Verify plan adherence after implementation | run |  |
| P2 | validate | scripts/validate/validate_changed_files.py | Validate files changed by agents |  |  |
| P2-OPT | checkpoint | scripts/checkpoint/__init__.py |  |  |  |
| P2-OPT | checkpoint | scripts/checkpoint/create_checkpoint.py | Create git checkpoint before implementation | skills,run |  |
| P2-OPT | checkpoint | scripts/checkpoint/restore_checkpoint.py | Restore git checkpoint on failure | skills |  |
| P2-OPT | docs | scripts/docs/__init__.py |  |  |  |
| P2-OPT | docs | scripts/docs/analyze_codebase.py | Analyze codebase for documentation | skills |  |
| P2-OPT | docs | scripts/docs/analyze_with_lsp.py | Plugin script: analyze_with_lsp |  | Not referenced by workflows; keep only if docs generation needs it. |
| P2-OPT | docs | scripts/docs/audit_docs.py | Audit documentation completeness | skills |  |
| P2-OPT | docs | scripts/docs/bootstrap_docs.py | Plugin script: bootstrap_docs | skills |  |
| P2-OPT | docs | scripts/docs/ensure_change_doc.py | Ensure documentation for changes |  |  |
| P2-OPT | docs | scripts/docs/generate_docs.py | Plugin script: generate_docs | skills |  |
| P2-OPT | docs | scripts/docs/populate_registry_sections.py | Populate registry with doc sections |  | Nice-to-have (sections indexing); not required for core deliver. |
| P2-OPT | docs | scripts/docs/sync_registry.py | Plugin script: sync_registry | skills |  |
| P2-OPT | docs | scripts/docs/validate_docs.py | Plugin script: validate_docs | skills |  |
| P2-OPT | hooks | scripts/hooks/__init__.py |  |  |  |
| P2-OPT | hooks | scripts/hooks/audit_log.py | Audit logging hook for tool and agent tracking |  |  |
| P2-OPT | hooks | scripts/hooks/generate_hooks_json.py | Generate hooks.json configuration |  |  |
| P2-OPT | hooks | scripts/hooks/on_session_start.py | Session start hook for initialization | hooks |  |
| P2-OPT | hooks | scripts/hooks/on_setup.py | Setup hook for plugin initialization | hooks |  |
| P2-OPT | hooks | scripts/hooks/resolve_agent_path.py | Resolve agent paths for custom agents |  |  |
| P2-OPT | hooks | scripts/hooks/uninstall_hooks.py | Uninstall plugin hooks from settings | skills |  |
| P2-OPT | hooks | scripts/hooks/validate_actions_write.py | Validate actions.json writes against schema | hooks |  |
| P2-OPT | hooks | scripts/hooks/validate_task_invocation.py | Validate Task tool invocations | hooks |  |
| P2-OPT | skill_asset | skills/policy-hooks-deployer/assets/hooks/policy_pre_tool_use.py | Portable Claude Code Hook: Policy Enforcement (at) |  |  |
| P2-OPT | skill_script | skills/policy-hooks-deployer/scripts/install_policy_hooks.py | Install at policy enforcement hooks into a Claude Code project or user scope. | skills |  |
| P3-OPT | agents | scripts/agents/generate_project_agents.py | Generate project-specific agents |  |  |
| P3-OPT | audit | scripts/audit/__init__.py |  |  |  |
| P3-OPT | audit | scripts/audit/audit_analyzer.py | Analyze audit logs | skills |  |
| P3-OPT | audit | scripts/audit/audit_log_parser.py | Parse and extract data from audit log files |  |  |
| P3-OPT | audit | scripts/audit/prune_audit_logs.py | Prune old audit log entries | skills |  |
| P3-OPT | audit | scripts/audit/recommendations.py | Generate audit recommendations |  |  |
| P3-OPT | audit | scripts/audit/report_generator.py | Generate audit reports in markdown and JSON |  |  |
| P3-OPT | audit | scripts/audit/scoring.py | Score audit metrics |  |  |
| P3-OPT | audit | scripts/audit/session_auditor.py | Run full session audits | skills |  |
| P3-OPT | audit | scripts/audit/subagent_extractor.py | Extract detailed subagent data from audit logs |  |  |
| P3-OPT | audit | scripts/audit/subagent_report_writer.py | Write per-subagent audit reports |  |  |
| P3-OPT | import | scripts/import/__init__.py |  |  |  |
| P3-OPT | import | scripts/import/detect_docs.py | Detect existing documentation | skills |  |
| P3-OPT | import | scripts/import/detect_tooling.py | Detect project tooling configuration | skills |  |
| P3-OPT | import | scripts/import/generate_config.py | Generate project configuration | skills |  |
| P3-OPT | learning | scripts/learning/learning_status.py | Show learning/memory status | skills |  |
| P3-OPT | learning | scripts/learning/update_learning_state.py | Update learning state from sessions | skills,run |  |
| P3-OPT | maintenance | scripts/maintenance/__init__.py |  |  |  |
| P3-OPT | maintenance | scripts/maintenance/cleanup_sessions.py | Clean up old sessions | skills |  |
| P3-OPT | orchestrator | scripts/orchestrator/__init__.py | Workflow orchestration engine for at. |  | Only needed if you move orchestration into Python (state machine); otherwise skip. |
| P3-OPT | orchestrator | scripts/orchestrator/phases/__init__.py | Phase implementations for workflow engine. |  | Only needed if you move orchestration into Python (state machine); otherwise skip. |
| P3-OPT | orchestrator | scripts/orchestrator/phases/phase_doctor.py | Doctor phase implementation |  | Only needed if you move orchestration into Python (state machine); otherwise skip. |
| P3-OPT | orchestrator | scripts/orchestrator/workflow_engine.py | Core workflow orchestration engine |  | Only needed if you move orchestration into Python (state machine); otherwise skip. |
| P3-OPT | skill_asset | skills/audit-hooks-deployer/assets/hooks/audit_sessions.py | Portable Claude Code Hook: Session Lifecycle Audit (at) |  |  |
| P3-OPT | skill_asset | skills/audit-hooks-deployer/assets/hooks/audit_subagents.py | Portable Claude Code Hook: Subagent Lifecycle Audit (at) |  |  |
| P3-OPT | skill_asset | skills/audit-hooks-deployer/assets/hooks/audit_tools.py | Portable Claude Code Hook: Tool Usage Audit (at) |  |  |
| P3-OPT | skill_asset | skills/audit-hooks-deployer/assets/hooks/auto_approve_session.py | Claude Code Hook: Auto-Approve Session File Edits (at) |  |  |
| P3-OPT | skill_asset | skills/audit-hooks-deployer/assets/hooks/context_inject.py | Claude Code Hook: Context Injection (at) |  |  |
| P3-OPT | skill_asset | skills/god-class-detector/assets/check_god_classes.py | God class detection (portable, no third-party deps). | skills |  |
| P3-OPT | skill_asset | skills/project-pack-interviewer/assets/enforcement/check_architecture_boundaries.py | Architecture boundary enforcement (portable, no third-party deps). |  |  |
| P3-OPT | skill_asset | skills/project-pack-interviewer/assets/enforcement/run_enforcements.py | Run at enforcement checks for a repo (fail-the-gate by default). |  |  |
| P3-OPT | skill_script | skills/audit-hooks-deployer/scripts/install_audit_hooks.py | Install at audit hooks into a Claude Code project or user scope. | skills |  |
| P3-OPT | skill_script | skills/god-class-detector/scripts/install_god_class_detector.py | Install god class detection for at. | skills |  |
| P3-OPT | skill_script | skills/project-pack-interviewer/scripts/install_project_pack.py | Install repo-specific project pack rules and (optional) enforcement for at. | skills |  |
| P3-OPT | telemetry | scripts/telemetry/__init__.py |  |  |  |
| P3-OPT | telemetry | scripts/telemetry/build_session_kpis.py | Build session KPI metrics | skills,run |  |
| P3-OPT | upgrade | scripts/upgrade/upgrade_project.py | Upgrade project to latest plugin version | skills |  |

### JS files

| Phase | Path | Purpose | Used by | Notes |
|---|---|---|---|---|
| DROP | scripts/hooks/auto-format.js | Auto-Format Hook (PostToolUse) |  | Prefer Python-only hooks to avoid Node dependency. |
| DROP | scripts/hooks/session-end.js | Session End Hook (Stop) | hooks | Prefer Python-only hooks to avoid Node dependency. |
| DROP | scripts/hooks/session-start.js | Session Start Hook |  | Prefer Python-only hooks to avoid Node dependency. |
| DROP | scripts/lib/language-detector.js | Language Detection Library |  | Prefer Python-only hooks to avoid Node dependency. |
| DROP | scripts/lib/utils.js | Utility functions for hooks and scripts |  | Prefer Python-only hooks to avoid Node dependency. |
| P3-OPT | scripts/hooks/detect-debug.js | Debug Statement Detection Hook (PostToolUse) | hooks | Optional UX: debug-statement reminder; can be rewritten in Python. |
| P3-OPT | scripts/hooks/suggest-compact.js | Strategic Compact Suggester (PreToolUse) | hooks | Optional UX: /compact reminders; not core. |

### Agents

| Phase | Name | Path | Purpose | Notes |
|---|---|---|---|---|
| DROP | docs-builder | agents/docs-builder.md | [DEPRECATED - use docs-keeper instead] Bootstrap, discover, update, and validate project documentation. | Deprecated by docs-keeper. |
| DROP | docs-generator | agents/docs-generator.md | [DEPRECATED - use docs-keeper instead] Generate, audit, or migrate documentation. | Deprecated by docs-keeper. |
| P1 | action-planner | agents/action-planner.md | Create a verifiable, executable plan (actions.json + traceability + verification checklist). Use before any implementati |  |
| P1 | implementor | agents/implementor.md | Implement non-test code changes assigned by actions.json, within declared file scope. Use for production code changes (n |  |
| P1 | tests-builder | agents/tests-builder.md | Write or update tests assigned by actions.json and project conventions (tests-only by default). Use when tests are requi |  |
| P2 | compliance-checker | agents/compliance-checker.md | Verify acceptance criteria and checklist items with evidence, producing a binary APPROVE/REJECT decision. |  |
| P2 | docs-keeper | agents/docs-keeper.md | Unified documentation management agent. Maintains documentation as a living contract through bootstrap, sync, update, di |  |
| P2 | quality-gate | agents/quality-gate.md | Run configured quality commands from .claude/project.yaml (format/lint/typecheck/test/build/e2e) and capture evidence fo |  |
| P2-OPT | ideation | agents/ideation.md | Interactive ideation agent with user stories, traceability matrix, SRP/DRY/KISS compliance, and plugin-aware recommendat |  |
| P2-OPT | lsp-verifier | agents/lsp-verifier.md | Run LSP-based semantic verification checks declared in planning/actions.json (acceptance_criteria.verification.type='lsp |  |
| P2-OPT | reviewer | agents/reviewer.md | Review changes for correctness, plan compliance, and policy adherence. Verifies all planned tasks and acceptance criteri |  |
| P2-OPT | root-cause-analyzer | agents/root-cause-analyzer.md | Reproduce and isolate issues, confirm root cause, and propose fix + prevention. Produces analysis/root_cause.md. |  |
| P2-OPT | tdd-guide | agents/tdd-guide.md | Guide Test-Driven Development through Red-Green-Refactor cycles. Use with `/at:run deliver --tdd` for test-first feature |  |
| P3-OPT | analysis-auditor | agents/analysis-auditor.md | Audit analysis phases (triage, ideate) for issue investigation, option exploration, and recommendation quality | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | audit-aggregator | agents/audit-aggregator.md | Aggregate audit results from phase auditors, calculate overall scores, and generate recommendations | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | compliance-auditor | agents/compliance-auditor.md | Audit the compliance verification phase, analyzing acceptance criteria verification and approval decisions | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | planning-auditor | agents/planning-auditor.md | Audit the planning phase of a workflow session, analyzing actions.json structure, context selection, and task breakdown  | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | quality-auditor | agents/quality-auditor.md | Audit the quality gate phase, analyzing command execution, pass/fail results, and coverage metrics | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | review-auditor | agents/review-auditor.md | Audit the code review phase, analyzing review thoroughness, finding quality, and feedback actionability | Only needed if you keep the session-auditor subsystem. |
| P3-OPT | task-auditor | agents/task-auditor.md | Audit individual implementation/test tasks, analyzing context usage, tool efficiency, and completion status | Only needed if you keep the session-auditor subsystem. |

### Skills

| Phase | Name | Path | Purpose | Notes |
|---|---|---|---|---|
| P1 | doctor | skills/doctor/SKILL.md | Validate and auto-fix .claude/project.yaml and tool availability for at |  |
| P1 | init-project | skills/init-project/SKILL.md | Generate a project overlay for at (CLAUDE.md, .claude/rules, .claude/project.yaml) for Python/Go/TypeScript/Rust |  |
| P1 | run | skills/run/SKILL.md | Run a contract-driven workflow (deliver/triage/review/ideate) with always-on sessions and quality/compliance gates |  |
| P1 | session-progress | skills/session-progress/SKILL.md | Show a session progress report and the recommended next step (best-effort; supports resume workflows) |  |
| P1 | sessions | skills/sessions/SKILL.md | List at sessions (reads workflow.sessions_dir and prints session id/workflow/status/updated_at) |  |
| P2-OPT | docs | skills/docs/SKILL.md | Manage project documentation - bootstrap, generate from codebase analysis with LSP, sync registry, audit coverage. |  |
| P2-OPT | policy-hooks-deployer | skills/policy-hooks-deployer/SKILL.md | Install and configure Claude Code policy enforcement hooks (fail-the-gate) to block secrets access and dangerous command | Consolidate into one command (keep one name, keep other as alias). |
| P2-OPT | registry | skills/registry/SKILL.md | [DEPRECATED - use /at:docs instead] Manual registry management. Registry is now auto-maintained. |  |
| P2-OPT | resolve-failed-quality | skills/resolve-failed-quality/SKILL.md | Resolve a failing quality check from quality/quality_report.json by fixing root cause and re-running the failing command |  |
| P2-OPT | setup-policy-hooks | skills/setup-policy-hooks/SKILL.md | Install and configure at policy enforcement hooks (opt-in) to block secrets access and dangerous commands | Consolidate into one command (keep one name, keep other as alias). |
| P2-OPT | tdd-workflow | skills/tdd-workflow/SKILL.md | Test-Driven Development workflow skill for implementing features using Red-Green-Refactor cycle |  |
| P2-OPT | uninstall-hooks | skills/uninstall-hooks/SKILL.md | Uninstall at hooks from Claude Code settings (audit/policy) |  |
| P2-OPT | verify | skills/verify/SKILL.md | Run comprehensive verification checks before PR |  |
| P3-OPT | audit | skills/audit/SKILL.md | Analyze Claude Code audit logs under .claude/audit_logs (sessions/tools/subagents/traces) for observability and debuggin |  |
| P3-OPT | audit-hooks-deployer | skills/audit-hooks-deployer/SKILL.md | Install and configure Claude Code hooks for tool/session/subagent auditing (writes JSONL logs under .claude/audit_logs). | Consolidate into one command (keep one name, keep other as alias). |
| P3-OPT | cleanup-sessions | skills/cleanup-sessions/SKILL.md | Clean up old sessions based on retention policy (max age and count) |  |
| P3-OPT | continuous-learning | skills/continuous-learning/SKILL.md | Automatically extract reusable patterns from Claude Code sessions and save them for future use |  |
| P3-OPT | god-class-audit | skills/god-class-detector/SKILL.md | Scan codebase for god classes (SRP violations) and generate refactoring suggestions. Configurable thresholds for SLOC, m |  |
| P3-OPT | help | skills/help/SKILL.md | Display comprehensive help for at. Shows available commands, workflows, common use cases, and links to detailed document |  |
| P3-OPT | import-repo | skills/import-repo/SKILL.md | Wizard to import an existing repository into at with auto-detection of tooling, docs, and guided configuration | Merge into one import wizard; avoid duplicate flows. |
| P3-OPT | learning-status | skills/learning-status/SKILL.md | Show the current automatic learning/memory status for this project (at) |  |
| P3-OPT | learning-update | skills/learning-update/SKILL.md | Update the project's automatic learning/memory artifacts from a session (defaults to latest) |  |
| P3-OPT | project-bootstrapper | skills/project-bootstrapper/SKILL.md | Bootstrap a repo for at by generating CLAUDE.md, .claude/project.yaml, baseline rules under .claude/rules/at/, a repo-ow |  |
| P3-OPT | project-pack-interviewer | skills/project-pack-interviewer/SKILL.md | Interview the user and generate repo-specific "project pack" rules under .claude/rules/project/ with corporate-grade con |  |
| P3-OPT | prune-audit-logs | skills/prune-audit-logs/SKILL.md | Prune .claude/audit_logs JSONL files (keep N days; dry-run by default) |  |
| P3-OPT | repo-importer | skills/repo-importer/SKILL.md | Import an existing repository into at. Auto-detects languages, package managers, linters, formatters, type checkers, tes | Merge into one import wizard; avoid duplicate flows. |
| P3-OPT | retrospective | skills/retrospective/SKILL.md | Generate a controlled retrospective from a session (quality/compliance/docs outcomes) and propose improvements to rules/ |  |
| P3-OPT | session-auditor | skills/session-auditor/SKILL.md | Audit workflow sessions to evaluate quality, efficiency, and generate improvement recommendations. Supports parallel ana |  |
| P3-OPT | session-kpis | skills/session-kpis/SKILL.md | Generate per-session telemetry KPIs (files changed, tasks done, gate outcomes) and optionally roll up into docs/AGENTIC_ |  |
| P3-OPT | setup-audit-hooks | skills/setup-audit-hooks/SKILL.md | Install and configure at audit hooks (opt-in) for tool/session/subagent logging under .claude/audit_logs | Consolidate into one command (keep one name, keep other as alias). |
| P3-OPT | strategic-compact | skills/strategic-compact/SKILL.md | Suggests manual context compaction at logical workflow boundaries rather than arbitrary auto-compaction | Low value; drop unless users request. |
| P3-OPT | upgrade | skills/upgrade/SKILL.md | Upgrade project's at configuration to the latest plugin version. Audits schema, hooks, and rules for changes, creates ba |  |
