#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Upgrade project overlay to current templates (conservative, dry-run default)

Currently manages:
- ensures docs registry filename standardization (no docs/REGISTRY.json)
- ensures templates/docs/DOCUMENTATION_REGISTRY.json exists (creates if missing)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


def _read_template(plugin_root: Path, rel_path: str) -> str:
    path = plugin_root / "templates" / rel_path
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade at overlay in a conservative way (dry-run default).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    actions: list[str] = []

    # Standardize registry name.
    drift = project_root / "docs" / "REGISTRY.json"
    if drift.exists():
        actions.append(f"DRIFT\t{drift} exists (manual fix recommended; not auto-deleting)")

    reg = project_root / "docs" / "DOCUMENTATION_REGISTRY.json"
    if not reg.exists():
        actions.append(f"CREATE\t{reg}")
        if args.apply:
            reg.parent.mkdir(parents=True, exist_ok=True)
            reg.write_text(_read_template(plugin_root, "docs/DOCUMENTATION_REGISTRY.json"), encoding="utf-8")

    for a in actions or ["OK\t(no overlay upgrades needed)"]:
        print(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

