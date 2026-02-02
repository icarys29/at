#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Print learning status (best-effort)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "learning_status.py is deprecated and will be removed in v0.5.0. "
    "Agent can read state directly. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

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
