# Prioritized Recommendations

## Tier 1: Critical (Do First)

### R1. Reduce Script Count by 50%

**Problem:** 100+ Python scripts create maintenance burden and latency.

**Action:**
1. Identify scripts that duplicate Claude's reasoning (validation, compliance, summaries)
2. Move their logic to agent instructions with inline schemas
3. Keep only essential scripts: session management, quality execution, audit logging

**Scripts to eliminate or merge:**
- `validate_actions.py` + `actions_validator.py` → Agent instruction with schema
- `plan_adherence.py` → Agent self-check
- `parallel_conformance.py` → Action-planner validation rules
- `validate_changed_files.py` → Remove (scope hook already enforces)
- `gates_summary.py` → Agent aggregation
- `generate_compliance_report.py` → Agent decision

**Expected outcome:** ~50 scripts instead of ~100; faster workflows.

---

### R2. Simplify Scope Enforcement

**Problem:** `enforce_file_scope.py` is 325 lines of complex heuristics (transcript parsing, task inference).

**Action:**
1. Remove the hook for most users
2. Add clear scope instructions to `implementor` and `tests-builder` agents
3. For high-compliance users, offer opt-in hook with simpler logic:
   - Read `file_scope.writes[]` from environment variable set by orchestrator
   - No transcript parsing

**Implementation:**
```markdown
# In implementor.md

## Write Scope (CRITICAL)
You may ONLY write to these files:
${FILE_SCOPE_WRITES}

If you need to write elsewhere:
1. STOP immediately
2. Report: "Scope mismatch: need to write to X but scope is Y"
3. Do NOT attempt the write
```

---

### R3. Create `/at:setup` Wizard

**Problem:** Installation requires 5+ manual steps.

**Action:**
1. Create `/at:setup` skill that auto-detects project tooling
2. Generate `project.yaml` with detected commands
3. Ask yes/no questions for optional features
4. Run `/at:doctor` at the end

**Expected outcome:** New users start with `claude --plugin at && /at:setup`.

---

### R4. Implement Friendly Error Messages

**Problem:** Errors are technical and unhelpful.

**Action:**
1. Create `scripts/lib/errors.py` with error catalog
2. Map technical errors to user-friendly messages with examples
3. Include "how to fix" suggestions in all gate failures

**Example transformation:**
```python
# Before
print("FAIL: actions.json does not conform to the contract.", file=sys.stderr)

# After
print_error(
    "Plan validation failed",
    details="Task 'implement-auth' is missing acceptance criteria",
    fix="Add an 'acceptance_criteria' array to define how to verify the task is complete",
    example='{"id": "ac-1", "statement": "...", "verifications": [...]}',
    docs_link="/at:help acceptance-criteria"
)
```

---

## Tier 2: Important (Do Soon)

### R5. Leverage Claude Code Frontmatter

**Problem:** Underutilizing native features.

**Action:**
1. Add `skills:` to agent frontmatter for context injection
2. Use `model: haiku` for simpler agents (reviewer, docs-keeper)
3. Explore native output validation if available

---

### R6. Consolidate Session Resolution

**Problem:** Multiple methods to find the current session.

**Action:**
1. Set `AT_SESSION_DIR` environment variable at session creation
2. Modify all scripts to read from this variable first
3. Remove transcript-parsing heuristics from hooks

---

### R7. Add `/at:status` Quick View

**Problem:** Getting session status requires verbose commands.

**Action:**
1. Create `/at:status` skill that shows:
   - Current session ID
   - Workflow and status
   - Task progress (X/Y complete)
   - Last gate results
2. Make it the default when running `/at:run` with no arguments

---

### R8. Document Hook Precedence

**Problem:** Users don't know how hooks interact.

**Action:**
1. Create `docs/HOOKS.md` explaining:
   - Plugin hooks vs project hooks vs user hooks
   - Override and disable mechanisms
   - Performance implications
2. Add to `/at:help hooks`

---

## Tier 3: Nice to Have (Future)

### R9. Implement Automatic Upgrade

**Action:**
1. Track overlay version in `.claude/project.yaml`
2. Create migration system for schema changes
3. `/at:upgrade` checks version and applies migrations

---

### R10. Add Visual Progress

**Action:**
1. Emit structured progress events from `/at:run`
2. Render as ASCII progress bar or status line
3. Support both inline and summary modes

---

### R11. Create Plugin Marketplace Entry

**Action:**
1. Ensure `plugin.json` has all marketplace fields
2. Add screenshots/demos to README
3. Publish to Claude Code plugin registry (when available)

---

## Implementation Roadmap

### Phase 1: Foundation (1-2 weeks)
- [ ] R1: Audit scripts, identify elimination targets
- [ ] R2: Simplify scope enforcement
- [ ] R4: Create error catalog

### Phase 2: Onboarding (1-2 weeks)
- [ ] R3: Build `/at:setup` wizard
- [ ] R7: Add `/at:status`
- [ ] R8: Document hooks

### Phase 3: Polish (2-3 weeks)
- [ ] R5: Frontmatter improvements
- [ ] R6: Session resolution consolidation
- [ ] R1 (continued): Execute script reduction

### Phase 4: Future (ongoing)
- [ ] R9: Automatic upgrade
- [ ] R10: Visual progress
- [ ] R11: Marketplace

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Script count | ~100 | ~50 |
| Installation steps | 5+ | 2 |
| Time to first `/at:run` | 15+ min | 5 min |
| Hook latency per Write | ~100ms | ~20ms or removed |
| User-reported confusion (hypothetical) | High | Low |

---

## Appendix: Scripts to Keep

Essential scripts that add real value:

| Script | Reason |
|--------|--------|
| `create_session.py` | Filesystem setup must be reliable |
| `run_quality_suite.py` | Subprocess execution for lint/test |
| `create_checkpoint.py` | Git operations must be atomic |
| `restore_checkpoint.py` | Rollback requires reliability |
| `audit_log.py` | Structured logging |
| `init_project.py` | Project setup orchestration |
| `doctor.py` | Configuration validation |
| `generate_registry_md.py` | Simple, deterministic transformation |

Everything else should be evaluated for agent replacement.
