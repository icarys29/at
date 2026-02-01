#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: SessionStart hook to surface a small learning context snippet (best-effort, fail-open)

This hook attempts to provide a short system message pointing to recent learning status.
If the host does not surface `systemMessage` for SessionStart, it is harmless.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, load_project_config  # noqa: E402
from learning.learning_state import learning_root  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _emit_system_message(msg: str) -> None:
    try:
        print(json.dumps({"continue": True, "systemMessage": msg}))
    except Exception:
        return


def main() -> int:
    payload = _read_hook_input()
    if not payload or payload.get("hook_event_name") != "SessionStart":
        return 0

    project_root = detect_project_dir()
    cfg = load_project_config(project_root) or {}
    learning_cfg = cfg.get("learning") if isinstance(cfg.get("learning"), dict) else {}
    if isinstance(learning_cfg.get("enabled"), bool) and not learning_cfg.get("enabled"):
        return 0

    max_chars = 1200
    if isinstance(learning_cfg.get("sessionstart_context_max_chars"), int):
        max_chars = max(0, int(learning_cfg.get("sessionstart_context_max_chars")))

    root = learning_root(project_root)
    status = root / "STATUS.md"
    if not status.exists():
        return 0

    try:
        text = status.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return 0

    if not text:
        return 0

    # Allow opt-in disable via env for debugging.
    if os.environ.get("AT_DISABLE_SESSIONSTART_LEARNING", "").strip().lower() in {"1", "true", "yes"}:
        return 0

    snippet = text[:max_chars]
    _emit_system_message(f"[at] Learning status snippet:\n\n{snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

