---
name: god-class-audit
version: "0.5.0"
updated: "2026-02-02"
description: "Scan for oversized classes (SRP heuristic) using LSP."
argument-hint: "[--max-methods N] [--max-lines N]"
allowed-tools: Read, Glob, LSP
---

# /at:god-class-audit

Scan for oversized classes that may violate Single Responsibility Principle.

## Procedure

### 1) Set thresholds

Default thresholds (can be overridden):
- `max_methods`: 15
- `max_lines`: 300

### 2) Find code files

Use Glob to find:
- `**/*.py` (Python)
- `**/*.ts` (TypeScript)
- `**/*.go` (Go)

Exclude:
- `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `build/`

### 3) Analyze each file using LSP

For each file:
```
LSP documentSymbol operation:
- filePath: {file}
- line: 1
- character: 1
```

For each class/struct symbol:
- Count methods (function symbols within the class range)
- Estimate line count from symbol range

### 4) Identify violations

A class is a "god class" candidate if:
- methods > max_methods, OR
- lines > max_lines

### 5) Output report

```
# God Class Audit

- files_scanned: `{count}`
- classes_analyzed: `{count}`
- violations: `{count}`

## Violations

### `src/services/user_manager.py:UserManager`
- methods: `23` (threshold: 15)
- lines: `450` (threshold: 300)
- Suggestion: Split by responsibility (e.g., UserAuth, UserProfile, UserStorage)

### `src/handlers/api.ts:APIHandler`
- methods: `18` (threshold: 15)
- Suggestion: Extract endpoint handlers into separate classes
```

## Output

Report to stdout. Exit non-zero if violations found.
