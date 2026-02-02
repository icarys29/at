#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: UX nudge (compaction suggestion) — warning only

Stop hook that suggests conversation compaction when the transcript is large.
Never blocks stopping.

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.active_session import resolve_session_dir_from_hook  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402


STATE_REL = "status/ux_nudges_state.json"
TRANSCRIPT_BYTES_THRESHOLD = 1_000_000  # ~1MB


def _read_hook_input() -> dict[str, Any] | None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return None
    return data if isinstance(data, dict) else None







def _warn(message: str) -> None:
    print(json.dumps({"systemMessage": message}))


def _load_state(session_dir: Path) -> dict[str, Any]:
    p = session_dir / STATE_REL
    if not p.exists():
        return {"version": 1, "debug_warned_paths": [], "compact_warned": False}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"version": 1, "debug_warned_paths": [], "compact_warned": False}
    except Exception:
        return {"version": 1, "debug_warned_paths": [], "compact_warned": False}


def _save_state(session_dir: Path, state: dict[str, Any]) -> None:
    p = session_dir / STATE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        return


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "Stop":
        return 0

    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return 0

    project_root = detect_project_dir()
    sessions_dir = get_sessions_dir(project_root)
    claude_session_id = hook_input.get("session_id")
    active = resolve_session_dir_from_hook(
        project_root=project_root,
        sessions_dir=sessions_dir,
        claude_session_id=str(claude_session_id) if isinstance(claude_session_id, str) else None,
    )
    if not active:
        return 0

    state = _load_state(active.session_dir)
    if state.get("compact_warned") is True:
        return 0

    p = Path(transcript_path).expanduser()
    try:
        size = p.stat().st_size
    except Exception:
        return 0

    if size < TRANSCRIPT_BYTES_THRESHOLD:
        return 0

    state["compact_warned"] = True
    _save_state(active.session_dir, state)

    mb = size / (1024 * 1024)
    msg = (
        "at nudge (compact): this session transcript is large "
        f"(~{mb:.1f} MiB). Consider compacting before continuing to reduce context loss risk."
    )
    _warn(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
