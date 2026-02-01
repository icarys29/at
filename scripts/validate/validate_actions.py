#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate actions.json structure

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from validate.actions_validator import validate_actions_file  # noqa: E402


def _resolve_actions_path(project_root: Path, sessions_dir: str, actions_path: str | None, session: str | None) -> Path:
    if actions_path:
        p = Path(actions_path).expanduser()
        if p.is_absolute():
            return p
        return (project_root / p).resolve()

    session_dir = resolve_session_dir(project_root, sessions_dir, session)
    return (session_dir / "planning" / "actions.json").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate planning/actions.json (schema + parallel execution invariants).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--actions-path", default=None, help="Path to actions.json (absolute or project-relative)")
    parser.add_argument("--session", default=None, help="Session id or directory (to find planning/actions.json)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    actions = _resolve_actions_path(project_root, sessions_dir, args.actions_path, args.session)

    errors = validate_actions_file(actions, project_root=project_root)
    if errors:
        print("FAIL: actions.json does not conform to the contract.", file=sys.stderr)
        print(f"File: {actions}", file=sys.stderr)
        for e in errors[:50]:
            print(f"- {e.path}: {e.message}", file=sys.stderr)
        if len(errors) > 50:
            print(f"- … ({len(errors) - 50} more)", file=sys.stderr)
        return 1

    print("OK: actions.json looks valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
