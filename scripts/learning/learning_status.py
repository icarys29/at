#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Print learning status (best-effort)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir  # noqa: E402
from learning.learning_state import learning_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Show at learning status.")
    parser.add_argument("--project-dir", default=None)
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    root = learning_root(project_root)
    status = root / "STATUS.md"
    if status.exists():
        print(status.read_text(encoding="utf-8", errors="ignore"))
        return 0
    print("No learning status found. Run: uv run scripts/learning/update_learning_state.py --session <id>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

