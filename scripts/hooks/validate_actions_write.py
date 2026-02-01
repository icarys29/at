#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate actions.json writes against the at contract

Version: 0.1.0
Updated: 2026-02-01
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
    errors = validate_actions_data(data, project_root=project_root)
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
