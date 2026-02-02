---
name: docs-code-index
version: "0.5.0"
updated: "2026-02-02"
description: "Analyze code structure using LSP for documentation generation."
argument-hint: "[--session <id|dir>] [--scope changed|full]"
allowed-tools: Read, Glob, LSP, Bash
---

# /at:docs-code-index

Analyze code structure to help docs-keeper generate accurate documentation.

## When to use
- Before running `/at:docs sync` for better code coverage
- When documentation needs to reference code symbols

## Procedure

### 1) Determine scope

If `--scope changed` (default):
- Read `SESSION_DIR/implementation/tasks/*.yaml`
- Collect `changed_files[].path` where action is `created` or `modified`

If `--scope full`:
- Scan project for code files (*.py, *.ts, *.go, *.rs)
- Exclude: node_modules, .venv, dist, build, __pycache__

### 2) Analyze each file using LSP

For each code file:
```
LSP documentSymbol operation:
- filePath: {file}
- line: 1
- character: 1
```

Extract:
- Classes/structs with their methods
- Functions with signatures
- Interfaces/traits
- Type definitions

### 3) Generate code index

```json
{
  "version": 1,
  "generated_at": "{timestamp}",
  "scope": "changed|full",
  "files": [
    {
      "path": "src/example.py",
      "language": "python",
      "symbols": [
        {"kind": "class", "name": "Example", "line": 10},
        {"kind": "function", "name": "process", "line": 25}
      ]
    }
  ]
}
```

### 4) Output

Write to `SESSION_DIR/documentation/code_index.json` if session exists.

```
# Code Index

- scope: `{scope}`
- files_analyzed: `{count}`
- symbols_total: `{count}`

## Files
- `src/example.py` (python): 5 symbols
- `src/util.ts` (typescript): 3 symbols
```

## Output

Code index summary to stdout. JSON written to session if available.
