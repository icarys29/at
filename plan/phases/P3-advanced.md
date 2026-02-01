# P3 — Advanced (audit, learning, telemetry, project packs)

## Outcome

Add advanced capabilities once the core is stable:
- audit hooks + analytics
- persistent learning/memory
- session KPIs/telemetry
- repo-specific project packs + enforcement scripts
- upgrade/import tooling

## References (read first; keep context lean)

- Template: `references/skills-template.md`
- Template: `references/agents-template.md`
- Claude Code hooks: `references/claude-code/hooks-guidelines.md`
- Claude Code memory/rules: `references/claude-code/memory-and-rules.md`
- Debugging methodology (for triage/root-cause work): `references/debugging/systematic-debugging.md`

## Scope (include)

### Audit hooks + analysis

- uv-scripted hooks for:
  - tool usage audit (PreToolUse/PostToolUse)
  - session lifecycle audit (SessionStart/SessionEnd)
  - subagent lifecycle audit (SubagentStop)
- analyzer scripts + report generator
- pruning tool for audit logs

### Learning/memory

- `.claude/agent-team/learning/` scaffolding
- update scripts + sessionstart context injection hook (best-effort, fail-open)

### Telemetry

- `telemetry/session_kpis.{json,md}` per session
- optional rollups

### Project packs + enforcement (optional)

- “project pack interviewer” that can install:
  - `.claude/rules/project/**`
  - `.claude/at/enforcement.json`
  - portable enforcement scripts under `.claude/at/scripts/`

## Non-goals

- Do not expand the core kernel contract surface area.
- No heavy third-party dependencies; keep portability.

## Work Items

### P3-01 Audit subsystem

Deliverables:
- hooks installer + audit JSONL schema
- analyzer producing a stable markdown + json report

Acceptance:
- Opt-in, sensitive by default (no traces unless explicitly enabled).

### P3-02 Learning subsystem

Deliverables:
- `STATUS.md`, per-session digests, rollups
- optional ADR stubs

Acceptance:
- Writes only under learning dir; never touches repo code.

### P3-03 Telemetry subsystem

Deliverables:
- deterministic KPI extraction based on session artifacts

Acceptance:
- Does not require network access; best-effort when artifacts missing.

### P3-04 Project pack + enforcement

Deliverables:
- optional “hex boundaries” enforcement and a runner

Acceptance:
- Enforcement runs deterministically and integrates with quality gate when present.

### P3-05 Upgrade/import utilities

Deliverables:
- upgrade script for overlay changes
- import wizard only if it reduces onboarding friction in practice

Acceptance:
- Conservative, idempotent, and safe by default.

## Exit Criteria

- Optional subsystems are installable, useful, and do not destabilize the kernel.
