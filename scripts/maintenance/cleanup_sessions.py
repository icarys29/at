#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Cleanup sessions (dry-run default)

Prunes old session directories under workflow.sessions_dir.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402


def _is_session_dir(p: Path) -> bool:
    return p.is_dir() and (p / "session.json").exists()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune old at sessions (dry-run default).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--keep", type=int, default=50, help="Keep newest N sessions.")
    parser.add_argument("--days", type=int, default=0, help="Also prune sessions older than N days (0 disables).")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    root = (project_root / sessions_dir).resolve()
    if not root.exists():
        print("OK\t(no sessions dir)")
        return 0

    sessions = [p for p in sorted(root.iterdir(), reverse=True) if _is_session_dir(p)]
    keep_n = max(0, int(args.keep))
    cutoff = time.time() - (max(0, int(args.days)) * 86400) if args.days and args.days > 0 else None

    to_delete = sessions[keep_n:]
    if cutoff is not None:
        to_delete = [p for p in to_delete if p.stat().st_mtime < cutoff]

    if not to_delete:
        print("OK\t(no sessions to prune)")
        return 0

    for p in to_delete:
        rel = str(p.relative_to(project_root)).replace("\\", "/")
        action = "DELETE" if args.apply else "DRYRUN_DELETE"
        print(f"{action}\t{rel}")
        if args.apply:
            try:
                for child in sorted(p.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        child.rmdir()
                p.rmdir()
            except Exception as exc:
                print(f"WARNING: failed to delete {p}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

