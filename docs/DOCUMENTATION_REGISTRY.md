# Documentation Registry (at)

This file is generated from the JSON registry and is intended for fast human scanning.

- Source: `docs/DOCUMENTATION_REGISTRY.json`

## Index

| Tier | ID | Title | Path | When | Tags |
|---:|---|---|---|---|---|
| 1 | `DOC-PROJECT-CONTEXT` | Project Context | `docs/PROJECT_CONTEXT.md` | Use for project-wide conventions, workflow expectations, and baseline constraints (planning + execution). | context, conventions, workflow |
| 2 | `DOC-ADR-INDEX` | ADRs Index | `docs/adr/README.md` | Use when a task introduces or changes a material architecture decision (create/update an ADR). | architecture, decisions |
| 2 | `DOC-ARCHITECTURE` | Architecture Overview | `docs/ARCHITECTURE.md` | Use for architectural boundaries, dependency direction rules, and patterns in use (recorded concisely). | architecture, patterns, boundaries |
| 3 | `DOC-REGISTRY-MD` | Documentation Registry (Markdown view) | `docs/DOCUMENTATION_REGISTRY.md` | Use when updating documentation; this file is generated from the JSON registry and should remain in sync. | registry |

## Notes

- Tiers: 1=core contract, 2=architecture/conventions, 3=how-to, 4=reference/appendix.
- Keep docs concise and keep this registry accurate; gates may fail on drift.
