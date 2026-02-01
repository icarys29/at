# Documentation Registry (at)

This file is generated from the JSON registry and is intended for fast human scanning.

- Source: `docs/DOCUMENTATION_REGISTRY.json`

## Index

| Tier | Type | ID | Status | Owners | Title | Path | When | Tags |
|---:|---|---|---|---|---|---|---|---|
| 1 | context | `DOC-PROJECT-CONTEXT` | active | core | Project Context | `docs/PROJECT_CONTEXT.md` | Use for project-wide conventions, workflows, and baseline constraints (planning + execution). | context, conventions, workflow |
| 2 | ard | `ARD-INDEX` | active | core | Architecture Records (ARDs) Index | `docs/architecture/README.md` | Use when a new core component/framework requires an internal design record (responsibilities/flow/boundaries). | architecture, components |
| 2 | architecture | `DOC-ADR-INDEX` | active | core | ADRs Index | `docs/adr/README.md` | Use when a deliver introduces or changes a material architecture decision; create/update ADRs under docs/adr/. | architecture, decisions |
| 2 | architecture | `DOC-ARCHITECTURE` | active | core | Architecture Overview | `docs/ARCHITECTURE.md` | Use for architectural boundaries, dependency direction rules, and major patterns in use (keep concise). | architecture, patterns, boundaries |
| 2 | pattern | `PAT-INDEX` | active | core | Pattern Docs Index | `docs/patterns/README.md` | Use when a reusable implementation pattern emerges (avoid repeated ADRs by documenting the pattern once). | patterns |
| 3 | runbook | `RB-INDEX` | active | core | Runbooks Index | `docs/runbooks/README.md` | Use when operational procedures are needed (recovery, migrations, incident response). | runbooks, ops |

## Generated Artifacts

| ID | Path | Source | Generator | Mode |
|---|---|---|---|---|
| `DOC-REGISTRY-MD` | `docs/DOCUMENTATION_REGISTRY.md` | `docs/DOCUMENTATION_REGISTRY.json` | docs-keeper | overwrite |

## Notes

- Tiers: 1=core contract, 2=architecture/conventions, 3=how-to, 4=reference/appendix.
- Keep docs concise and keep this registry accurate; gates may fail on drift.
