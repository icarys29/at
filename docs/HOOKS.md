# Hooks Reference

This document explains how hooks work in Agent Team (at) and how to customize them.

## Overview

Hooks are scripts that run automatically at specific points in Claude Code's execution. The `at` plugin uses hooks for:

- **Scope enforcement** - Prevent writes outside declared file scope
- **Audit logging** - Record tool usage and session events
- **Policy enforcement** - Block access to secrets and dangerous commands
- **Validation** - Check artifacts as they're written

## Hook Types

| Event | When it fires | Common uses |
|-------|---------------|-------------|
| `PreToolUse` | Before a tool executes | Validation, scope checking, blocking |
| `PostToolUse` | After a tool completes | Logging, post-validation |
| `SubagentStop` | When a subagent finishes | Output validation, state updates |
| `SessionStart` | When Claude Code starts | Context injection |

## Configuration Locations

Hooks are configured in JSON files. Claude Code merges configurations from multiple locations:

### 1. Plugin hooks (lowest priority)
```
<plugin-dir>/hooks/hooks.json
```
The `at` plugin ships with default hooks here.

### 2. Project hooks (medium priority)
```
.claude/settings.json
```
Project-specific overrides.

### 3. User hooks (highest priority)
```
~/.claude/settings.json
```
User-wide settings that override everything else.

## Precedence Rules

When the same hook event has multiple handlers:

1. **All handlers run** - Hooks don't replace each other, they accumulate
2. **Any deny wins** - If any hook returns `permissionDecision: deny`, the action is blocked
3. **Order matters** - Hooks run in the order they appear in the merged configuration

## Plugin Default Hooks

The `at` plugin includes these hooks by default:

### SubagentStop
```json
{
  "matcher": "*",
  "hooks": [{
    "type": "command",
    "command": "uv run \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/on_subagent_stop.py\"",
    "timeout": 30
  }]
}
```
Validates subagent output format.

### PreToolUse (Task)
```json
{
  "matcher": "Task",
  "hooks": [{
    "type": "command",
    "command": "uv run \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/validate_task_invocation.py\"",
    "timeout": 10
  }]
}
```
Validates subagent spawning.

### PreToolUse (Write/Edit)
```json
{
  "matcher": "Write || Edit",
  "hooks": [{
    "type": "command",
    "command": "uv run \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/enforce_file_scope.py\"",
    "timeout": 10
  }]
}
```
Enforces file scope restrictions.

### PostToolUse (Write)
```json
{
  "matcher": "Write",
  "hooks": [{
    "type": "command",
    "command": "uv run \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/validate_actions_write.py\"",
    "timeout": 10
  }]
}
```
Validates actions.json writes.

## Installing Optional Hooks

### Audit Hooks
Records all tool usage to `.claude/audit_logs/`:
```
/at:setup-audit-hooks
```

### Policy Hooks
Blocks access to secrets and dangerous commands:
```
/at:setup-policy-hooks
```

### Learning Hooks
Captures patterns for future sessions:
```
/at:setup-learning-hooks
```

## Disabling Hooks

### Disable a specific plugin hook

Add to `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write || Edit",
        "hooks": []
      }
    ]
  }
}
```

This replaces the plugin's scope enforcement with an empty handler.

### Disable all plugin hooks

Run:
```
/at:uninstall-hooks
```

Or manually remove hooks from `.claude/settings.json`.

## Writing Custom Hooks

Hook scripts receive JSON on stdin and must output JSON to stdout.

### Input format
```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "content": "..."
  },
  "session_id": "claude-session-id",
  "transcript_path": "/path/to/transcript"
}
```

### Output format

**Allow the action:**
```json
{
  "continue": true
}
```

**Deny the action:**
```json
{
  "continue": true,
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Explanation for user"
  }
}
```

**Add a message:**
```json
{
  "continue": true,
  "hookSpecificOutput": {
    "message": "Note: This file was modified"
  }
}
```

## Performance Considerations

Hooks add latency to every tool call they match:

| Hook | Typical latency |
|------|-----------------|
| `enforce_file_scope.py` | 50-100ms |
| `audit_pre_tool_use.py` | 10-20ms |
| `policy_pre_tool_use.py` | 20-40ms |

For performance-sensitive workflows:
1. Use specific matchers instead of `*`
2. Keep hook scripts fast (< 100ms)
3. Consider disabling non-essential hooks

## Debugging Hooks

### Check which hooks are active
```bash
cat .claude/settings.json | jq '.hooks'
```

### Run a hook manually
```bash
echo '{"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "test.py"}}' | \
  uv run scripts/hooks/enforce_file_scope.py
```

### Check hook logs
If audit hooks are enabled:
```bash
tail -f .claude/audit_logs/tools_*.jsonl
```

## Common Issues

### "Hook timeout" errors
Increase the timeout in hooks.json or optimize the hook script.

### Hooks not firing
Check that:
1. The matcher matches the tool name
2. The hook is in the correct settings file
3. The script path is correct

### Permission denied
Hook scripts must be executable:
```bash
chmod +x scripts/hooks/*.py
```
