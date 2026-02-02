#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Simplified file scope enforcement hook

Version: 0.5.0
Updated: 2026-02-02

This is a simplified replacement for enforce_file_scope.py.
It reads the allowed write scope from an environment variable
instead of parsing transcripts.

The orchestrator should set AT_FILE_SCOPE_WRITES before dispatching
each subagent task.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.paths import path_matches_scope  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session_env import get_file_scope_from_env, get_session_from_env  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None




def _deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            }
        )
    )
    return 0


def _allow() -> int:
    print(json.dumps({"continue": True}))
    return 0


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PreToolUse":
        return _allow()

    tool_name = hook_input.get("tool_name")
    if tool_name not in {"Write", "Edit"}:
        return _allow()

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return _allow()

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return _allow()

    # Get allowed writes from environment (set by orchestrator)
    writes = get_file_scope_from_env()
    if not writes:
        # No scope set - fail open to avoid blocking non-at workflows
        return _allow()

    project_root = detect_project_dir()

    # Resolve and normalize the target path
    target = Path(file_path).expanduser()
    try:
        target_abs = target.resolve()
    except Exception:
        return _deny(f"Cannot resolve path: {file_path!r}")

    # Make repo-relative
    try:
        repo_rel = target_abs.relative_to(project_root)
    except Exception:
        return _deny(f"Path outside project root: {file_path!r}")

    repo_rel_posix = str(repo_rel).replace("\\", "/")

    # Always allow session artifacts
    session = get_session_from_env()
    if session:
        sessions_dir = get_sessions_dir(project_root)
        sessions_prefix = sessions_dir.rstrip("/") + "/"
        if repo_rel_posix.startswith(sessions_prefix):
            return _allow()

    # Check against scope
    if path_matches_scope(repo_rel_posix, writes):
        return _allow()

    preview = ", ".join(writes[:5])
    more = f" (+{len(writes) - 5} more)" if len(writes) > 5 else ""
    return _deny(
        f"Write to '{repo_rel_posix}' is outside declared scope.\n"
        f"Allowed: {preview}{more}\n"
        f"Stop and report if the plan scope is wrong."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Fail open on error
        print(json.dumps({"continue": True}))
        print(f"Hook error: {exc}", file=sys.stderr)
        raise SystemExit(0)
