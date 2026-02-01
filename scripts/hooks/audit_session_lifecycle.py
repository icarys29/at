#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Audit hook (SessionStart/SessionEnd) - lifecycle logging

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
    if not payload:
        return 0

    ev = payload.get("hook_event_name")
    if ev not in {"SessionStart", "SessionEnd"}:
        return 0

    project_root = detect_project_dir()
    paths = ensure_audit_paths(project_root)

    record: dict[str, Any] = {
        "version": 1,
        "ts": utc_now(),
        "event": ev,
        "cwd": payload.get("cwd"),
        "session_id": payload.get("session_id"),
    }
    append_jsonl(paths.lifecycle_jsonl, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

