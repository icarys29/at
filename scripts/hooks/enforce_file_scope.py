#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Enforce file scope restrictions on Write/Edit tools

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path  # noqa: E402


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _read_tail(path: Path, *, max_bytes: int = 300_000) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if max_bytes > 0 and len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="ignore")


def _find_session_and_task(project_root: Path, sessions_dir: str, transcript_path: Path) -> tuple[Path | None, str | None]:
    text = _read_tail(transcript_path)
    if not text:
        return (None, None)

    # Prefer concrete task context paths.
    m = re.search(
        rf"(?P<base>/[^\s\"']+?|{re.escape(sessions_dir)}/[^\s\"']+?)/inputs/task_context/(?P<task>[A-Za-z0-9_.-]+)\\.md",
        text,
    )
    if m:
        base = m.group("base").strip("\"'")
        session_dir = Path(base) if base.startswith("/") else (project_root / base)
        session_dir = session_dir.resolve()
        if (session_dir / "session.json").exists():
            return (session_dir, m.group("task"))

    # Fallback: newest session dir + any task id mentioned.
    task_id = None
    m2 = re.search(r"inputs/task_context/(?P<task>[A-Za-z0-9_.-]+)\\.md", text)
    if m2:
        task_id = m2.group("task")

    root = (project_root / sessions_dir).resolve()
    if not root.exists() or not root.is_dir():
        return (None, task_id)

    best: tuple[float, Path] | None = None
    try:
        for p in root.iterdir():
            if not p.is_dir():
                continue
            if not (p / "session.json").exists():
                continue
            try:
                mtime = p.stat().st_mtime
            except Exception:
                continue
            if best is None or mtime > best[0]:
                best = (mtime, p)
    except Exception:
        return (None, task_id)

    return (best[1] if best else None, task_id)


def _allowed_by_writes(repo_rel_posix: str, writes: list[str]) -> bool:
    for w in writes:
        if not isinstance(w, str) or not w.strip():
            continue
        raw = w.strip().replace("\\", "/")
        is_dir = raw.endswith("/")
        norm = normalize_repo_relative_posix_path(raw)
        if not norm:
            continue
        if is_dir and not norm.endswith("/"):
            norm = norm + "/"
        if is_dir:
            if repo_rel_posix.startswith(norm):
                return True
        else:
            if repo_rel_posix == norm:
                return True
    return False


def _deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            }
        )
    )
    return 0


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PreToolUse":
        return 0

    tool_name = hook_input.get("tool_name")
    if tool_name not in {"Write", "Edit"}:
        return 0

    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return 0

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return 0

    project_root = detect_project_dir()
    sessions_dir = get_sessions_dir(project_root)

    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return 0

    session_dir, task_id = _find_session_and_task(project_root, sessions_dir, Path(transcript_path).expanduser())
    if session_dir is None or not task_id:
        return 0

    manifest_path = session_dir / "inputs" / "task_context_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    task = ((manifest.get("tasks") or {}).get(task_id) or {}) if isinstance(manifest, dict) else {}
    writes = ((task.get("file_scope") or {}).get("writes") or []) if isinstance(task, dict) else []
    if not isinstance(writes, list) or not writes:
        return 0

    target = Path(file_path).expanduser()
    try:
        target_abs = target.resolve()
    except Exception:
        return _deny(f"Refusing to {tool_name} an unresolvable path: {file_path!r}")

    try:
        repo_rel = target_abs.relative_to(project_root)
    except Exception:
        return _deny(f"Out-of-scope {tool_name}: {file_path!r} is outside the project root")

    repo_rel_posix = str(repo_rel).replace("\\", "/")

    # Always allow session artifacts.
    sessions_prefix = sessions_dir.rstrip("/") + "/"
    if repo_rel_posix == sessions_dir.rstrip("/") or repo_rel_posix.startswith(sessions_prefix):
        return 0

    if _allowed_by_writes(repo_rel_posix, writes):
        return 0

    preview = ", ".join([w for w in writes[:12] if isinstance(w, str)])
    more = "" if len(writes) <= 12 else f" (+{len(writes) - 12} more)"
    return _deny(
        f"Out-of-scope {tool_name} for task {task_id!r}: {repo_rel_posix!r}. "
        f"Allowed file_scope.writes: {preview}{more}. "
        "Stop and report if the plan file scope is wrong."
    )


if __name__ == "__main__":
    start = time.time()
    try:
        raise SystemExit(main())
    finally:
        _ = start
