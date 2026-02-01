# Hooks (project)

This folder is reserved for project-scoped hook scripts/configuration.

Recommended: install the minimal docs-keeper hooks (exactly 2) via:

- `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/hooks/install_docs_keeper_hooks.py" --scope project`

Hooks should detect and block/warn, not perform large edits:
- detect → docs skill fixes → docs-keeper agent executes

