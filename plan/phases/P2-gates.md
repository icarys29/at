# P2 — Gates (deterministic quality/compliance/docs)

## Outcome

Turn the kernel into a reliable “done means gates pass” workflow:
- deterministic plan adherence gate
- deterministic parallel conformance gate
- deterministic quality suite runner (format/lint/test/build)
- compliance gate (binary decision with evidence)
- docs gate (registry + coverage rules)
- rollback/checkpoint safety
- policy hooks for secrets + destructive command blocking

## References (read first; keep context lean)

- Template: `references/skills-template.md`
- Template: `references/agents-template.md`
- Claude Code hooks: `references/claude-code/hooks-guidelines.md`
- Claude Code memory/rules: `references/claude-code/memory-and-rules.md`

## Scope (include)

### Deterministic scripts

- `scripts/validate/plan_adherence.py`
- `scripts/validate/parallel_conformance.py`
- `scripts/quality/run_quality_suite.py`
- `scripts/checkpoint/create_checkpoint.py`
- `scripts/checkpoint/restore_checkpoint.py`
- `scripts/validate/docs_gate.py`
- (optional in P2) `scripts/validate/lsp_gate.py` + `lsp-verifier` agent (or defer to P2.5)

### Agents

- `quality-gate` (runs deterministic quality runner + minimal remediation)
- `compliance-checker` (APPROVE/REJECT with evidence pointers)
- `docs-keeper` (single docs agent; remove deprecated docs agents)

### Skills (consolidate names)

- one canonical command for policy hooks install (`/at:setup-policy-hooks`)
- uninstall hooks tool (`/at:uninstall-hooks`)
- optional: `resolve-failed-quality` (rerun only failing quality command)

## Work Items

### P2-01 Rollback + safety checkpoint

Deliverables:
- checkpoint scripts
- `/at:run --rollback <session>` behavior

Acceptance:
- A failed workflow can be rolled back to a pre-implementation checkpoint deterministically.

### P2-02 Plan adherence gate

Deliverables:
- plan adherence report `{json,md}` under `quality/`
- integration into `/at:run` deliver path

Acceptance:
- Failing acceptance criteria verifications are reported with actionable details.

### P2-03 Parallel conformance gate

Deliverables:
- conformance report `{json,md}` under `quality/`

Acceptance:
- Detects overlaps and out-of-scope changes (via task artifacts + git diff when available).

### P2-04 Quality suite runner (deterministic)

Deliverables:
- `quality/quality_report.{json,md}`
- per-command logs under `quality/command_logs/`

Acceptance:
- Uses `.claude/project.yaml` command config.
- Supports conditional/skip logic for e2e commands (`requires_env`, `requires_files`).

### P2-05 Compliance gate

Deliverables:
- `compliance/COMPLIANCE_VERIFICATION_REPORT.md`

Acceptance:
- Decision is binary and evidence-based.
- Integrates `validate_changed_files.py` best-effort check when git is available.

### P2-06 Docs update + docs gate

Deliverables:
- `documentation/docs_summary.{json,md}`
- `documentation/docs_gate_report.{json,md}`

Acceptance:
- Registry validation is deterministic.
- Coverage rules can be enforced when configured, but onboarding remains possible (registry requirement configurable).
- Standardize on **one registry**: `docs/DOCUMENTATION_REGISTRY.json` (no `docs/REGISTRY.json` drift).

### P2-07 Policy hooks (uv-scripted)

Deliverables:
- install script under a single canonical skill
- `PreToolUse` hook blocking:
  - forbidden secret files (`policies.forbid_secrets_globs`)
  - destructive shell commands (`rm -rf`, `git push --force`, etc.)

Acceptance:
- Hooks are optional to install but easy/idiot-proof; installed hooks are deterministic and dependency-free.
- Hook install skills follow `references/skills-template.md` (short) and the hook scripts follow `references/claude-code/hooks-guidelines.md` (fast, safe, untrusted input handling).

## Exit Criteria

- `deliver` becomes “binary”: if gates fail, workflow stops with remediation steps.
- Default parallel execution remains safe and enforced through gates + hooks.
