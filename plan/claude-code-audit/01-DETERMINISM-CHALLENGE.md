# Challenge: Does Determinism Lower Agentic Value?

## The Core Tension

The plugin's philosophy is "determinism first" — scripts produce stable, auditable outputs. But this philosophy:

1. **Duplicates Claude's reasoning** — Scripts validate what Claude can validate in-context
2. **Adds latency** — Each `uv run` call adds 100-500ms overhead
3. **Reduces adaptability** — Hard-coded logic can't adapt to edge cases
4. **Increases maintenance** — 100+ Python files to keep in sync

## Script-by-Script Value Assessment

### HIGH VALUE (Keep as scripts)

| Script | Purpose | Why Deterministic |
|--------|---------|-------------------|
| `run_quality_suite.py` | Run lint/test/build commands | **Essential**: subprocess execution must be reliable |
| `create_session.py` | Create session directories | **Essential**: filesystem operations need reliability |
| `create_checkpoint.py` / `restore_checkpoint.py` | Git stash-like checkpoints | **Essential**: git operations must be atomic |
| `audit_log.py` | Write JSONL audit logs | **Essential**: structured logging must be reliable |
| `generate_registry_md.py` | Generate docs registry markdown | **Reasonable**: simple transformation, deterministic |

### MEDIUM VALUE (Consider agent alternatives)

| Script | Purpose | Challenge |
|--------|---------|-----------|
| `build_context_pack.py` | Assemble context markdown | **Challenge**: 430 lines to do what a prompt template could do. Claude can read the same files and format them contextually. |
| `build_task_contexts.py` | Build per-task context slices | **Challenge**: Could be agent instructions: "For each task in actions.json, extract only the relevant files and doc sections." |
| `docs_plan.py` | Determine which docs need updates | **Challenge**: Coverage rules are already in the registry. Claude can apply them without a script. |
| `session_progress.py` | Generate progress reports | **Challenge**: Report generation from session artifacts is something Claude excels at. |

### LOW VALUE (Strong candidates for removal)

| Script | Purpose | Challenge |
|--------|---------|-----------|
| `validate_actions.py` / `actions_validator.py` | Validate actions.json schema | **Challenge**: Give Claude the JSON schema in context. It can validate and explain violations better than a script. |
| `plan_adherence.py` | Check if implementation matches plan | **Challenge**: This is comparing two things Claude wrote. Let Claude do the comparison with reasoning. |
| `parallel_conformance.py` | Check parallel execution safety | **Challenge**: If the action-planner agent is instructed correctly, it won't create conflicts. Post-hoc validation is defensive programming against yourself. |
| `validate_changed_files.py` | Compare changed files to scope | **Challenge**: Claude already knows what it wrote. A hook that blocks out-of-scope writes (which you have) is sufficient. |
| `gates_summary.py` | Aggregate gate results | **Challenge**: Simple aggregation. Claude can read the individual reports and summarize. |
| `compliance/generate_compliance_report.py` | APPROVE/REJECT decision | **Challenge**: Reads `ok` fields from JSON files and combines them. This is trivial for Claude to do in-context. |

### HOOK SCRIPTS — Special Category

| Script | Purpose | Challenge |
|--------|---------|-----------|
| `enforce_file_scope.py` | Block out-of-scope writes | **Conflicted**: The logic is complex (325 lines) and fragile (parses transcripts). Claude Code's native `permissionMode` handles this better. If you need scope enforcement, use `permissionMode: askEdits` combined with clear instructions. |
| `validate_task_invocation.py` | Validate Task tool calls | **Questionable**: Why validate subagent spawning? The orchestrator controls this. |
| `validate_actions_write.py` | Validate actions.json on write | **Questionable**: Duplicates `validate_actions.py`. |

## Quantified Impact

Current workflow (`/at:run deliver`):
```
1. create_session.py         ~200ms
2. build_context_pack.py     ~300ms
3. [agent: solution-architect]
4. [agent: story-writer]
5. [agent: action-planner]
6. validate_actions.py       ~150ms
7. user_stories_gate.py      ~100ms (optional)
8. docs_requirements_for_plan.py ~100ms
9. build_task_contexts.py    ~400ms
10. create_checkpoint.py     ~300ms
11. [agents: implementor/tests-builder × N tasks]
12. validate_task_artifacts.py ~100ms
13. [agent: lsp-verifier] (optional)
14. plan_adherence.py        ~100ms
15. parallel_conformance.py  ~100ms
16. run_quality_suite.py     ~variable (lint/test)
17. e2e_gate.py              ~100ms
18. [agent: docs-keeper]
19. docs_gate.py             ~100ms
20. validate_changed_files.py ~100ms
21. generate_compliance_report.py ~100ms
22. [agent: compliance-checker] (optional)
23. gates_summary.py         ~100ms
24. task_board.py            ~100ms
25. session_progress.py      ~100ms
```

**Estimated script overhead: 2.5-4 seconds** (excluding quality suite)

This doesn't count hook invocations:
- `enforce_file_scope.py` — called on every Write/Edit (~100ms each)
- `validate_actions_write.py` — called on every Write to actions.json
- `on_subagent_stop.py` — called when each subagent completes

**Hook overhead for a 5-task session: ~1-2 seconds additional**

## The Alternative: Agent Instructions

Instead of 100+ scripts, consider this pattern:

```markdown
# Agent: Action Planner

## Validation Rules (apply before writing actions.json)
- Every `implementor` and `tests-builder` task must declare `file_scope.writes[]`
- `writes[]` entries must be exact file paths or directory prefixes ending in `/`
- Tasks in the same parallel group must have non-overlapping `writes[]`
- Every task must have `acceptance_criteria[]` with at least one `verification`
- If `workflow.strategy=tdd`, tests-builder tasks must precede implementor tasks

## Schema
<include schema/actions.schema.json>

## Self-Check
Before writing actions.json, verify:
1. All tasks have unique IDs
2. `depends_on[]` references exist
3. `parallel_execution.groups` covers all code tasks exactly once
4. No overlapping `writes[]` within any group
```

This achieves the same validation without a script. Claude can explain violations in natural language, suggest fixes, and adapt to edge cases.

## Recommendations

1. **Keep essential scripts** — Session management, quality command execution, checkpoints, audit logging
2. **Move validation to agent instructions** — Schema validation, plan adherence, compliance decisions
3. **Simplify context building** — Use `@imports` and structured prompts instead of markdown generators
4. **Reduce hook complexity** — Trust Claude Code's permission system; add only essential guardrails
5. **Measure before optimizing** — Add timing to scripts to identify actual bottlenecks
