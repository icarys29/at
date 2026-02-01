#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Audit hook (SubagentStop) - subagent lifecycle logging

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

from audit.audit_log import append_jsonl, ensure_audit_paths  # noqa: E402
from lib.io import utc_now  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def main() -> int:
    payload = _read_hook_input()
    if not payload or payload.get("hook_event_name") != "SubagentStop":
        return 0

    project_root = detect_project_dir()
    paths = ensure_audit_paths(project_root)

    record: dict[str, Any] = {
        "version": 1,
        "ts": utc_now(),
        "event": "SubagentStop",
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
        "agent": payload.get("agent"),
        "agent_transcript_path": payload.get("agent_transcript_path"),
    }
    append_jsonl(paths.subagents_jsonl, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

