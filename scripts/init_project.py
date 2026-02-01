#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Initialize project with at overlay

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_text  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_template(rel_path: str) -> str:
    path = _plugin_root() / "templates" / rel_path
    if not path.exists():
        raise RuntimeError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def _write_if_missing(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap `.claude/` overlay for the at plugin.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing overlay files (conservative by default).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    project_name = project_root.name

    results: list[tuple[str, str]] = []

    # .claude/project.yaml
    project_yaml = _read_template("project.yaml").replace("CHANGE_ME", project_name)
    results.append(
        (_write_if_missing(project_root / ".claude" / "project.yaml", project_yaml, force=args.force), ".claude/project.yaml")
    )

    # Rules
    results.append(
        (
            _write_if_missing(project_root / ".claude" / "rules" / "at" / "global.md", _read_template("rules/global.md"), force=args.force),
            ".claude/rules/at/global.md",
        )
    )
    # Project rules placeholder (non-destructive).
    project_rules_readme = (
        "# Project Rules\n\n"
        "Put repo-specific rules here (kept separate from plugin baseline rules).\n"
        "- Baseline: `.claude/rules/at/`\n"
        "- Project: `.claude/rules/project/`\n"
        "\n"
        f"- Initialized: {utc_now()}\n"
    )
    results.append(
        (
            _write_if_missing(project_root / ".claude" / "rules" / "project" / "README.md", project_rules_readme, force=False),
            ".claude/rules/project/README.md",
        )
    )

    # Docs scaffolding
    results.append(
        (
            _write_if_missing(project_root / "docs" / "DOCUMENTATION_REGISTRY.json", _read_template("docs/DOCUMENTATION_REGISTRY.json"), force=args.force),
            "docs/DOCUMENTATION_REGISTRY.json",
        )
    )
    results.append(
        (
            _write_if_missing(project_root / "docs" / "PROJECT_CONTEXT.md", _read_template("docs/PROJECT_CONTEXT.md"), force=args.force),
            "docs/PROJECT_CONTEXT.md",
        )
    )

    # Contributor pointer (optional; do not overwrite).
    pointer = (
        "# CLAUDE.md (project)\n\n"
        "If this repo uses the at plugin, add project-specific instructions here.\n"
        "Keep it short; prefer `.claude/rules/**` with `@imports` for larger rule sets.\n"
    )
    if not (project_root / "CLAUDE.md").exists():
        write_text(project_root / "CLAUDE.md", pointer)
        results.append(("CREATE", "CLAUDE.md"))
    else:
        results.append(("SKIP", "CLAUDE.md"))

    for status, rel in results:
        print(f"{status}\t{rel}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
