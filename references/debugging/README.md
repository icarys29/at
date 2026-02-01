---
status: stable
last_updated: 2026-01-22
---

# Debugging Reference

This directory contains systematic debugging methodology for the `root-cause-analyzer` agent and other agents investigating failures.

## Files

| File | Purpose | When to Read |
|------|---------|--------------|
| `systematic-debugging.md` | Core 4-phase methodology | Start here for any bug investigation |
| `root-cause-tracing.md` | Backward tracing technique | When bug is deep in call stack |
| `defense-in-depth.md` | Multi-layer validation patterns | When proposing prevention measures |
| `condition-based-waiting.md` | Replace flaky timeouts | When investigating flaky tests |

## Key Principle

**NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST**

Random fixes waste time and create new bugs. Systematic debugging is faster than guess-and-check thrashing.

## The Four Phases

1. **Root Cause Investigation** - Read errors, reproduce, gather evidence, trace data flow
2. **Pattern Analysis** - Find working examples, compare against references
3. **Hypothesis and Testing** - Form single hypothesis, test minimally
4. **Implementation** - Create failing test, implement single fix, verify

## Usage

These references are **not auto-loaded**. Agents read them on-demand when relevant:

```markdown
# In agent procedure
5) **Trace data flow**: if error is deep in call stack, trace backward to find original trigger
   (see `references/debugging/root-cause-tracing.md`).
```

This keeps agent context lean while providing detailed methodology when needed.

## Source

Adapted from [antigravity-awesome-skills](https://github.com/AntiguanGiant/antigravity-awesome-skills) systematic-debugging skill, modified to integrate with at patterns.
