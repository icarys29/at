#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: List existing sessions

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    args = parser.parse_args()

    project_dir = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_dir)
    root = (project_dir / sessions_dir).resolve()
    if not root.exists():
        print(f"No sessions dir: {root}")
        return 0

    sessions = [p for p in sorted(root.iterdir()) if p.is_dir()]
    if not sessions:
        print(f"No sessions under: {root}")
        return 0

    for p in sessions:
        meta = p / "session.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            workflow = data.get("workflow", "?")
            status = data.get("status", "?")
            updated = data.get("updated_at", "?")

            progress = p / "status" / "session_progress.json"
            if progress.exists():
                try:
                    prog = json.loads(progress.read_text(encoding="utf-8"))
                except Exception:
                    prog = {}
                if isinstance(prog, dict) and isinstance(prog.get("overall_status"), str) and prog.get("overall_status"):
                    status = prog.get("overall_status")
                if isinstance(prog, dict) and isinstance(prog.get("generated_at"), str) and prog.get("generated_at"):
                    updated = prog.get("generated_at")

            print(f"{p.name}\t{workflow}\t{status}\t{updated}")
        else:
            print(f"{p.name}\t?\t?\t?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
