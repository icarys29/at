#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate Task tool invocations (guardrail; opt-in via policy hooks)

Goal:
- Prevent accidental invocation of at subagents without required session context.
- Fail open for non-at usage (unknown agents, missing context).

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.active_session import resolve_session_dir_from_hook  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, get_plugin_root  # noqa: E402


_BUILTIN_AGENTS = {"Explore", "Plan", "general-purpose", "Bash", "claude-code-guide"}

_AGENTS_REQUIRING_TASK_CONTEXT = {"implementor", "tests-builder"}


def _load_hook_input() -> dict[str, Any] | None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _emit(decision: str, reason: str) -> int:
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                },
            }
        )
    )
    return 0


def _plugin_agent_names(plugin_root: Path) -> set[str]:
    agents_dir = plugin_root / "agents"
    names: set[str] = set()
    if not agents_dir.exists():
        return names
    for p in agents_dir.glob("*.md"):
        if p.is_file() and p.stem:
            names.add(p.stem)
    return names


def _has_task_context_ref(prompt: str) -> bool:
    # Accept either the literal SESSION_DIR placeholder or a resolved path.
    return "inputs/task_context/" in prompt.replace("\\", "/")


def _has_session_ref(prompt: str, *, sessions_dir: str, session_dir_abs: Path | None, project_root: Path | None) -> bool:
    p = prompt.replace("\\", "/")
    if "SESSION_DIR" in p:
        return True

    # Explicit resolved session dir path.
    if session_dir_abs is not None:
        abs_s = str(session_dir_abs).replace("\\", "/")
        if abs_s and abs_s in p:
            return True
        if project_root is not None:
            try:
                rel = str(session_dir_abs.relative_to(project_root)).replace("\\", "/")
            except Exception:
                rel = ""
            if rel and rel in p:
                return True

    # Pattern match for sessions_dir/<session_id>
    sd = (sessions_dir or ".session").strip().rstrip("/").replace("\\", "/")
    if sd:
        # at session id format: YYYYMMDD-HHMMSS-<6hex>
        if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(sd)}/\d{{8}}-\d{{6}}-[0-9a-f]{{6}}(?![A-Za-z0-9_.-])", p):
            return True

    # Fall back to recognizing session.json references.
    if "/session.json" in p or "session.json" in p:
        return True

    return False


def main() -> int:
    hook_input = _load_hook_input()
    if not hook_input:
        return _emit("allow", "No hook input; allowing.")
    if hook_input.get("hook_event_name") != "PreToolUse":
        return _emit("allow", "Not a PreToolUse hook; allowing.")
    if hook_input.get("tool_name") != "Task":
        return _emit("allow", "Not a Task invocation; allowing.")

    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return _emit("allow", "Missing tool_input; allowing.")

    subagent_type = tool_input.get("subagent_type")
    subagent = subagent_type.strip() if isinstance(subagent_type, str) else ""
    if not subagent:
        return _emit("allow", "Task subagent_type not specified; allowing.")
    if subagent in _BUILTIN_AGENTS:
        return _emit("allow", f"Built-in agent {subagent!r}; allowing.")

    # Only enforce rules for at-owned agents. If it's another plugin/user agent, do not interfere.
    try:
        plugin_root = get_plugin_root()
    except Exception:
        plugin_root = None
    if not plugin_root:
        return _emit("allow", "Unable to resolve plugin root; allowing.")

    plugin_agents = _plugin_agent_names(plugin_root)
    if subagent not in plugin_agents:
        return _emit("allow", f"Non-at agent {subagent!r}; allowing.")

    prompt = tool_input.get("prompt")
    prompt_s = prompt if isinstance(prompt, str) else ""

    # Resolve best-effort active session dir (preferred) to validate the prompt includes it.
    project_root: Path | None
    try:
        project_root = detect_project_dir()
    except Exception:
        project_root = None
    sessions_dir = ".session"
    if project_root is not None:
        try:
            sessions_dir = get_sessions_dir(project_root)
        except Exception:
            sessions_dir = ".session"

    session_dir_abs: Path | None = None
    if project_root is not None:
        try:
            active = resolve_session_dir_from_hook(
                project_root=project_root,
                sessions_dir=sessions_dir,
                claude_session_id=str(hook_input.get("session_id") or "").strip() or None,
            )
            session_dir_abs = active.session_dir if active else None
        except Exception:
            session_dir_abs = None

    if subagent in _AGENTS_REQUIRING_TASK_CONTEXT and not _has_task_context_ref(prompt_s):
        return _emit(
            "deny",
            f"at agent {subagent!r} requires a task context reference (expected 'inputs/task_context/<task_id>.md' in the Task prompt).",
        )

    if not _has_session_ref(prompt_s, sessions_dir=sessions_dir, session_dir_abs=session_dir_abs, project_root=project_root):
        return _emit(
            "deny",
            f"at agent {subagent!r} requires session context (include SESSION_DIR or a concrete '{sessions_dir}/<session_id>' path in the Task prompt).",
        )

    return _emit("allow", f"at Task invocation for {subagent!r} looks valid.")


if __name__ == "__main__":
    raise SystemExit(main())
