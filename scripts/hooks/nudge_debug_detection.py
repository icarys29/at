#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: UX nudge (debug detection) — warning only

PostToolUse hook that scans edited files for high-confidence debug statements.
Never blocks tool execution. Writes a small per-session state file to avoid
repeating the same warning many times.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.active_session import resolve_session_dir_from_hook  # noqa: E402
from lib.path_policy import forbid_secrets_globs_from_project_yaml, is_forbidden_path, normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402


STATE_REL = "status/ux_nudges_state.json"
MAX_SCAN_BYTES = 600_000

_CODE_EXTS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

_PATTERNS: dict[str, list[tuple[re.Pattern[str], str, str]]] = {
    "python": [
        (re.compile(r"\\b(pdb|ipdb)\\.set_trace\\s*\\("), "HIGH", "pdb.set_trace"),
        (re.compile(r"\\bbreakpoint\\s*\\("), "HIGH", "breakpoint()"),
        (re.compile(r"^\\s*(import\\s+(pdb|ipdb)\\b|from\\s+(pdb|ipdb)\\s+import\\b)"), "MED", "debugger import"),
    ],
    "javascript": [
        (re.compile(r"\\bdebugger\\s*;"), "HIGH", "debugger;"),
        (re.compile(r"\\bconsole\\.(log|debug|trace)\\s*\\("), "MED", "console.log/debug/trace"),
    ],
    "typescript": [
        (re.compile(r"\\bdebugger\\s*;"), "HIGH", "debugger;"),
        (re.compile(r"\\bconsole\\.(log|debug|trace)\\s*\\("), "MED", "console.log/debug/trace"),
    ],
    "go": [
        (re.compile(r"\\bpanic\\s*\\("), "MED", "panic(...)"),
    ],
    "rust": [
        (re.compile(r"\\bdbg!\\s*\\("), "MED", "dbg!(...)"),
    ],
}


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


def _repo_rel(project_root: Path, abs_path: Path) -> str | None:
    try:
        rel = abs_path.resolve().relative_to(project_root.resolve())
    except Exception:
        return None
    norm = normalize_repo_relative_posix_path(str(rel).replace("\\", "/"))
    return norm


def _scan_file(path: Path, language: str) -> list[dict[str, Any]]:
    try:
        data = path.read_bytes()
    except Exception:
        return []
    if len(data) > MAX_SCAN_BYTES:
        return []
    text = data.decode("utf-8", errors="ignore")
    lines = text.splitlines()

    matches: list[dict[str, Any]] = []
    patterns = _PATTERNS.get(language, [])
    if not patterns:
        return matches

    for i, line in enumerate(lines[:60_000], start=1):
        # Skip comment-only lines (best-effort).
        stripped = line.lstrip()
        if stripped.startswith(("#", "//")):
            continue
        for rx, sev, label in patterns:
            if rx.search(line):
                matches.append({"line": i, "severity": sev, "label": label})
                break
        if len(matches) >= 8:
            break
    return matches


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "PostToolUse":
        return 0
    tool = hook_input.get("tool_name")
    if tool not in {"Write", "Edit"}:
        return 0

    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
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

    abs_path = Path(file_path).expanduser()
    try:
        abs_path = abs_path.resolve()
    except Exception:
        return 0

    rel_posix = _repo_rel(project_root, abs_path)
    if not rel_posix:
        return 0

    forbid = forbid_secrets_globs_from_project_yaml(project_root)
    if is_forbidden_path(rel_posix, forbid):
        return 0

    ext = Path(rel_posix).suffix.lower()
    language = _CODE_EXTS.get(ext)
    if not language:
        return 0

    if not abs_path.exists() or not abs_path.is_file():
        return 0

    state = _load_state(active.session_dir)
    warned = state.get("debug_warned_paths")
    warned_set = {str(x) for x in warned} if isinstance(warned, list) else set()
    if rel_posix in warned_set:
        return 0

    matches = _scan_file(abs_path, language)
    if not matches:
        return 0

    # Update state first to reduce repeat warnings if hooks run concurrently.
    warned_set.add(rel_posix)
    state["debug_warned_paths"] = sorted(warned_set)
    _save_state(active.session_dir, state)

    sev_rank = {"HIGH": 3, "MED": 2, "LOW": 1}
    max_sev = max((sev_rank.get(m.get("severity", ""), 0) for m in matches if isinstance(m, dict)), default=0)
    sev_label = "HIGH" if max_sev >= 3 else ("MED" if max_sev >= 2 else "LOW")

    lines = [f"at nudge (debug/{sev_label}): potential debug statements detected in `{rel_posix}`"]
    for m in matches[:6]:
        if not isinstance(m, dict):
            continue
        ln = m.get("line")
        label = m.get("label")
        if isinstance(ln, int) and ln > 0 and isinstance(label, str) and label:
            lines.append(f"- L{ln}: {label}")
    lines.append("Consider removing before finalizing the change.")
    _warn("\\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
