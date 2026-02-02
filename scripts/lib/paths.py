#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Canonical path utilities - single source of truth for path handling

Version: 0.5.0
Updated: 2026-02-02

This module provides canonical path utilities for consistent path handling
across all scripts and hooks.
"""
from __future__ import annotations

import re
from pathlib import Path


def normalize_to_repo_relative_posix(path: str | Path, *, project_root: Path | None = None) -> str | None:
    """Normalize a path to repo-relative POSIX format.

    Args:
        path: Input path (can be absolute, relative, or already repo-relative)
        project_root: Project root for resolving relative paths

    Returns:
        Repo-relative POSIX path (e.g., "src/foo/bar.py"), or None if invalid
    """
    if not path:
        return None

    path_str = str(path).strip()
    if not path_str:
        return None

    # Reject paths with directory traversal
    if ".." in path_str:
        return None

    # Convert to Path and normalize
    p = Path(path_str)

    # If absolute, try to make relative to project_root
    if p.is_absolute():
        if project_root is None:
            return None
        try:
            p = p.resolve().relative_to(project_root.resolve())
        except ValueError:
            return None  # Path is outside project root

    # Convert to POSIX format
    result = str(p).replace("\\", "/")

    # Remove leading ./
    if result.startswith("./"):
        result = result[2:]

    # Remove leading /
    result = result.lstrip("/")

    # Reject empty result
    if not result:
        return None

    return result


def is_safe_repo_path(path: str) -> bool:
    """Check if a path is safe (no traversal, no absolute paths).

    Args:
        path: Path to check

    Returns:
        True if the path is safe for repo-relative operations
    """
    if not path or not isinstance(path, str):
        return False

    path = path.strip()

    # Reject empty paths
    if not path:
        return False

    # Reject absolute paths
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return False

    # Reject directory traversal
    if ".." in path:
        return False

    # Reject paths starting with ~
    if path.startswith("~"):
        return False

    return True


def resolve_from_session(
    session_dir: Path,
    path: str,
    *,
    allow_absolute: bool = False,
) -> Path | None:
    """Resolve a path relative to a session directory.

    Args:
        session_dir: Session directory
        path: Path to resolve (relative to session)
        allow_absolute: Whether to allow absolute paths (default False)

    Returns:
        Resolved absolute path, or None if invalid
    """
    if not path or not isinstance(path, str):
        return None

    path = path.strip()
    if not path:
        return None

    p = Path(path)

    if p.is_absolute():
        if not allow_absolute:
            return None
        return p.resolve()

    # Resolve relative to session
    return (session_dir / p).resolve()


def path_matches_scope(path: str, scope: list[str]) -> bool:
    """Check if a path matches any pattern in a scope list.

    Args:
        path: Repo-relative POSIX path to check
        scope: List of allowed patterns (exact paths or directory prefixes ending in /)

    Returns:
        True if the path is allowed by the scope
    """
    if not path or not scope:
        return False

    path = normalize_to_repo_relative_posix(path) or path

    for pattern in scope:
        if not isinstance(pattern, str) or not pattern.strip():
            continue

        pattern = pattern.strip().replace("\\", "/")

        # Directory prefix (ends with /)
        if pattern.endswith("/"):
            if path.startswith(pattern) or path + "/" == pattern:
                return True
        # Exact match
        elif path == pattern:
            return True

    return False


def has_glob_chars(path: str) -> bool:
    """Check if a path contains glob characters.

    Args:
        path: Path to check

    Returns:
        True if the path contains glob characters
    """
    return bool(re.search(r"[*?\[\]]", path or ""))


def validate_write_scope(writes: list[str]) -> list[str]:
    """Validate a write scope list.

    Args:
        writes: List of write scope entries

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not writes:
        return errors

    for i, w in enumerate(writes):
        if not isinstance(w, str) or not w.strip():
            errors.append(f"writes[{i}]: empty or invalid entry")
            continue

        w = w.strip()

        if has_glob_chars(w):
            errors.append(f"writes[{i}]: glob patterns not allowed in writes ('{w}')")

        if not is_safe_repo_path(w.rstrip("/")):
            errors.append(f"writes[{i}]: unsafe path ('{w}')")

    return errors
