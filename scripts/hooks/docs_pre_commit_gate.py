#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs pre-commit/PR gate (blocks)

Intercepts likely "commit/pr" Bash commands and runs docs lint.
Hooks must not modify docs: they detect and block; docs-keeper fixes.

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _bash_command_text(hook_input: dict[str, Any]) -> str:
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command")
    return cmd if isinstance(cmd, str) else ""


def _looks_like_commit_or_pr(cmd: str) -> bool:
    c = cmd.strip()
    if not c:
        return False
    # Basic heuristics; determinism here is about behavior predictability, not perfect detection.
    needles = ["git commit", "git merge", "gh pr", "git push", "git rebase"]
    return any(n in c for n in needles)


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PreToolUse":
        return 0
    if hook_input.get("tool_name") != "Bash":
        return 0

    cmd = _bash_command_text(hook_input)
    if not _looks_like_commit_or_pr(cmd):
        return 0

    project_root = detect_project_dir()
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or str(get_plugin_root())).resolve()
    lint_script = (plugin_root / "scripts" / "docs" / "docs_lint.py").resolve()
    if not lint_script.exists():
        return 0

    proc = subprocess.run(
        [sys.executable, str(lint_script), "--project-dir", str(project_root)],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode == 0:
        return 0

    out = (proc.stdout or "")[-4000:]
    reason = (
        "Docs lint failed. Fix docs drift before commit/PR.\n"
        "- Run: `/at:docs-keeper sync` (or your project’s docs sync command)\n"
        "- Details (tail):\n"
        + out
    )
    print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
