# Agent Team (`at`) — Claude Code workflow kernel

`at` is a corporate-grade, **session-backed** workflow kernel for Claude Code. It turns a request into a repeatable run with:

- deterministic session artifacts (plans, task outputs, reports)
- minimal, task-scoped context (context pack + per-task context slices)
- binary gates (scope, quality, docs, compliance)
- optional hooks for policy enforcement, audit logging, and UX nudges

## Quickstart

- Run Claude Code with this plugin: `claude --plugin-dir .`
- Maintainer guide: `CLAUDE.md` (also available via `AGENT.md`)
- Plugin manifest: `.claude-plugin/plugin.json`
