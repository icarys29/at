#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate actions.json writes against the at contract

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir  # noqa: E402
from validate.actions_validator import validate_actions_data  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _is_actions_json_path(file_path: str) -> bool:
    if not file_path:
        return False
    normalized = file_path.replace("\\", "/")
    return normalized.endswith("/planning/actions.json") or normalized == "planning/actions.json"


def _strategy_override_for_actions_path(project_root: Path, file_path: str) -> str | None:
    try:
        p = Path(file_path).expanduser()
    except Exception:
        return None
    if not p.is_absolute():
        p = (project_root / p).resolve()
    try:
        resolved = p.resolve()
    except Exception:
        resolved = p
    if resolved.name != "actions.json" or resolved.parent.name != "planning":
        return None
    session_dir = resolved.parent.parent
    sess = session_dir / "session.json"
    if not sess.exists():
        return None
    try:
        data = json.loads(sess.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    st = data.get("workflow_strategy")
    return st if isinstance(st, str) and st in {"default", "tdd"} else None


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PostToolUse":
        return 0

    tool_name = hook_input.get("tool_name")
    if tool_name != "Write":
        return 0

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0
    file_path = tool_input.get("file_path")
    content = tool_input.get("content")
    if not isinstance(file_path, str) or not isinstance(content, str):
        return 0

    if not _is_actions_json_path(file_path):
        return 0

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"BLOCKED: planning/actions.json is not valid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print("BLOCKED: planning/actions.json root must be an object", file=sys.stderr)
        return 2

    project_root = detect_project_dir()
    strategy_override = _strategy_override_for_actions_path(project_root, file_path)
    errors = validate_actions_data(data, project_root=project_root, strategy_override=strategy_override)
    if errors:
        print("BLOCKED: planning/actions.json does not conform to the at contract.", file=sys.stderr)
        for e in errors[:20]:
            print(f"- {e.path}: {e.message}", file=sys.stderr)
        if len(errors) > 20:
            print(f"- … ({len(errors) - 20} more)", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
