#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Active session helpers (best-effort)

Stores a small mapping under the configured sessions root to help hooks resolve
the current at `SESSION_DIR` without transcript heuristics.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.io import utc_now_full


ACTIVE_SESSION_FILE = ".at_active_session.json"
SESSION_LINKS_FILE = ".at_session_links.json"

# Keep the mapping small to avoid unbounded growth.
MAX_SESSION_LINKS = 50


@dataclass(frozen=True)
class ActiveSession:
    session_id: str
    session_dir: Path


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_valid_session_dir(sessions_root: Path, session_id: str) -> bool:
    if not session_id or not session_id.strip():
        return False
    p = (sessions_root / session_id.strip()).resolve()
    return p.is_dir() and (p / "session.json").exists()


def _read_active_session_id(sessions_root: Path) -> str | None:
    data = _load_json(sessions_root / ACTIVE_SESSION_FILE)
    if not data:
        return None
    sid = data.get("session_id")
    if isinstance(sid, str) and sid.strip() and _is_valid_session_dir(sessions_root, sid.strip()):
        return sid.strip()
    return None


def write_active_session(
    sessions_root: Path,
    *,
    session_id: str,
    claude_session_id: str | None = None,
) -> None:
    """
    Best-effort update:
    - sessions_root/.at_active_session.json
    - sessions_root/.at_session_links.json (if claude_session_id provided)
    """
    sessions_root.mkdir(parents=True, exist_ok=True)

    _write_json(
        sessions_root / ACTIVE_SESSION_FILE,
        {"version": 1, "updated_at": utc_now_full(), "session_id": session_id},
    )

    if not claude_session_id or not claude_session_id.strip():
        return

    links_path = sessions_root / SESSION_LINKS_FILE
    links = _load_json(links_path) or {}
    entries = links.get("entries") if isinstance(links.get("entries"), list) else []

    # Keep a list of {claude_session_id, session_id, updated_at} entries (most recent last).
    new_entries: list[dict[str, Any]] = []
    for it in entries:
        if not isinstance(it, dict):
            continue
        csid = it.get("claude_session_id")
        if not isinstance(csid, str) or not csid.strip():
            continue
        if csid.strip() == claude_session_id.strip():
            continue
        new_entries.append(it)

    new_entries.append(
        {
            "claude_session_id": claude_session_id.strip(),
            "session_id": session_id,
            "updated_at": utc_now_full(),
        }
    )
    new_entries = new_entries[-MAX_SESSION_LINKS:]

    _write_json(
        links_path,
        {
            "version": 1,
            "updated_at": utc_now_full(),
            "entries": new_entries,
        },
    )


def resolve_session_dir_from_hook(
    *,
    project_root: Path,
    sessions_dir: str,
    claude_session_id: str | None,
) -> ActiveSession | None:
    """
    Best-effort resolution of the active at session directory for a Claude session:
    1) sessions_root/.at_session_links.json (keyed by Claude session id)
    2) sessions_root/.at_active_session.json (last created/resumed)
    """
    sessions_root = (project_root / sessions_dir).resolve()
    if not sessions_root.exists():
        return None

    # 1) Link mapping (preferred).
    if claude_session_id and claude_session_id.strip():
        links = _load_json(sessions_root / SESSION_LINKS_FILE) or {}
        entries = links.get("entries") if isinstance(links.get("entries"), list) else []
        for it in reversed(entries):
            if not isinstance(it, dict):
                continue
            csid = it.get("claude_session_id")
            sid = it.get("session_id")
            if not isinstance(csid, str) or not isinstance(sid, str):
                continue
            if csid.strip() != claude_session_id.strip():
                continue
            if _is_valid_session_dir(sessions_root, sid.strip()):
                session_dir = (sessions_root / sid.strip()).resolve()
                return ActiveSession(session_id=sid.strip(), session_dir=session_dir)

    # 2) Last active (fallback).
    sid = _read_active_session_id(sessions_root)
    if sid and _is_valid_session_dir(sessions_root, sid):
        session_dir = (sessions_root / sid).resolve()
        return ActiveSession(session_id=sid, session_dir=session_dir)

    return None
