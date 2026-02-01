# Self Audit Report (at)

- generated_at: `2026-02-01T11:38:55.994920+00:00`
- ok: `true`

## Checks

- `plugin.version_consistency`: `ok` — plugin.json.version='0.1.0' VERSION='0.1.0'
- `hooks.script_refs_exist`: `ok` — all hook script references exist
- `markdown.script_refs_exist`: `ok` — all agents/skills script references exist
- `versioning.python_headers`: `ok` — all scripts have at Version/Updated header
- `versioning.frontmatter`: `ok` — all agents/skills have version+updated frontmatter
- `contracts.schema_workflows`: `ok` — schema workflows match validator: ['deliver', 'ideate', 'review', 'triage']
- `contracts.schema_owners`: `ok` — schema owners match validator: ['action-planner', 'compliance-checker', 'ideation', 'implementor', 'quality-gate', 'reviewer', 'root-cause-analyzer', 'tests-builder']
- `contracts.validator_fixtures`: `ok` — validator fixtures behave as expected
