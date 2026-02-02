#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Help (command index + quickstart)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "help.py is deprecated and will be removed in v0.5.0. "
    "Help content lives in SKILL.md. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import get_plugin_root, get_plugin_version  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    argument_hint: str
    path: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_frontmatter_block(text: str) -> str | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, min(len(lines), 300)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    return "\n".join(lines[1:end]) + "\n"


def _count_indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _escape_yaml_double_quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _collapse_block_scalars(frontmatter: str) -> str:
    """
    Convert YAML block scalars (>, |) into quoted scalar strings so they can be
    parsed by lib.simple_yaml.load_minimal_yaml (which intentionally supports a
    smaller YAML subset).
    """
    lines = frontmatter.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.lstrip(" ")
        indent = _count_indent(raw)
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            out.append(raw)
            i += 1
            continue

        key, rest = stripped.split(":", 1)
        key = key.strip()
        rest = rest.lstrip(" ")
        if key and rest and rest[0] in {"|", ">"}:
            style = rest[0]
            j = i + 1
            block_lines: list[str] = []
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    block_lines.append("")
                    j += 1
                    continue
                nxt_indent = _count_indent(nxt)
                if nxt_indent <= indent:
                    break
                block_lines.append(nxt)
                j += 1

            content_indent = None
            for bl in block_lines:
                if not isinstance(bl, str) or not bl.strip():
                    continue
                content_indent = _count_indent(bl) if content_indent is None else min(content_indent, _count_indent(bl))

            norm: list[str] = []
            for bl in block_lines:
                if not bl:
                    norm.append("")
                    continue
                if content_indent is None:
                    norm.append(bl.lstrip(" "))
                else:
                    norm.append(bl[content_indent:] if len(bl) >= content_indent else bl.lstrip(" "))

            if style == "|":
                value = "\n".join(norm).strip()
            else:
                value = " ".join([x.strip() for x in norm if x.strip()]).strip()

            out.append(" " * indent + f'{key}: "{_escape_yaml_double_quoted(value)}"')
            i = j
            continue

        out.append(raw)
        i += 1

    return "\n".join(out) + "\n"


def _parse_frontmatter(text: str) -> dict[str, Any]:
    fm = _extract_frontmatter_block(text)
    if fm is None:
        return {}
    try:
        data = load_minimal_yaml(_collapse_block_scalars(fm))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sanitize_one_line(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _iter_skills(plugin_root: Path) -> Iterable[SkillInfo]:
    for p in sorted((plugin_root / "skills").glob("*/SKILL.md")):
        raw = _read_text(p)
        fm = _parse_frontmatter(raw)
        name = _sanitize_one_line(fm.get("name")) or p.parent.name
        desc = _sanitize_one_line(fm.get("description"))
        arg = _sanitize_one_line(fm.get("argument-hint") or fm.get("argument_hint"))
        yield SkillInfo(name=name, description=desc, argument_hint=arg, path=str(p))


def _to_json(skills: list[SkillInfo], *, plugin_version: str) -> dict[str, Any]:
    return {
        "version": 1,
        "plugin_version": plugin_version,
        "skills": [
            {"name": s.name, "description": s.description, "argument_hint": s.argument_hint, "path": s.path}
            for s in skills
        ],
    }


def _print_md(skills: list[SkillInfo], *, plugin_version: str) -> None:
    print("# at — Help")
    print("")
    print(f"- plugin_version: `{plugin_version}`")
    print("")
    print("## Quickstart")
    print("")
    print("1) `/at:init-project` (first time in a repo)")
    print("2) `/at:run \"<request>\"` (default workflow: deliver)")
    print("3) `/at:session-progress --session <id|dir>` (if anything stops/blocks)")
    print("")
    print("## Workflows (via /at:run)")
    print("")
    print("- `deliver` — plan → implement/tests → gates → docs → final artifacts")
    print("- `triage` — root-cause analysis + remediation options (no repo edits by default)")
    print("- `review` — evidence-backed review report from session artifacts")
    print("- `ideate` — architecture brief + options; no actions.json by default")
    print("")
    print("## Commands")
    print("")
    for s in skills:
        arg = f" `{s.argument_hint}`" if s.argument_hint else ""
        desc = f" — {s.description}" if s.description else ""
        print(f"- `/at:{s.name}`{arg}{desc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Print at help (command index + quickstart).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    plugin_root = get_plugin_root()
    plugin_version = get_plugin_version(plugin_root)

    skills = list(_iter_skills(plugin_root))
    # Hide internal/non-user-facing items if they exist without name.
    skills = [s for s in skills if s.name and s.name != "SKILL"]

    if args.json:
        print(json.dumps(_to_json(skills, plugin_version=plugin_version), indent=2, sort_keys=True))
        return 0

    _print_md(skills, plugin_version=plugin_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
