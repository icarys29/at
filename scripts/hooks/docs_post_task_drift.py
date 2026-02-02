#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs drift detector (post-task; non-blocking)

If code changed in the active at session but docs registry wasn't touched, emit a warning.
Hooks must not modify docs.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.active_session import resolve_session_dir_from_hook  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _collect_changed_paths(session_dir: Path) -> tuple[set[str], set[str]]:
    """
    Returns:
      (all_changed_paths, doc_related_paths)
    """
    changed: set[str] = set()
    doc_related: set[str] = set()
    for p in sorted((session_dir / "implementation" / "tasks").glob("*.yaml")) + sorted((session_dir / "testing" / "tasks").glob("*.yaml")):
        data = _load_yaml(p)
        if not data:
            continue
        items = data.get("changed_files")
        if not isinstance(items, list):
            continue
        for it in items[:500]:
            if not isinstance(it, dict):
                continue
            fp = it.get("path")
            if not isinstance(fp, str) or not fp.strip():
                continue
            rel = fp.strip().replace("\\", "/")
            changed.add(rel)
            if rel.startswith("docs/") and rel.endswith(".md"):
                doc_related.add(rel)
            if rel in {"docs/DOCUMENTATION_REGISTRY.json", "docs/DOCUMENTATION_REGISTRY.md"}:
                doc_related.add(rel)
    return (changed, doc_related)


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "SubagentStop":
        return 0

    project_root = detect_project_dir()
    config = load_project_config(project_root) or {}
    sessions_dir = get_sessions_dir(project_root, config)
    claude_session_id = os.environ.get("CLAUDE_SESSION_ID")
    active = resolve_session_dir_from_hook(project_root=project_root, sessions_dir=sessions_dir, claude_session_id=claude_session_id)
    if not active:
        return 0

    session_dir = active.session_dir
    changed, doc_related = _collect_changed_paths(session_dir)
    if not changed:
        return 0

    # If the session touched non-doc files but did not touch docs registry or docs, warn.
    non_doc_changes = [p for p in changed if not p.startswith("docs/")]
    if non_doc_changes and not doc_related:
        msg = (
            "Docs drift risk: session changed code/files but did not touch docs registry or docs.\n"
            f"- Session: {session_dir.name}\n"
            "- Suggested next step: run `/at:docs-keeper sync --session <SESSION_DIR>` (or your project’s docs sync command)."
        )
        print(json.dumps({"systemMessage": msg}))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
