#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Archive planning outputs within a session (iteration support)

Moves existing planning artifacts into:
- SESSION_DIR/planning/history/<UTCSTAMP>/

This keeps iterative runs (ideate/planning) predictable without losing previous outputs.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _sanitize_stamp(stamp: str) -> str:
    # utc_now() is YYYY-MM-DDTHH:MM:SSZ; make it path-safe.
    return (
        stamp.strip()
        .replace(":", "")
        .replace("-", "")
        .replace("T", "-")
        .replace("Z", "Z")
        .replace(" ", "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive existing planning outputs under planning/history/ for a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[
            "planning/ARCHITECTURE_BRIEF.md",
            "planning/ARCHITECTURE_BRIEF.json",
            "planning/IDEATION.md",
            "planning/IDEATION.json",
        ],
        help="Session-relative paths to archive if they exist.",
    )
    parser.add_argument("--max-history", type=int, default=25, help="Keep at most this many history directories (best-effort).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    planning_dir = session_dir / "planning"
    planning_dir.mkdir(parents=True, exist_ok=True)

    existing: list[str] = []
    for rel in args.paths[:50]:
        if not isinstance(rel, str) or not rel.strip():
            continue
        p = (session_dir / rel.strip()).resolve()
        # Only move files under the session dir.
        try:
            p.relative_to(session_dir.resolve())
        except Exception:
            continue
        if p.exists() and p.is_file():
            existing.append(rel.strip())

    if not existing:
        print("(no planning outputs to archive)")
        return 0

    stamp = _sanitize_stamp(utc_now())
    dest_dir = planning_dir / "history" / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    moved: list[dict[str, str]] = []
    for rel in existing:
        src = (session_dir / rel).resolve()
        dest = (dest_dir / src.name).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            src.rename(dest)
            moved.append({"from": rel, "to": dest.relative_to(session_dir).as_posix()})
        except Exception:
            # Best-effort: if rename fails, skip.
            continue

    report = {"version": 1, "archived_at": utc_now(), "moved": moved}
    write_json(dest_dir / "archive_report.json", report)

    # Best-effort pruning (keep newest N by dir name).
    try:
        hist_root = planning_dir / "history"
        if hist_root.exists():
            dirs = sorted([p for p in hist_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
            for d in dirs[int(max(0, args.max_history)) :]:
                for child in d.glob("*"):
                    try:
                        if child.is_file():
                            child.unlink()
                    except Exception:
                        pass
                try:
                    d.rmdir()
                except Exception:
                    pass
    except Exception:
        pass

    print(str(dest_dir.relative_to(session_dir).as_posix()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

