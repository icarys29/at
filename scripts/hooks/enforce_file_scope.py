#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Enforce file scope restrictions on Write/Edit tools

Version: 0.5.0
Updated: 2026-02-02
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
from lib.active_session import resolve_session_dir_from_hook  # noqa: E402
from lib.io import load_json_safe, utc_now_full, write_json  # noqa: E402
from lib.session_env import get_file_scope_from_env, get_session_from_env  # noqa: E402


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


def _task_map_path(session_dir: Path) -> Path:
    return session_dir / "status" / "transcript_task_map.json"


def _load_task_map(session_dir: Path) -> dict[str, Any]:
    data = load_json_safe(_task_map_path(session_dir), default={})
    return data if isinstance(data, dict) else {}


def _save_task_map(session_dir: Path, data: dict[str, Any]) -> None:
    try:
        write_json(_task_map_path(session_dir), data)
    except Exception:
        pass


def _remember_task_for_transcript(session_dir: Path, transcript_path: str, task_id: str, method: str) -> None:
    if not transcript_path or not task_id:
        return
    data = _load_task_map(session_dir)
    mappings = data.get("mappings")
    if not isinstance(mappings, dict):
        mappings = {}
    mappings[transcript_path] = {"task_id": task_id, "method": method, "updated_at": utc_now_full()}
    data["version"] = 1
    data["updated_at"] = utc_now_full()
    data["mappings"] = mappings
    _save_task_map(session_dir, data)


def _get_task_from_task_map(session_dir: Path, transcript_path: str) -> str | None:
    data = _load_task_map(session_dir)
    mappings = data.get("mappings")
    if not isinstance(mappings, dict):
        return None
    entry = mappings.get(transcript_path)
    if not isinstance(entry, dict):
        return None
    tid = entry.get("task_id")
    return tid.strip() if isinstance(tid, str) and tid.strip() else None


def _find_task_id_in_transcript(transcript_path: Path, *, max_bytes: int = 300_000) -> str | None:
    text = _read_tail(transcript_path, max_bytes=max_bytes)
    if not text:
        return None
    m = re.search(r"inputs/task_context/(?P<task>[A-Za-z0-9_.-]+)\\.md", text)
    if m:
        return m.group("task")
    return None


def _infer_task_id_from_target(repo_rel_posix: str, tasks: dict[str, Any]) -> tuple[str | None, list[str]]:
    """
    Best-effort inference: find the unique task whose declared writes include repo_rel_posix.
    Returns (task_id, candidates).
    """
    candidates: list[str] = []
    for tid, meta in tasks.items():
        if not isinstance(tid, str) or not tid.strip():
            continue
        if not isinstance(meta, dict):
            continue
        fs = meta.get("file_scope")
        if not isinstance(fs, dict):
            continue
        writes = fs.get("writes")
        if not isinstance(writes, list):
            continue
        if _allowed_by_writes(repo_rel_posix, writes):
            candidates.append(tid)
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


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

    # PREFERRED: Check env-based file scope first (set by orchestrator via set_file_scope_env)
    env_writes = get_file_scope_from_env()
    if env_writes:
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

        # Always allow session artifacts
        sessions_prefix = sessions_dir.rstrip("/") + "/"
        if repo_rel_posix == sessions_dir.rstrip("/") or repo_rel_posix.startswith(sessions_prefix):
            return 0

        # Check against env scope
        if _allowed_by_writes(repo_rel_posix, env_writes):
            return 0

        preview = ", ".join(env_writes[:8])
        more = "" if len(env_writes) <= 8 else f" (+{len(env_writes) - 8} more)"
        return _deny(
            f"Out-of-scope {tool_name}: {repo_rel_posix!r}. "
            f"Allowed writes (from AT_FILE_SCOPE_WRITES): {preview}{more}. "
            "Stop and report if the plan file scope is wrong."
        )

    # FALLBACK: Use manifest-based resolution (legacy behavior)

    # Prefer deterministic resolution of the active SESSION_DIR using hook input (session_id),
    # falling back to transcript heuristics only when necessary.
    claude_session_id = hook_input.get("session_id")
    active = resolve_session_dir_from_hook(
        project_root=project_root,
        sessions_dir=sessions_dir,
        claude_session_id=str(claude_session_id) if isinstance(claude_session_id, str) else None,
    )

    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return 0

    # If we can't resolve a session, fail open (do not interfere with non-at usage).
    session_dir = active.session_dir if active else None
    task_id: str | None = None
    if session_dir is None:
        session_dir, task_id = _find_session_and_task(project_root, sessions_dir, Path(transcript_path).expanduser())
        if session_dir is None:
            return 0
    else:
        # Try cached mapping first (supports parallel subagent transcripts).
        task_id = _get_task_from_task_map(session_dir, transcript_path)

    manifest_path = session_dir / "inputs" / "task_context_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return 0  # no manifest => not in an at execution context

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

    tasks = (manifest.get("tasks") or {}) if isinstance(manifest, dict) else {}
    if not isinstance(tasks, dict):
        return 0

    # Resolve task_id if missing: transcript parsing, then best-effort inference from target path.
    if not task_id:
        found = _find_task_id_in_transcript(Path(transcript_path).expanduser())
        if found:
            task_id = found
            _remember_task_for_transcript(session_dir, transcript_path, task_id, "transcript")

    if not task_id:
        inferred, candidates = _infer_task_id_from_target(repo_rel_posix, tasks)
        if inferred:
            task_id = inferred
            _remember_task_for_transcript(session_dir, transcript_path, task_id, "inferred-from-target")
        else:
            preview = ", ".join(sorted(candidates)[:12])
            more = "" if len(candidates) <= 12 else f" (+{len(candidates) - 12} more)"
            return _deny(
                f"Cannot determine active task for {tool_name} to {repo_rel_posix!r}. "
                "Remediation: ensure the subagent reads `SESSION_DIR/inputs/task_context/<task_id>.md` before editing, "
                "or ensure file_scope.writes uniquely identifies the task. "
                f"Candidate tasks for this path: {preview}{more}."
            )

    task = (tasks.get(task_id) or {}) if isinstance(tasks.get(task_id), dict) else {}
    fs = task.get("file_scope") if isinstance(task.get("file_scope"), dict) else {}
    writes = fs.get("writes") if isinstance(fs.get("writes"), list) else []
    if not isinstance(writes, list) or not writes:
        # If the task declares no writes, we can't enforce. Fail open to avoid blocking workflows
        # that deliberately omit file_scope.writes (e.g., sequential plans).
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
