---
name: self-audit
version: "0.5.0"
updated: "2026-02-02"
description: Run integrity checks for the at plugin configuration.
argument-hint: ""
allowed-tools: Read, Glob, Bash
---

# /at:self-audit

Run integrity checks on the at plugin to verify configuration consistency.

## Procedure

### 1) Check version consistency

Verify these files have matching versions:
- `VERSION`
- `plugin.json`
- `.claude-plugin/plugin.json`

### 2) Check skill integrity

For each `skills/*/SKILL.md`:
- Verify frontmatter has required fields (name, version, description)
- Verify `allowed-tools` are valid tool names
- Check for references to non-existent scripts

### 3) Check agent integrity

For each `agents/*.md`:
- Verify frontmatter has required fields (name, description, tools)
- Verify `disallowedTools: Task` is set (no nested subagents)

### 4) Check script integrity

Run compile check:
```bash
uv run python -m compileall -q scripts/
```

### 5) Check hooks configuration

Verify `hooks/hooks.json` references existing scripts.

### 6) Output report

```
# Self-Audit Report

## Version Check
- VERSION: {version}
- plugin.json: {version}
- .claude-plugin/plugin.json: {version}
- Status: {OK|MISMATCH}

## Skills ({count})
- {skill_name}: {OK|issues}

## Agents ({count})
- {agent_name}: {OK|issues}

## Scripts
- Compile check: {OK|FAILED}

## Hooks
- hooks.json: {OK|issues}

## Overall
- Status: {PASS|FAIL}
- Issues: {count}
```

## Output

Audit report to stdout. No artifacts written.
