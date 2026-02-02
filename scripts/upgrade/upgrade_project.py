#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Upgrade project overlay to current templates (conservative, dry-run default)

This is a thin wrapper around `scripts/upgrade/migrate_overlay.py`.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade at overlay in a conservative way (dry-run default).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", default=None, help="Rollback from a backup dir created by migrate_overlay.py apply.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    migrate = (SCRIPT_ROOT / "upgrade" / "migrate_overlay.py").resolve()
    if not migrate.exists():
        raise RuntimeError(f"Missing migrate_overlay.py: {migrate}")

    cmd: list[str]
    if args.rollback:
        cmd = [sys.executable, str(migrate), "--project-dir", str(project_root), "rollback", "--backup-dir", str(args.rollback)]
    elif args.apply:
        cmd = [sys.executable, str(migrate), "--project-dir", str(project_root), "apply"]
    else:
        cmd = [sys.executable, str(migrate), "--project-dir", str(project_root), "plan"]

    proc = subprocess.run(cmd, cwd=str(project_root))
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
