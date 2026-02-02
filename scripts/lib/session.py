#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Session path helpers

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

from pathlib import Path


def resolve_session_dir(project_root: Path, sessions_dir: str, session_arg: str | None) -> Path:
    """
    Resolve a session directory.

    - If `session_arg` is a directory (absolute or project-relative) containing session.json, use it.
    - If `session_arg` is a session id, resolve it under `<project_root>/<sessions_dir>/<id>`.
    - If `session_arg` is None, pick the most recent session dir by name (timestamp prefix).
    """
    sessions_root = (project_root / sessions_dir).resolve()

    if session_arg:
        p = Path(session_arg).expanduser()
        for candidate in (p, project_root / p, sessions_root / session_arg):
            try:
                resolved = candidate.resolve()
            except Exception:
                continue
            if resolved.is_dir() and (resolved / "session.json").exists():
                return resolved
        raise RuntimeError(f"Session not found: {session_arg!r}")

    if not sessions_root.exists():
        raise RuntimeError(f"No sessions dir: {sessions_root}")
    candidates = [p for p in sorted(sessions_root.iterdir(), reverse=True) if p.is_dir() and (p / "session.json").exists()]
    if not candidates:
        raise RuntimeError(f"No sessions under: {sessions_root}")
    return candidates[0].resolve()
