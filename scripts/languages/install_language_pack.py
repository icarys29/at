#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install a language pack into a project's overlay (rules + pack metadata)

Installs (project-local):
- `.claude/rules/at/lang/<lang>.md` (concise guidance)
- `.claude/at/languages/<lang>.json` (structured metadata for planner/gates)

This is intentionally safe and deterministic:
- no edits to project source code
- no automatic mutation of `.claude/project.yaml`
- installs only files under `.claude/`

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


SUPPORTED = {"python", "go", "typescript", "rust"}


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")


def _write_file(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def _write_json(path: Path, obj: dict[str, Any], *, force: bool) -> str:
    return _write_file(path, json.dumps(obj, indent=2, sort_keys=True) + "\n", force=force)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install an at language pack into the current project.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--lang", required=True, choices=sorted(SUPPORTED))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()
    lang = str(args.lang).strip()

    pack_path = f"templates/languages/{lang}/pack.json"
    pack = json.loads(_read_template(plugin_root, pack_path))
    if not isinstance(pack, dict) or pack.get("version") != 1 or pack.get("language") != lang:
        raise RuntimeError(f"Invalid pack template: {pack_path}")

    rules_md_template = pack.get("rules_md_template")
    if not isinstance(rules_md_template, str) or not rules_md_template.strip():
        raise RuntimeError(f"Pack missing rules_md_template: {pack_path}")

    # rules_md_template is stored as a template path under plugin root.
    rules_src = rules_md_template.strip()
    rules_content = _read_template(plugin_root, rules_src)

    results: list[tuple[str, str]] = []
    results.append(
        (
            _write_file(project_root / ".claude" / "rules" / "at" / "lang" / f"{lang}.md", rules_content, force=args.force),
            f".claude/rules/at/lang/{lang}.md",
        )
    )
    results.append(
        (
            _write_json(project_root / ".claude" / "at" / "languages" / f"{lang}.json", pack, force=args.force),
            f".claude/at/languages/{lang}.json",
        )
    )

    for status, rel in results:
        print(f"{status}\t{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
