#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Setup E2E test scaffolding for a project (safe, guided)

Installs:
- e2e/README.md
- e2e/.env.example
- `.claude/at/e2e.json` (configuration for runner + gate)

Never creates `e2e/.env` (humans own secrets).

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")


def _write_if_missing(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def _ensure_gitignore_entry(project_root: Path, entry: str) -> str:
    gi = project_root / ".gitignore"
    entry = entry.strip()
    if not entry:
        return "SKIP"
    if not gi.exists():
        gi.write_text(entry + "\n", encoding="utf-8")
        return "CREATE"
    txt = gi.read_text(encoding="utf-8", errors="ignore")
    lines = [l.rstrip("\n") for l in txt.splitlines()]
    if entry in lines:
        return "SKIP"
    gi.write_text(txt.rstrip() + ("\n" if not txt.endswith("\n") else "") + entry + "\n", encoding="utf-8")
    return "UPDATE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup E2E scaffolding for an at-enabled project.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files (conservative by default).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    results: list[tuple[str, str]] = []
    results.append((_write_if_missing(project_root / "e2e" / "README.md", _read_template(plugin_root, "templates/e2e/README.md"), force=args.force), "e2e/README.md"))
    results.append(
        (_write_if_missing(project_root / "e2e" / ".env.example", _read_template(plugin_root, "templates/e2e/.env.example"), force=args.force), "e2e/.env.example")
    )

    e2e_cfg = json.loads(_read_template(plugin_root, "templates/claude/at/e2e.json"))
    results.append(
        (
            _write_if_missing(project_root / ".claude" / "at" / "e2e.json", json.dumps(e2e_cfg, indent=2, sort_keys=True) + "\n", force=args.force),
            ".claude/at/e2e.json",
        )
    )

    results.append((_ensure_gitignore_entry(project_root, "e2e/.env"), ".gitignore (ensure e2e/.env ignored)"))

    for status, rel in results:
        print(f"{status}\t{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
