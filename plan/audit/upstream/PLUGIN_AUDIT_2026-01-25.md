# Plugin Architecture Audit

**Date**: 2026-01-25
**Auditor**: Claude Opus 4.5
**Scope**: Full adversarial review of at v0.7.2

---

## Executive Summary

The plugin demonstrates sophisticated engineering with its deterministic execution model and contract-driven design. However, there are structural issues that could undermine reliability and adoption:

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Design Flaws | 1 | 2 | 2 | 1 |
| Operational Risks | 0 | 2 | 2 | 1 |
| Missing Capabilities | 0 | 1 | 3 | 2 |
| **Total** | **1** | **5** | **7** | **4** |

**Most Critical Issue**: Docs registry coupling gates all execution on documentation infrastructure, which is backwards for adoption.

---

## 1. Fundamental Design Concerns

### 1.1 [CRITICAL] Docs Registry Coupling

**Severity**: Critical
**Component**: `validate_actions.py`, `build_task_contexts.py`

**Problem**: Every code task **must** declare `context.doc_ids[]` that exist in `DOCUMENTATION_REGISTRY.json`. This creates:

- Chicken-and-egg: New projects can't run `/at:run` until registry is populated
- Maintenance burden: Registry updates become blocking dependencies
- Brittleness: File moves/renames break the entire planning phase

**Evidence**:
- `agents/action-planner.md` requires doc_ids for all code tasks
- `scripts/validate_actions.py` fails if doc_ids don't resolve

**Recommendation**:
```yaml
# .claude/project.yaml
docs:
  require_registry: false  # Make optional
  fallback_context: "glob"  # Use glob patterns when registry incomplete
```

---

### 1.2 [HIGH] Binary Gates Without Gradation

**Severity**: High
**Component**: `agents/compliance-checker.md`

**Problem**: APPROVE/REJECT with no middle ground. If 9/10 acceptance criteria pass but 1 fails for a minor reason, the entire workflow is REJECTED.

**Impact**: Blocks pragmatic shipping of 90% correct work.

**Recommendation**:
```yaml
acceptance_criteria:
  - id: AC1
    severity: critical  # Block on failure
  - id: AC2
    severity: high      # Block on failure
  - id: AC3
    severity: medium    # Warn, don't block
  - id: AC4
    severity: low       # Informational
```

Add config:
```yaml
workflow:
  strict_mode: true  # false = only block on critical/high
```

---

### 1.3 [HIGH] No Rollback Mechanism

**Severity**: High
**Component**: `commands/run.md`

**Problem**: If implementation is fundamentally wrong, the only path is "fix in place" through remediation loops (max 2). No checkpoint/revert capability.

**Impact**: Bad architectural decisions require manual intervention outside the workflow.

**Recommendation**:
- Create git stash/branch before implementation phase
- Add `--rollback` flag: `at:run --rollback <session_id>`
- Implement phase checkpoints with restore capability

---

### 1.4 [MEDIUM] Orchestrator is Untestable Markdown

**Severity**: Medium
**Component**: `commands/run.md` (18,947 bytes)

**Problem**: 600+ lines of procedural specification in Markdown. Not testable, no type safety, fragile to model interpretation drift.

**Impact**: Debugging failures requires tracing through prose. One misinterpretation breaks the workflow.

**Recommendation**:
- Extract orchestration to Python state machine
- Keep Markdown as documentation, not implementation
- Add integration tests for workflow transitions

---

### 1.5 [MEDIUM] Final Reply Contracts are Unenforceable

**Severity**: Medium
**Component**: All agents (final message format)

**Problem**: Agents must emit specific YAML format in their final message (STATUS, SUMMARY, REPO_DIFF, SESSION_ARTIFACTS). No mechanism enforces this.

**Impact**: Parse failures, incomplete session artifacts, mysterious downstream gate failures.

**Recommendation**:
- Require agents write final state to file: `<session>/results/<task_id>.yaml`
- Validate file against schema before considering task complete
- Parse file, not natural language output

---

### 1.6 [LOW] Skills Cannot Be Programmatically Invoked

**Severity**: Low
**Component**: `skills/` (all skills)

**Problem**: Skills are user-invocable only. Agents can't call skills for reference/methodology.

**Impact**: Forces agents to embed copies of knowledge (duplication).

**Recommendation**:
- Create `skills/<skill>/reference.md` for agents to Read
- Or add `model-invocable: true` flag for lightweight skills

---

## 2. Operational Risks

### 2.1 [HIGH] Session Directory Pollution

**Severity**: High
**Component**: `.session/` directory

**Problem**: Every workflow creates a session. No cleanup mechanism.

**Impact**:
- Directory fills with hundreds of sessions
- Git history bloats if sessions are committed
- Disk space exhaustion on long-lived projects

**Recommendation**:
```yaml
workflow:
  session_retention_days: 7
  session_retention_count: 50  # Keep last N
```

Add `scripts/prune_sessions.py` for cleanup.

---

### 2.2 [HIGH] Policy Hooks are Opt-In

**Severity**: High
**Component**: `skills/policy-hooks-deployer/`

**Problem**: Security policies only activate if users run `/at:setup-policy-hooks`. Most won't.

**Impact**: `.env` files, secrets, dangerous commands unprotected by default.

**Recommendation**:
- Install policy hooks by default during `/at:init-project`
- Require explicit `policies.disable: true` to turn off
- Make `.env` protection the default

---

### 2.3 [MEDIUM] LSP Requirement Without Fallback

**Severity**: Medium
**Component**: `agents/lsp-verifier.md`, `scripts/lsp_gate.py`

**Problem**: If `lsp.required: true` but LSP server unavailable, verification fails hard.

**Impact**: CI environments, containers, new developers blocked.

**Recommendation**:
```yaml
lsp:
  required: true
  fallback: "warn"  # "fail" | "warn" | "skip"
```

---

### 2.4 [MEDIUM] No Rate Limiting or Cost Controls

**Severity**: Medium
**Component**: `commands/run.md` (remediation loops)

**Problem**: Up to 2 remediation loops per gate. With 4+ gates, a single workflow could iterate 8+ times.

**Impact**: Token/cost burn if issue isn't fixable by remediation.

**Recommendation**:
```yaml
workflow:
  max_remediation_loops: 2      # Per gate
  max_total_remediations: 4     # Global limit
```

---

### 2.5 [LOW] Hardcoded Paths in Scripts

**Severity**: Low
**Component**: Various scripts

**Problem**: Paths like `.session/`, `docs/DOCUMENTATION_REGISTRY.json` may be hardcoded.

**Impact**: Config overrides don't work everywhere.

**Recommendation**:
- Audit all scripts for hardcoded paths
- Use central config loader
- Document all configurable paths

---

## 3. Missing Capabilities

### 3.1 [HIGH] No Diff Preview Before Implementation

**Severity**: High
**Component**: `commands/run.md`

**Problem**: No way to see what code will change before implementation runs.

**Impact**: Users commit to implementation without understanding scope.

**Recommendation**:
```bash
at:run --dry-run  # Shows planned changes without executing
```

---

### 3.2 [MEDIUM] No Incremental Resume from Phase

**Severity**: Medium
**Component**: Session resumption

**Problem**: Can't say "just re-run quality gate"—resume may re-run prior steps.

**Recommendation**:
```bash
at:run --from-phase quality --session <id>
```

---

### 3.3 [MEDIUM] No Integration Testing Story

**Severity**: Medium
**Component**: `commands/run.md` (quality phase)

**Problem**: Focus on unit tests. No first-class support for E2E, integration tests.

**Recommendation**:
```yaml
commands:
  typescript:
    test: "npm test"
    integration_test: "npm run test:e2e"  # New
```

Add integration phase after quality gate.

---

### 3.4 [MEDIUM] No Dependency Vulnerability Scanning

**Severity**: Medium
**Component**: Quality gate

**Problem**: No `npm audit`, `pip-audit`, or license compliance checks.

**Recommendation**:
```yaml
commands:
  typescript:
    security_audit: "npm audit --audit-level=high"
```

Add security gate in workflow.

---

### 3.5 [LOW] No Workflow Composition

**Severity**: Low
**Component**: `commands/run.md`

**Problem**: Can't customize which phases run. Want "deliver but skip compliance"? Must copy and modify run.md.

**Recommendation**:
```yaml
workflow:
  phases:
    - planning
    - implementation
    - quality
    # - compliance  # Disabled
    - docs
```

---

### 3.6 [LOW] TDD Mode is Awkward Coupling

**Severity**: Low
**Component**: `commands/run.md` (TDD path)

**Problem**: TDD replaces phases 1-3 but shares 4-11. Creates maintenance burden.

**Recommendation**:
- Make TDD a fully independent workflow
- Extract shared gates into reusable functions

---

## 4. Architectural Concerns

### 4.1 Parallel Execution Fragility

**Component**: `scripts/parallel_conformance.py`

**Concern**:
- Planner may not accurately predict all files touched
- Generated files (codegen, migrations) are unpredictable
- Lock files are globally shared

**Recommendation**:
- Run parallel tasks in isolated git worktrees
- Add `parallel_execution.isolate: true` for full isolation
- Merge with conflict detection

---

### 4.2 Agent Specs are Documentation, Not Code

**Component**: `agents/*.md`

**Concern**:
- Claude's interpretation may drift between model versions
- No way to test agent behavior programmatically
- Subtle wording changes cause behavior changes

**Recommendation**:
- Create reference implementations for critical logic
- Add behavioral tests that verify agent outputs
- Version agent specs and track changes

---

### 4.3 actions.json Schema Too Permissive

**Component**: `scripts/validate_actions.py`

**Concern**: Many optional fields, validation happens late. Planner can create invalid plans that fail at execution.

**Recommendation**:
- Strict JSON Schema validation immediately after planner
- Return to planner for fixes if validation fails
- Separate "planner can output" from "orchestrator requires"

---

## 5. Priority Action Items

### Immediate (P0)

| # | Issue | Fix |
|---|-------|-----|
| 1 | Docs registry blocks adoption | Make `docs.require_registry` optional |
| 2 | No rollback capability | Add git checkpoint before implementation |
| 3 | Final reply contracts unenforceable | Write to file + validate schema |

### Near-Term (P1)

| # | Issue | Fix |
|---|-------|-----|
| 4 | Binary gates inflexible | Add severity levels to acceptance criteria |
| 5 | Session pollution | Add retention policy + cleanup script |
| 6 | Policy hooks opt-in | Make default-on during init |
| 7 | No dry-run mode | Add `--dry-run` flag |

### Mid-Term (P2)

| # | Issue | Fix |
|---|-------|-----|
| 8 | Orchestrator untestable | Extract to Python state machine |
| 9 | LSP fails hard | Add fallback modes |
| 10 | No phase resume | Add `--from-phase` flag |
| 11 | No security audit | Add security gate |

### Future (P3)

| # | Issue | Fix |
|---|-------|-----|
| 12 | Workflow composition | Declarative phase config |
| 13 | TDD coupling | Make independent workflow |
| 14 | Agent behavioral tests | Add test harness |
| 15 | Skills for agents | Add reference.md pattern |

---

## 6. Metrics to Track

After implementing fixes, track:

| Metric | Target | Rationale |
|--------|--------|-----------|
| New project onboarding time | < 5 min | Docs registry was blocking |
| First successful `/at:run` | < 30 min | Reduce friction |
| Remediation loop rate | < 1.5 per workflow | Fewer retries = better plans |
| Session cleanup failures | 0 | Automated cleanup working |
| Security policy coverage | 100% new projects | Policy hooks default-on |

---

## Appendix: Files Reviewed

- `.claude-plugin/plugin.json`
- `commands/run.md`
- `agents/*.md` (all 12 agents)
- `skills/*.md` (all 10 skills)
- `contexts/*.md` (all 3 contexts)
- `hooks/hooks.json`
- `schemas/project.schema.json`
- `docs/` (documentation files)
- `scripts/` (validation scripts)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-25 | Claude Opus 4.5 | Initial audit |
