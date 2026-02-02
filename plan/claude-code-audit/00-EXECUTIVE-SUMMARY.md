# Claude Code Plugin Audit: Executive Summary

**Date:** 2026-02-02
**Plugin:** Agent Team (`at`) v0.3.1
**Auditor:** Claude Code Analysis

## Overall Assessment

The `at` plugin is an ambitious, well-structured workflow kernel for Claude Code. However, the heavy reliance on **deterministic Python scripts** creates a tension with Claude Code's core value proposition: **agentic flexibility and intelligence**.

### Key Finding

**~70% of the workflow is deterministic scripts; ~30% is agentic.**

This ratio inverts what makes agentic development valuable. The scripts enforce contracts that Claude can already reason about, while adding:
- Maintenance burden (100+ Python files)
- Latency (multiple subprocess calls per workflow)
- Rigidity (hard-coded paths, schemas, validation rules)
- Duplication (scripts reimplement what agents could handle contextually)

## Verdict by Category

| Category | Score | Notes |
|----------|-------|-------|
| **Architecture** | B | Clean separation of concerns, but over-engineered |
| **Claude Code Integration** | C+ | Underutilizes frontmatter, hooks, and native primitives |
| **User Experience** | B- | Complex installation, steep learning curve |
| **Maintainability** | C | 100+ scripts, version headers everywhere, tight coupling |
| **Value-Add of Determinism** | C | Many scripts could be agent instructions instead |

## Top 5 Recommendations

1. **Collapse validation scripts into agent instructions** — Claude can validate `actions.json` schema compliance if given the schema in context.

2. **Use Claude Code's native `permissionMode` instead of scope enforcement hooks** — The hook-based file scope enforcement is complex and fragile. Claude Code's built-in permission modes handle this better.

3. **Replace context-building scripts with structured prompts** — `build_context_pack.py` (430 lines) assembles markdown that could be a structured prompt template with `@imports`.

4. **Leverage frontmatter `skills:` injection** — Instead of scripts that build task contexts, declare skill dependencies in agent frontmatter and let Claude Code inject them.

5. **Simplify installation to a single command** — Currently requires `/at:init-project`, manual config editing, optional hooks setup, language pack installation. Should be `claude --install-plugin at && /at:setup`.

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Scripts become stale as Claude Code evolves | High | Move logic to agents/prompts |
| Complex hook chains cause debugging nightmares | Medium | Reduce to essential hooks only |
| New users abandon plugin due to complexity | High | Simplify onboarding flow |
| Performance overhead from subprocess calls | Medium | Batch operations, reduce script count |

## Next Steps

See detailed analysis files in this directory:
- `01-DETERMINISM-CHALLENGE.md` — Script-by-script value assessment
- `02-CLAUDE-CODE-OPPORTUNITIES.md` — Leveraging native capabilities
- `03-CONFLICTS-INCONSISTENCIES.md` — Technical issues found
- `04-UX-IMPROVEMENTS.md` — Installation and usage improvements
- `05-RECOMMENDATIONS.md` — Prioritized action items
