#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Session environment utilities - single source of truth for session resolution

Version: 0.4.0
Updated: 2026-02-02

This module provides the canonical way to resolve the current session directory.
All scripts and hooks should use these functions instead of ad-hoc resolution.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple


class SessionContext(NamedTuple):
    """Resolved session context."""
    session_dir: Path
    session_id: str
    resolution_method: str


# Environment variable names
ENV_SESSION_DIR = "AT_SESSION_DIR"
ENV_SESSION_ID = "AT_SESSION_ID"
ENV_FILE_SCOPE_WRITES = "AT_FILE_SCOPE_WRITES"


def get_session_from_env() -> SessionContext | None:
    """Get session from environment variables (preferred method).

    Returns:
        SessionContext if AT_SESSION_DIR is set and valid, None otherwise.
    """
    session_dir_str = os.environ.get(ENV_SESSION_DIR)
    if not session_dir_str:
        return None

    session_dir = Path(session_dir_str).expanduser().resolve()
    if not session_dir.is_dir():
        return None

    if not (session_dir / "session.json").exists():
        return None

    session_id = os.environ.get(ENV_SESSION_ID, session_dir.name)

    return SessionContext(
        session_dir=session_dir,
        session_id=session_id,
        resolution_method="environment",
    )


def set_session_env(session_dir: Path) -> None:
    """Set session environment variables.

    Call this from create_session.py and at the start of /at:run.

    Args:
        session_dir: The session directory path
    """
    resolved = session_dir.resolve()
    os.environ[ENV_SESSION_DIR] = str(resolved)
    os.environ[ENV_SESSION_ID] = resolved.name


def set_file_scope_env(writes: list[str]) -> None:
    """Set file scope environment variable for hooks.

    Call this before dispatching a subagent task.

    Args:
        writes: List of allowed write paths for the task
    """
    os.environ[ENV_FILE_SCOPE_WRITES] = ":".join(writes)


def get_file_scope_from_env() -> list[str]:
    """Get allowed write paths from environment.

    Returns:
        List of allowed write paths, or empty list if not set.
    """
    scope_str = os.environ.get(ENV_FILE_SCOPE_WRITES, "")
    if not scope_str:
        return []
    return [p.strip() for p in scope_str.split(":") if p.strip()]


def clear_session_env() -> None:
    """Clear session environment variables."""
    for var in [ENV_SESSION_DIR, ENV_SESSION_ID, ENV_FILE_SCOPE_WRITES]:
        os.environ.pop(var, None)
