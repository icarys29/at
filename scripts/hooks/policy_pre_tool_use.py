#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Policy hook (secrets + destructive commands)

Blocks:
- Reads/writes of forbidden secret paths (`policies.forbid_secrets_globs`)
- Destructive Bash commands (rm -rf, git push --force, etc.)

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

from lib.path_policy import forbid_secrets_globs_from_project_yaml, is_forbidden_path, normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


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


def _is_destructive_shell(command: str) -> str | None:
    c = command.strip()
    if not c:
        return None
    compact = re.sub(r"\\s+", " ", c)

    patterns: list[tuple[str, str]] = [
        (r"(?i)(^|[;&|])\\s*rm\\s+-[\\w-]*r[\\w-]*f[\\w-]*\\s+", "rm -rf (or equivalent)"),
        (r"(?i)\\bgit\\s+push\\b[^\\n]*\\s(--force|-f)\\b", "git push --force/-f"),
        (r"(?i)\\bgit\\s+clean\\b[^\\n]*\\s-?f[^\\n]*\\s-?d\\b", "git clean -fd (deletes untracked files)"),
        (r"(?i)\\bmkfs\\.", "mkfs.* (format disk)"),
    ]
    for pat, label in patterns:
        if re.search(pat, compact):
            return label
    # Prevent accidental exfiltration of local E2E env secrets via terminal output.
    # Users should run E2E via deterministic runners that load env internally.
    if re.search(r"(?i)\be2e/\.env\b", compact) and re.search(r"(?i)\b(cat|less|more|head|tail|sed|awk|grep|rg|python|node|ruby|perl)\b", compact):
        return "direct read of e2e/.env (use runner; do not print secrets)"
    return None


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PreToolUse":
        return 0

    tool_name = hook_input.get("tool_name")
    if tool_name not in {"Read", "Write", "Edit", "Bash"}:
        return 0

    project_root = detect_project_dir()
    forbid = forbid_secrets_globs_from_project_yaml(project_root)

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    if tool_name in {"Read", "Write", "Edit"}:
        fp = tool_input.get("file_path")
        if not isinstance(fp, str) or not fp.strip():
            return 0
        target = Path(fp).expanduser()
        try:
            abs_path = target.resolve()
        except Exception:
            return 0
        try:
            rel = abs_path.relative_to(project_root.resolve())
        except Exception:
            return 0
        rel_posix = str(rel).replace("\\", "/")
        norm = normalize_repo_relative_posix_path(rel_posix)
        if not norm:
            return 0
        if is_forbidden_path(norm, forbid):
            return _deny(f"Blocked {tool_name} of forbidden secret path: {norm!r} (policies.forbid_secrets_globs)")
        return 0

    if tool_name == "Bash":
        cmd = tool_input.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return 0
        label = _is_destructive_shell(cmd)
        if label:
            return _deny(f"Blocked destructive shell command ({label}). Use a safer alternative or remove policy hooks if intentional.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
