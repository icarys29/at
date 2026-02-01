# User Stories (at)

This document captures the user-facing stories that the rebuilt `at` plugin should support.

These stories are meant to:
- guide implementation sequencing (map to phases `P0..P3`)
- provide traceability to capabilities (`plan/requirements/CAPABILITY_TABLES.md`)
- serve as a stable reference for what “done” means for the plugin’s UX

## Personas

- **Developer**: uses `/at:*` to ship features/fixes with guardrails.
- **Tech Lead**: cares about repeatability, quality evidence, and auditability.
- **Security Lead**: cares about preventing secrets exposure and dangerous actions.
- **Maintainer**: evolves the plugin safely (versioning, templates, minimal drift).

## Index (high-level)

| Status | ID | Title | Persona | Phase | Related Capabilities |
|---|---|---|---|---:|---|
| In progress | US-INIT-001 | Load plugin + discover commands | Developer | P0 | CAP-PLUG-001, CAP-PLUG-004 |
| Done | US-INIT-002 | Bootstrap overlay (`/at:init-project`) | Developer | P1 | CAP-OVER-001..003 |
| Done | US-DOCTOR-001 | Validate repo readiness (`/at:doctor`) | Developer | P1 | CAP-CONF-001..005 |
| In progress | US-DELIVER-001 | Deliver workflow end-to-end | Developer | P1 | CAP-SESS-001..003, CAP-PLAN-002..004, CAP-CTX-001..005, CAP-EXEC-001..004 |
| In progress | US-DELIVER-002 | Parallel execution by default | Developer | P1 | CAP-PLAN-004, CAP-PAR-001..002 |
| In progress | US-GATE-001 | Deterministic gates (quality/compliance/docs) | Tech Lead | P2 | CAP-GATE-001..006 |
| Done | US-SEC-001 | Policy hooks prevent secrets exposure | Security Lead | P2 | CAP-POL-001..004 |
| Not started | US-AUDIT-001 | Audit hooks capture tool/session/subagent events | Tech Lead | P3 | CAP-AUDIT-001..006 |
| Not started | US-LEARN-001 | Persistent learning/memory updates | Developer | P3 | CAP-LEARN-001..004 |

---

## Onboarding / Setup

### US-INIT-001 — Load plugin + discover commands

- Persona: Developer
- Phase: P0
- Status: In progress
- Story: As a developer, I want to load the plugin and discover `/at:*` commands, so that I can use it without guessing.
- Acceptance:
  - Running `claude --plugin-dir .` loads without errors.
  - `/help` (or command discovery UI) lists the plugin commands once skills exist.
- Related: CAP-PLUG-001, CAP-PLUG-004

### US-INIT-002 — Bootstrap overlay (`/at:init-project`)

- Persona: Developer
- Phase: P1
- Status: Done
- Story: As a developer, I want to bootstrap `.claude/project.yaml`, baseline rules, and docs scaffolding, so that `deliver` has the required overlay.
- Acceptance:
  - Creates `.claude/project.yaml` from template.
  - Creates docs scaffolding including `docs/DOCUMENTATION_REGISTRY.json`.
  - Re-run is safe and idempotent unless `--force`.
- Related: CAP-OVER-001..004

### US-DOCTOR-001 — Validate repo readiness (`/at:doctor`)

- Persona: Developer
- Phase: P1
- Status: Done
- Story: As a developer, I want a deterministic readiness check, so that I can fix missing overlay/config issues before running deliver.
- Acceptance:
  - Reports whether `.claude/project.yaml` exists and is parseable.
  - Validates key config fields (project/workflow/commands).
  - If `docs.require_registry=true`, validates that the docs registry exists and has usable `docs[]` entries.
  - Exits non-zero on failure with actionable hints.
- Related: CAP-CONF-001..005

### US-INIT-003 — Install policy hooks (opt-in)

- Persona: Security Lead
- Phase: P2
- Status: Done
- Story: As a security lead, I want an easy way to install policy hooks, so that secrets and dangerous commands are blocked by default in daily use.
- Acceptance:
  - `/at:setup-policy-hooks` installs hooks in project scope by default (or user scope when requested).
  - Re-run is idempotent; no duplicate hook entries.
- Related: CAP-POL-001

### US-INIT-004 — Uninstall hooks cleanly

- Persona: Developer
- Phase: P3
- Status: Not started
- Story: As a developer, I want to remove installed hooks cleanly, so that I can troubleshoot or revert policy/audit tooling safely.
- Acceptance:
  - Hook config entries are removed from settings.
  - Hook script files are removed only when explicitly requested.
- Related: CAP-MAINT-001

---

## Deliver Workflow (core UX)

### US-DELIVER-001 — Deliver workflow end-to-end

- Persona: Developer
- Phase: P1
- Status: In progress
- Story: As a developer, I want to run `/at:run "request"` and get a session-backed plan and execution, so that changes are repeatable and auditable.
- Acceptance:
  - A `SESSION_DIR` is created with `session.json` and `inputs/request.md`.
  - Planner writes a valid `planning/actions.json` (+ checklists).
  - Task contexts are generated and used by implementor/tests tasks.
  - Implementation/test tasks write per-task artifacts.
- Related: CAP-SESS-001..003, CAP-PLAN-002..003, CAP-CTX-001..005, CAP-EXEC-001..003

### US-DELIVER-002 — Parallel execution by default (safe)

- Persona: Developer
- Phase: P1
- Status: In progress
- Story: As a developer, I want code tasks to run in parallel by default when safe, so that I get faster iteration without scope conflicts.
- Acceptance:
  - Plan defaults `parallel_execution.enabled=true`.
  - All code tasks include `file_scope.writes[]` and they do not overlap within a group.
  - Parallel conformance gate exists by P2.
- Related: CAP-PLAN-004..005, CAP-PAR-001..003

### US-DELIVER-003 — Resume a session

- Persona: Developer
- Phase: P1
- Status: In progress
- Story: As a developer, I want to resume a stopped session by id or directory, so that I can continue without losing context.
- Acceptance:
  - `/at:run <session-id>` resumes and updates `status/session_progress.*`.
  - The orchestrator does not redo completed phases unless requested.
- Related: CAP-SESS-002..003

### US-DELIVER-004 — Dry-run plan (no repo changes)

- Persona: Tech Lead
- Phase: P2
- Status: Not started
- Story: As a tech lead, I want a dry-run plan/report, so that I can review scope before code changes happen.
- Acceptance:
  - Dry-run creates planning artifacts and a dry-run report.
  - No repo files are modified.
- Related: CAP-GATE-007

### US-DELIVER-005 — Rollback after bad implementation

- Persona: Developer
- Phase: P2
- Status: Done
- Story: As a developer, I want rollback support for a session, so that I can undo a wrong direction quickly.
- Acceptance:
  - A checkpoint exists before implementation.
  - `--rollback` restores that checkpoint and stops.
- Related: CAP-SESS-006, CAP-GATE-008

### US-DELIVER-006 — Rerun a specific gate/phase

- Persona: Developer
- Phase: P2
- Status: Not started
- Story: As a developer, I want to rerun only the failing gate (e.g., quality), so that remediation is fast and deterministic.
- Acceptance:
  - `--from-phase quality` reruns only quality-related steps.
  - Session progress reflects the rerun outcome.
- Related: CAP-SESS-005

---

## Planning & Contracts

### US-PLAN-001 — Plan is schema-valid and actionable

- Persona: Developer
- Phase: P1
- Status: In progress
- Story: As a developer, I want plans to be schema-valid and actionable for subagents, so that execution is deterministic.
- Acceptance:
  - `planning/actions.json` validates against `schemas/actions.schema.json`.
  - Validation errors are actionable and surfaced early (ideally at write-time).
- Related: CAP-PLAN-001..003, CAP-PLAN-008

### US-PLAN-002 — Plan includes explicit file scope and verifications

- Persona: Tech Lead
- Phase: P1
- Status: In progress
- Story: As a tech lead, I want each task to declare file scope and verifications, so that scope and “done” are enforceable.
- Acceptance:
  - Each task declares `file_scope.allow` and (when parallel) `file_scope.writes`.
  - Acceptance criteria include verifications (`file/grep/command/lsp`) where meaningful.
- Related: CAP-PLAN-005..006

---

## Scope Enforcement (safety)

### US-SCOPE-001 — Out-of-scope edits are blocked

- Persona: Security Lead
- Phase: P1
- Status: In progress
- Story: As a security lead, I want out-of-scope edits blocked at tool time, so that parallel work and plan compliance are enforceable.
- Acceptance:
  - Attempting to write/edit outside `file_scope.writes[]` is denied with a clear reason.
  - Session artifacts remain writable.
- Related: CAP-EXEC-004, CAP-HOOK-003

---

## Gates (quality/compliance/docs)

### US-GATE-001 — Plan adherence gate produces deterministic evidence

- Persona: Tech Lead
- Phase: P2
- Status: Done
- Story: As a tech lead, I want a deterministic plan adherence report, so that we can see exactly what passed/failed.
- Acceptance:
  - Gate writes JSON + Markdown.
  - Failures cite the task/criterion and details.
- Related: CAP-GATE-001

### US-GATE-002 — Quality gate runs repo toolchain deterministically

- Persona: Developer
- Phase: P2
- Status: Done
- Story: As a developer, I want quality commands to run deterministically and produce logs, so that failures are actionable.
- Acceptance:
  - Report includes per-command stdout/stderr paths.
  - Conditional commands can skip with reason.
- Related: CAP-GATE-002..003

### US-GATE-003 — Compliance checker is independent and evidence-based

- Persona: Tech Lead
- Phase: P2
- Status: Done
- Story: As a tech lead, I want an independent compliance decision with evidence pointers, so that we don’t ship unverified work.
- Acceptance:
  - Report contains APPROVE/REJECT marker.
  - Evidence references artifacts/commands/output.
- Related: CAP-GATE-005

### US-GATE-004 — Docs gate enforces docs-as-contract

- Persona: Tech Lead
- Phase: P2
- Status: In progress
- Story: As a tech lead, I want docs validation, so that changes are documented and future planning remains accurate.
- Acceptance:
  - Registry is validated.
  - Coverage rules (if enabled) enforce required docs for changed files. (Deferred: coverage rules enforcement not implemented yet.)
- Related: CAP-GATE-006

---

## Security / Policy

### US-SEC-001 — Block secrets file access

- Persona: Security Lead
- Phase: P2
- Status: Done
- Story: As a security lead, I want `.env` and secret paths blocked, so that accidental leakage is prevented.
- Acceptance:
  - Reading or editing `.env` is blocked.
  - `.env.sample` / templates remain allowed.
- Related: CAP-POL-002

### US-SEC-002 — Block dangerous destructive commands

- Persona: Security Lead
- Phase: P2
- Status: Done
- Story: As a security lead, I want destructive shell commands blocked, so that accidental repo damage is prevented.
- Acceptance:
  - `rm -rf` and `git push --force` are blocked.
- Related: CAP-POL-003

---

## Audit / Observability (opt-in)

### US-AUDIT-001 — Capture tool/session/subagent events

- Persona: Tech Lead
- Phase: P3
- Status: Not started
- Story: As a tech lead, I want audit logs of tool usage and lifecycle events, so that workflows are observable when needed.
- Acceptance:
  - JSONL logs exist under `.claude/audit_logs/`.
  - Trace capture is opt-in.
- Related: CAP-AUDIT-001..004

---

## Learning / Memory (opt-in by config)

### US-LEARN-001 — Update persistent learning from sessions

- Persona: Developer
- Phase: P3
- Status: Not started
- Story: As a developer, I want the plugin to maintain a small, persistent memory, so that future work starts with better context.
- Acceptance:
  - Learning updates write only under `.claude/agent-team/learning/`.
  - SessionStart can inject a bounded excerpt when enabled.
- Related: CAP-LEARN-001..004

---

## Maintainer Stories (keep the plugin healthy)

### US-MAINT-001 — Add new skills/agents without drift

- Persona: Maintainer
- Phase: P0+
- Status: In progress
- Story: As a maintainer, I want a clear template and discipline for new skills/agents, so that the plugin stays consistent and DRY.
- Acceptance:
  - New skills follow `references/skills-template.md` and remain short (≤ 500 lines).
  - New agents follow `references/agents-template.md` and remain SRP-focused.
- Related: CAP-PLUG-003, CAP-NFR-004
