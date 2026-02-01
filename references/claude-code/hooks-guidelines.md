---
status: stable
last_updated: 2026-02-01
sources:
  - https://code.claude.com/docs/en/hooks-reference
  - https://code.claude.com/docs/en/plugins-reference
---

# Claude Code Hooks — Practical Guidelines

This is a **concise but comprehensive** guide to hook applicability, configuration scopes, and limitations, aligned with Anthropic’s official Claude Code docs.

## 1) What hooks can and can’t do

Hooks run your commands (or Claude “prompt” hooks) at specific lifecycle events. They can:
- **Validate** tool inputs/outputs and session state (schema checks, file-scope policy, artifact verification).
- **Block** progress to force a correction (by “decision: block” or exiting with code `2`).
- **Notify** (non-blocking) or set environment vars for later steps.

Hooks cannot:
- “Rewrite” model output directly; they can only **block** and let the model try again.
- Replace tool permissions: hooks execute code with the permissions of the user running Claude Code, so treat them as powerful and security-sensitive.

## 2) Where hooks can be configured (scopes)

Hooks can be configured in multiple places:

### 2.1 User / project / local settings scopes

Claude Code loads hook configs from settings files (typical locations): `~/.claude/settings.json`, `<project>/.claude/settings.json`, and `<project>/.claude/settings.local.json`. These are merged into the active configuration. (See official docs for the current precedence.)  

Enterprise-managed setups may restrict hooks via `allowManagedHooksOnly`. If enabled, only managed hooks run.  

### 2.2 Plugin hooks

Plugins can ship hooks and Claude Code will load plugin hook configs from the plugin manifest’s `hooks` field (commonly pointing at `hooks/hooks.json`). Hook paths are relative to the plugin root.  

If multiple hook configs match the same event, they can run **in parallel**, and all matching hooks run (so each hook should be deterministic and safe under concurrency).  

### 2.3 Component-scoped hooks (agents + skills)

Agents and skills can define **component-scoped** hooks in their YAML frontmatter. Limitations:
- Component-scoped hooks support only these events: `PreToolUse`, `PostToolUse`, `Stop`.
- A special `once: true` option is available for skills (run hook only once per session); this is not available for agents.

## 3) Hook events and matchers (applicability)

### 3.1 Common lifecycle events (overview)

The official list includes events such as:
- `PreToolUse`, `PostToolUse`, `PostToolUseFailure`
- `PermissionRequest`
- `SessionStart`, `SessionEnd`
- `Stop`
- `SubagentStart`, `SubagentStop`
- `Notification`
- `PreCompact`
- `UserPromptSubmit`

### 3.2 Events that support `matcher`

Per the official reference, `matcher` is supported on:
- `PreToolUse` (scope to tool names)
- `PermissionRequest` (scope to tool names)
- `PostToolUse` (scope to tool names)

Other events (like `Stop` / `SubagentStop`) are generally “global” per scope (no matcher).

## 4) Hook types and execution model

### 4.1 Command hooks (most common)

`type: "command"` runs a command with JSON input provided on `stdin` and expects hook output as JSON on `stdout` (optional) plus diagnostics on `stderr`.

### 4.2 Prompt hooks (advanced)

Claude Code also supports prompt-based hooks where Claude decides whether to block/allow based on a prompt.

Note: the official docs currently contain mixed wording about which events prompt hooks support. Treat prompt hooks as primarily intended for `Stop` / `SubagentStop`, and verify behavior in your environment before relying on prompt hooks for other events.

## 5) Hook input (how to validate things)

Hook commands receive a JSON object on `stdin` (shape depends on event). Examples of useful inputs:
- `cwd`, `session_id`, `transcript_path`
- For `Stop`: `stop_hook_active` (use this to prevent infinite stop-hook loops)
- For `SubagentStop`: `agent_transcript_path` and `stop_hook_active`
- For `PreToolUse` / `PostToolUse`: tool name + tool input/output (varies by tool)

## 6) Hook output (how to block / enforce formats)

### 6.1 JSON output (preferred when you need control)

Hooks can return structured JSON on `stdout` for more control. Common fields include:
- `continue` / `stopReason` (stop processing after hooks; takes precedence over other decisions)
- `systemMessage` (show a user warning)
- `suppressOutput` (hide stdout from transcript mode)

Decision/blocking fields are **event-specific**:
- `Stop` / `SubagentStop`: `decision: "block"` with a required `reason` prevents stopping; `decision` omitted allows stopping.
- `PostToolUse`: `decision: "block"` can automatically prompt Claude using `reason`; omitted does nothing.
- `PreToolUse` / `PermissionRequest`: use `permissionDecision: "allow"|"deny"` and `permissionDecisionReason`. `PreToolUse` also supports `updatedInput` (to rewrite tool input) and `additionalContext` (to add context for the tool run).

### 6.2 Exit code 2 (simple/compatible)

If a hook exits with code `2`, Claude Code treats it as a block and shows the `stderr` output to Claude (so the model can correct its next attempt). Exit code `0` allows. Exit code `1` indicates an error.

### 6.3 Enforcing output formats: recommended pattern

To enforce a skill/agent output format:
1. Attach a `Stop` hook at the appropriate scope (component-scoped for the skill/agent, or global).
2. Parse the most recent assistant message from `transcript_path`.
3. Validate against a strict schema (JSON, YAML, specific headings, etc.).
4. If invalid, **block** with a reason explaining exactly what is wrong and what to output instead.
5. Include a loop guard using `stop_hook_active` to avoid repeated blocking.

For subagent Task outputs, prefer a global/plugin `SubagentStop` hook and validate using `agent_transcript_path`.

## 7) Environment variables (useful in hooks)

Common variables used in hook commands:
- `${CLAUDE_PROJECT_DIR}`: absolute path to the active project
- `${CLAUDE_PLUGIN_ROOT}`: plugin root directory (for plugin-shipped hooks)
- `${CLAUDE_ENV_FILE}`: a file you can append `KEY=VALUE` lines to, making environment vars available in subsequent commands

## 8) Reliability & security best practices

- Keep hooks fast and deterministic (hooks can block tools; slow hooks degrade UX).
- Avoid network calls in `PreToolUse` paths unless absolutely necessary.
- Quote variables and treat paths/inputs as untrusted (hooks run arbitrary code).
- Make validation messages “machine-correctable”: short, specific, and stating the exact expected output format.
