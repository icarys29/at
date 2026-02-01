---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/plugins-reference
  - https://code.claude.com/docs/en/plugins-location-reference
---

# Plugins (Claude Code)

## What a “plugin” is (in Claude Code)

A plugin is a **directory** that packages Claude Code extensions (e.g., slash commands/skills, subagents, hooks, MCP servers). A plugin defines what it provides via a plugin manifest.

## Plugin manifest location

The plugin manifest is: `.claude-plugin/plugin.json` (relative to the plugin root).

## Plugin manifest shape (high-level)

`plugin.json` commonly includes:
- `name`, `version`, `description`
- Optional metadata: `author`, `license`, `repository`, `keywords`
- Component path fields that point to what the plugin provides, for example:
  - `commands` (legacy “.md command” files)
  - `skills` (directory containing skill folders with `SKILL.md`)
  - `agents` (directory containing subagent markdown files)
  - `hooks` (hook config file(s), typically JSON)
  - `mcpServers` (MCP server config file(s), typically `.mcp.json`)
  - `lspServers` (LSP server config file(s), typically `.lsp.json`)
  - `outputStyles` (output style files)

Path values may be a string or list of strings (depending on the field). Use relative paths.

## Plugin install locations

Claude Code discovers plugins from user and project plugin directories (see the official “Plugins Location Reference” for the full list and platform-specific details).

## Note for this repo (`at`)

This repository currently uses a root-level `plugin.json` as part of its internal build/layout. The official Claude Code plugin manifest location is `.claude-plugin/plugin.json`. If you want the plugin to be maximally compatible with upstream expectations, consider migrating the manifest and updating docs accordingly.

## Environment variables

When running plugin commands/scripts, Claude Code provides `${CLAUDE_PLUGIN_ROOT}` to reference the plugin’s root directory from hook commands and scripts.

## Design guidance (aligns with KISS/YAGNI)

- Prefer **fewer** commands/agents with clearer contracts over adding many niche ones.
- Treat command names as API surface area: avoid renames and avoid adding new names unless there’s a concrete need.
- Keep plugin structure close to defaults unless there’s a strong reason; non-standard layouts add cognitive overhead.
