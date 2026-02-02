#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: I/O utilities for file operations and timestamps

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Get current UTC timestamp as ISO string with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_now_full() -> str:
    """Get current UTC timestamp as full ISO string (with microseconds)."""
    return datetime.now(timezone.utc).isoformat()


def safe_read_text(path: Path, *, max_chars: int = 0) -> tuple[str, bool]:
    """
    Safely read text file with optional truncation.

    Returns (content, was_truncated). On error returns ("[ERROR ...]", False).
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"[ERROR reading {path}: {exc}]\n", False
    if max_chars > 0 and len(raw) > max_chars:
        return raw[:max_chars] + "\n\n[TRUNCATED]\n", True
    return raw, False


def write_text(path: Path, content: str) -> None:
    """Write text to file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any], *, indent: int = 2, sort_keys: bool = True) -> None:
    """Write JSON to file, creating parent directories as needed."""
    write_text(path, json.dumps(data, indent=indent, sort_keys=sort_keys) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file (raises RuntimeError on missing/invalid)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object in {path}, got {type(data)}")
    return data


def load_json_safe(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Load JSON file, returning default on error (never raises)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
