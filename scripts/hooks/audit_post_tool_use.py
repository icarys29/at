#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Audit hook (PostToolUse) - tool usage logging

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

from audit.audit_log import append_jsonl, ensure_audit_paths, traces_enabled  # noqa: E402
from lib.io import utc_now_full  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def main() -> int:
    payload = _read_hook_input()
    if not payload or payload.get("hook_event_name") != "PostToolUse":
        return 0

    project_root = detect_project_dir()
    paths = ensure_audit_paths(project_root)

    tool_name = payload.get("tool_name")
    tool_output = payload.get("tool_output")
    tool_call_id = payload.get("tool_call_id") or payload.get("tool_use_id") or payload.get("tool_request_id")

    safe_result: dict[str, Any] = {}
    if isinstance(tool_output, dict):
        if isinstance(tool_output.get("exit_code"), int):
            safe_result["exit_code"] = int(tool_output.get("exit_code"))
        if isinstance(tool_output.get("ok"), bool):
            safe_result["ok"] = bool(tool_output.get("ok"))
        if isinstance(tool_output.get("status"), str) and tool_output.get("status").strip():
            safe_result["status"] = tool_output.get("status").strip()
        if isinstance(tool_output.get("error"), str) and tool_output.get("error").strip():
            safe_result["error"] = tool_output.get("error").strip()

    record: dict[str, Any] = {
        "version": 1,
        "ts": utc_now_full(),
        "event": "PostToolUse",
        "tool_name": tool_name,
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
    }
    if isinstance(tool_call_id, str) and tool_call_id.strip():
        record["tool_call_id"] = tool_call_id.strip()
    if safe_result:
        record["result"] = safe_result
    if traces_enabled():
        record["tool_output"] = tool_output
    append_jsonl(paths.tools_jsonl, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
