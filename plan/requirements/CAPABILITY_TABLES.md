# Capability Tables (at)

This document is a **capability checklist** for the rebuilt `at` Claude Code plugin.

Goal: for each capability, define **what it is**, **where it is implemented**, and **how to verify it** (preferably via deterministic scripts + session artifacts).

## How to use this document

- Treat each row as a requirement with a clear “definition of done”.
- A capability is “Done” only when:
  - the referenced components exist (skills/agents/scripts/schemas/hooks), and
  - verification passes (commands/artifacts), and
  - failure modes are sane (blocked vs fail-open) per the hook/gate intent.

## Conventions

- **Phase**: `P0` Foundations, `P1` Kernel, `P2` Gates, `P3` Advanced.
- **Session artifacts**: files under `SESSION_DIR` (e.g., `.session/<id>/...`).
- **Config overlay**: repo-owned config under `.claude/` (e.g., `.claude/project.yaml`).
- **Templates**: follow `references/skills-template.md` and `references/agents-template.md`.

---

## A) Plugin Packaging & Repository Layout

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-PLUG-001 | P0 | Plugin manifest exists and uses default layout conventions | `plugin.json` | `claude --plugin-dir .` loads without errors; `/help` shows `/at:*` commands once added |
| [x] | CAP-PLUG-002 | P0 | Repo has canonical component directories | `agents/`, `skills/`, `scripts/`, `schemas/`, `hooks/`, `templates/`, `references/` | Directory tree matches `CLAUDE.md` contract |
| [x] | CAP-PLUG-003 | P0 | Reference library is present and used for implementation | `references/*` | Skill/agent files explicitly follow templates; no ad-hoc formats introduced |
| [ ] | CAP-PLUG-004 | P0 | Plugin has a stable public API surface (command names) | `skills/*/SKILL.md` | Command list is documented; renames avoided or handled via aliases |

---

## B) Versioning & Change Discipline

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-VERS-001 | P0 | Plugin version is authoritative and discoverable | `plugin.json`, `VERSION` | `VERSION` matches `plugin.json.version` |
| [x] | CAP-VERS-002 | P0 | Consistent per-file version metadata (agents/skills/scripts) | headers/frontmatter; `CLAUDE.md` guidance | Version bump updates all required headers consistently |
| [x] | CAP-VERS-003 | P0 | Automated version bump tool exists (no manual drift) | `scripts/dev/add_version_headers.py` (or equivalent) | Running the script updates headers/frontmatter in a deterministic way |

---

## C) Project Overlay Bootstrap (`/at:init-project`)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-OVER-001 | P1 | Bootstrap overlay in an empty repo | `skills/init-project/SKILL.md`, `scripts/init_project.py`, `templates/**` | Creates `.claude/project.yaml`, baseline rules, docs scaffolding, and prints what changed |
| [x] | CAP-OVER-002 | P1 | Idempotent bootstrap (safe re-run) | same as above | Re-running does not overwrite user-owned files unless explicit `--force` |
| [x] | CAP-OVER-003 | P1 | One canonical docs registry name and format | `docs/DOCUMENTATION_REGISTRY.json` | Registry exists and validates; no `docs/REGISTRY.json` drift |
| [x] | CAP-OVER-004 | P1 | Sessions dir is configurable and defaulted | `.claude/project.yaml` → `workflow.sessions_dir` | Sessions are created under configured dir |

---

## D) Configuration (`.claude/project.yaml`) + Schema + Parsing

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-CONF-001 | P0 | Minimal YAML parser supports the config subset we need | `scripts/lib/simple_yaml.py` | Parses config examples used by templates and docs |
| [x] | CAP-CONF-002 | P0 | Project config schema exists | `schemas/project.schema.json` | `doctor` (or a validator) can validate config against schema |
| [x] | CAP-CONF-003 | P1 | Docs registry requirement is configurable (onboarding-friendly) | `.claude/project.yaml`: `docs.require_registry` | New repos can run deliver with `require_registry=false` and later tighten rules |
| [x] | CAP-CONF-004 | P1 | Policies exist for secrets blocking | `.claude/project.yaml`: `policies.forbid_secrets_globs` | Context builders and policy hooks respect it |
| [ ] | CAP-CONF-005 | P1 | LSP requirement is configurable and has fallback policy | `.claude/project.yaml`: `lsp.required` (+ fallback mode) | CI/dev can choose `fail|warn|skip` behavior |

---

## E) Sessions (always-on artifacts)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-SESS-001 | P1 | Create a new session directory deterministically | `scripts/session/create_session.py` | Creates `session.json`, `inputs/request.md`, log dir; stable naming |
| [x] | CAP-SESS-002 | P1 | Resume by session id or directory | `skills/run/SKILL.md`, `scripts/session/create_session.py` | `/at:run <session-id>` resumes correctly without redoing completed work unnecessarily |
| [x] | CAP-SESS-003 | P1 | Session progress report exists (JSON + MD) | `scripts/session/session_progress.py` | Writes `status/session_progress.json` and `.md` |
| [x] | CAP-SESS-004 | P1 | List sessions | `scripts/session/list_sessions.py`, `skills/sessions/SKILL.md` | Lists sessions under configured sessions dir |
| [ ] | CAP-SESS-005 | P2 | Resume from a specific phase/gate | `/at:run --from-phase <phase>` design | Can rerun quality gate only, without rerunning planning |
| [x] | CAP-SESS-006 | P2 | Rollback restores checkpoint cleanly | `scripts/checkpoint/*`, `/at:run --rollback` | Git state restored to pre-implementation checkpoint |
| [ ] | CAP-SESS-007 | P3 | Session retention cleanup | `scripts/maintenance/cleanup_sessions.py` | Can prune old sessions by age/count (dry-run supported) |

---

## F) Planning Contract (`planning/actions.json`)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-PLAN-001 | P0 | `actions.json` schema exists and is the single source of truth | `schemas/actions.schema.json` | Planner uses it; validators enforce it; examples never drift |
| [x] | CAP-PLAN-002 | P1 | Action planner produces valid plan artifacts | `agents/action-planner.md` | Writes `planning/actions.json`, `planning/REQUIREMENT_TRACEABILITY_MATRIX.md`, `planning/VERIFICATION_CHECKLIST.md` |
| [x] | CAP-PLAN-003 | P1 | Deterministic plan validation fails fast | `scripts/validate/validate_actions.py` | Non-zero exit with actionable error list |
| [x] | CAP-PLAN-004 | P1 | Default parallel execution is enabled in plans | `actions.json.parallel_execution.enabled=true` | Plan validation enforces required `file_scope.writes[]` per code task |
| [x] | CAP-PLAN-005 | P1 | `file_scope.writes[]` forbids globs (exact files or dir prefixes) | validator + schema guidance | Plans with globs in writes are rejected |
| [x] | CAP-PLAN-006 | P1 | Acceptance criteria verifications support `file`, `grep`, `command`, `lsp` | `schemas/actions.schema.json` | Validation rejects wrong field names; LSP specs are complete |
| [x] | CAP-PLAN-007 | P1 | Doc ids for task context are validated when required | `scripts/context/build_task_contexts.py` | Missing/unknown doc ids block task context generation (when require_registry=true) |
| [x] | CAP-PLAN-008 | P1 | Invalid `planning/actions.json` writes are blocked at tool-time (optional but recommended) | `scripts/hooks/validate_actions_write.py` + hooks config | Editing `planning/actions.json` to invalid shape is blocked immediately |

---

## G) Context Minimalism (context pack + task slices)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-CTX-001 | P1 | Context pack is built deterministically | `scripts/context/build_context_pack.py` | Writes `inputs/context_pack.md` (and JSON manifest if needed) |
| [x] | CAP-CTX-002 | P1 | Context pack respects forbidden secret globs | `scripts/lib/path_policy.py`, build script | Forbidden files are never embedded |
| [x] | CAP-CTX-003 | P1 | Per-task context slices are built deterministically | `scripts/context/build_task_contexts.py` | Writes `inputs/task_context/<task_id>.md` + `inputs/task_context_manifest.json` |
| [x] | CAP-CTX-004 | P1 | Task contexts include only required docs (doc_ids and optional doc_sections) | task context builder | Extracted sections match headings; full-doc inclusion is explicit |
| [x] | CAP-CTX-005 | P1 | Task context manifest includes per-task `file_scope` for hooks | manifest writer | `enforce_file_scope.py` can read writes allowlist from manifest |

---

## H) Execution (subagents) + File Scope Enforcement

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-EXEC-001 | P1 | Implementor subagent is SRP and plan-scoped | `agents/implementor.md` | Only modifies assigned non-test code; writes per-task artifact |
| [x] | CAP-EXEC-002 | P1 | Tests-builder subagent is SRP and plan-scoped | `agents/tests-builder.md` | Only modifies assigned test code; writes per-task artifact |
| [x] | CAP-EXEC-003 | P1 | Per-task artifacts are machine-checkable and stable | `schemas/task_artifact.schema.json`, `scripts/validate/validate_task_artifacts.py` | Validator parses artifacts and checks required fields |
| [x] | CAP-EXEC-004 | P1 | Out-of-scope writes are blocked at tool-time | `scripts/hooks/enforce_file_scope.py` + hooks config | Attempting to edit a non-writable file is denied with a precise message |
| [x] | CAP-EXEC-005 | P2 | Changed files can be checked against plan scope (git best-effort) | `scripts/validate/validate_changed_files.py` | When in a git repo, violations fail the gate; otherwise warns |

---

## I) Parallel Execution (default ON)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-PAR-001 | P1 | Orchestrator executes `parallel_execution.groups` with concurrency limit | `skills/run/SKILL.md` | Parallel groups run without exceeding `max_concurrent_agents` |
| [x] | CAP-PAR-002 | P1 | Parallel grouping prevents write-scope overlap within a group | plan validation + file scope discipline | Validator rejects overlapping writes across tasks in same group |
| [x] | CAP-PAR-003 | P2 | Parallel conformance gate validates task attribution + overlaps | `scripts/validate/parallel_conformance.py` | Writes `quality/parallel_conformance_report.{json,md}` |

---

## J) Gates (deterministic evidence)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-GATE-001 | P2 | Plan adherence gate runs declared verifications | `scripts/validate/plan_adherence.py` | Writes `quality/plan_adherence_report.{json,md}` and sets `ok` correctly |
| [x] | CAP-GATE-002 | P2 | Quality suite runner executes configured commands deterministically | `scripts/quality/run_quality_suite.py` | Writes `quality/quality_report.{json,md}` + command logs |
| [x] | CAP-GATE-003 | P2 | Conditional commands (e2e) can skip without failing | quality runner + config | Report marks `skip` with reason; overall gate behavior matches policy |
| [ ] | CAP-GATE-004 | P2 | LSP verification support (optional early, required if used) | `agents/lsp-verifier.md`, `scripts/validate/lsp_gate.py` | LSP checks declared in plan produce evidence and pass gate |
| [x] | CAP-GATE-005 | P2 | Compliance gate produces APPROVE/REJECT with evidence pointers | `agents/compliance-checker.md` | `compliance/COMPLIANCE_VERIFICATION_REPORT.md` contains a clear decision marker |
| [x] | CAP-GATE-006 | P2 | Docs gate validates registry + docs summary | `scripts/validate/docs_gate.py` | Writes `documentation/docs_gate_report.{json,md}` |
| [ ] | CAP-GATE-007 | P2 | Dry-run mode produces plan-only report and exits safely | `scripts/workflow/generate_dry_run_report.py` | Writes `final/dry_run_report.{json,md}`; no repo changes |
| [x] | CAP-GATE-008 | P2 | Rollback mode restores checkpoint and stops | `scripts/checkpoint/restore_checkpoint.py` | Restores git state and writes a clear report |

---

## K) Hooks (component-like validators)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-HOOK-001 | P1 | Plugin hook config exists and is minimal | `hooks/hooks.json` | Hooks run fast; only enforce invariants |
| [x] | CAP-HOOK-002 | P1 | SubagentStop enforces artifact existence and blocks missing outputs | `scripts/hooks/on_subagent_stop.py` | Missing required artifacts triggers retry; circuit breaker prevents infinite loops |
| [x] | CAP-HOOK-003 | P1 | PreToolUse enforces file scope on Write/Edit | `scripts/hooks/enforce_file_scope.py` | Deny includes allowed `file_scope.writes[]` in message |
| [x] | CAP-HOOK-004 | P1 | PostToolUse can validate `planning/actions.json` writes | `scripts/hooks/validate_actions_write.py` | Invalid writes are blocked with actionable schema error |
| [x] | CAP-HOOK-005 | P3 | SessionStart can inject learning context (best-effort) | `scripts/hooks/sessionstart_learning_context.py`, `scripts/learning/install_learning_hooks.py` | If snippet exists, it is injected (best-effort); hook fails open on errors |
| [ ] | CAP-HOOK-006 | P3 | Setup hook performs safe maintenance (e.g., prune audit logs) | `scripts/hooks/on_setup.py` | Runs only on explicit maintenance trigger; never blocks normal work |

---

## L) Security & Policy (secrets + dangerous commands)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-POL-001 | P2 | Policy hooks can be installed (project or user scope) | `skills/setup-policy-hooks/SKILL.md`, `scripts/hooks/install_policy_hooks.py` | Re-run is idempotent; settings updated safely |
| [x] | CAP-POL-002 | P2 | Policy hooks block `.env` and configured secret globs | `scripts/hooks/policy_pre_tool_use.py` | Attempts to Read/Edit `.env` are blocked; `.env.sample` is allowed |
| [x] | CAP-POL-003 | P2 | Policy hooks block destructive commands | `scripts/hooks/policy_pre_tool_use.py` | `rm -rf` / `git push --force` attempts are blocked |
| [x] | CAP-POL-004 | P2 | Context builders respect the same secret globs | context scripts + `lib/path_policy.py` | Forbidden docs/files are never embedded |

---

## M) Audit & Observability (opt-in)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-AUDIT-001 | P3 | Audit hooks installer exists and is idempotent | `scripts/audit/install_audit_hooks.py`, `skills/setup-audit-hooks/SKILL.md` | Re-run does not duplicate hook entries (managed tag pruning) |
| [x] | CAP-AUDIT-002 | P3 | Tool usage JSONL logs are captured | `scripts/hooks/audit_{pre,post}_tool_use.py` | `.claude/audit_logs/tools.jsonl` written |
| [x] | CAP-AUDIT-003 | P3 | Session/subagent lifecycle JSONL logs are captured | `scripts/hooks/audit_session_lifecycle.py`, `scripts/hooks/audit_subagent_stop.py` | `.claude/audit_logs/lifecycle.jsonl`, `.claude/audit_logs/subagents.jsonl` written |
| [x] | CAP-AUDIT-004 | P3 | Optional trace capture is explicit and off-by-default | `AT_AUDIT_TRACES_ENABLED` env var | When enabled, tool input/output is included; otherwise omitted |
| [x] | CAP-AUDIT-005 | P3 | Audit pruning exists (dry-run default) | `scripts/audit/prune_audit_logs.py`, `skills/prune-audit-logs/SKILL.md` | Old logs can be pruned safely (dry-run default) |
| [x] | CAP-AUDIT-006 | P3 | Audit analyzer produces a report | `scripts/audit/analyze_audit_logs.py`, `skills/audit-report/SKILL.md` | Generates `.claude/audit_reports/audit_report.{json,md}` |

---

## N) Learning / Memory (persistent, low-risk)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-LEARN-001 | P3 | Learning dir exists and is write-scoped | `scripts/init_project.py`, `.claude/agent-team/learning/` | All learning writes stay inside this dir |
| [x] | CAP-LEARN-002 | P3 | Learning update from session | `scripts/learning/update_learning_state.py`, `skills/learning-update/SKILL.md` | Writes `STATUS.md` + per-session digests |
| [x] | CAP-LEARN-003 | P3 | Learning status command exists | `scripts/learning/learning_status.py`, `skills/learning-status/SKILL.md` | Prints/exports current learning snapshot |
| [x] | CAP-LEARN-004 | P3 | SessionStart learning context injection (optional) | `scripts/hooks/sessionstart_learning_context.py`, `skills/setup-learning-hooks/SKILL.md` | Injects a bounded excerpt (best-effort); fails open |

---

## O) Telemetry (KPIs)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-TEL-001 | P3 | Deterministic KPI extraction per session | `scripts/telemetry/build_session_kpis.py`, `skills/telemetry-session-kpis/SKILL.md` | Writes `telemetry/session_kpis.{json,md}` under session |
| [x] | CAP-TEL-002 | P3 | Optional rollup for team visibility | `scripts/telemetry/rollup_kpis.py`, `skills/telemetry-rollup/SKILL.md` | Writes `<sessions_dir>/telemetry_rollup.{json,md}` |

---

## P) Project Packs & Enforcement (optional)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-PACK-001 | P3 | Project pack installer exists (rules + optional enforcement) | `scripts/project_pack/install_project_pack.py`, `skills/install-project-pack/SKILL.md` | Installs `.claude/at/**` safely (conservative defaults) |
| [x] | CAP-PACK-002 | P3 | Enforcement runner is deterministic and repo-local | `.claude/at/scripts/run_enforcements.py` (installed by project pack) | Can run in CI without plugin access |
| [x] | CAP-PACK-003 | P3 | Quality gate integrates enforcement when configured | `scripts/quality/run_quality_suite.py`, `agents/quality-gate.md` | `quality/enforcement_report.json` produced when runner exists |

---

## Q) Upgrade / Import / Maintenance (optional)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [x] | CAP-UPG-001 | P3 | Upgrade overlay to latest version | `scripts/upgrade/upgrade_project.py`, `skills/upgrade-project/SKILL.md` | Conservative updates; dry-run default |
| [ ] | CAP-IMP-001 | P3 | Repo import wizard (optional) | `scripts/import/*`, `skills/import-*` | Generates a valid `.claude/project.yaml` + docs scaffolding |
| [x] | CAP-MAINT-001 | P3 | Uninstall hooks helper exists | `skills/uninstall-hooks/SKILL.md`, `skills/uninstall-audit-hooks/SKILL.md`, `skills/uninstall-learning-hooks/SKILL.md` | Removes at-managed hooks cleanly (managed tag pruning) |
| [x] | CAP-MAINT-002 | P3 | Cleanup sessions helper exists | `scripts/maintenance/cleanup_sessions.py`, `skills/cleanup-sessions/SKILL.md` | Prunes sessions by policy (dry-run supported) |

---

## R) Cross-cutting Non-functional Requirements (NFRs)

| Done | ID | Phase | Capability | Implementation Pointers | Verification / Evidence |
|---|---|---:|---|---|---|
| [ ] | CAP-NFR-001 | P0 | Deterministic scripts: explicit I/O, no network required | `scripts/**/*.py` discipline | Scripts run offline; artifacts are stable and machine-readable |
| [ ] | CAP-NFR-002 | P0 | Path safety: repo-relative normalization prevents traversal | `scripts/lib/path_policy.py` | Attempts to use `..` / absolute paths are rejected |
| [ ] | CAP-NFR-003 | P1 | Hooks are fast and safe; failure modes are intentional | `hooks/hooks.json`, hook scripts | Hook timeouts configured; fail-open vs block is appropriate |
| [ ] | CAP-NFR-004 | P1 | SRP and DRY enforced structurally | agents/skills/templates/references | No duplicate docs agents; no duplicate skill names; shared libs used |
| [ ] | CAP-NFR-005 | P2 | Sensitive data is not embedded into session artifacts by default | context builders + policies | Forbidden globs respected; audit traces are opt-in |
