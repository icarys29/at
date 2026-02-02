#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Onboarding helpers (repo analysis + deterministic overlay proposals)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    ".claude",
    ".session",
}





EXT_TO_LANG = {
    ".py": "python",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
}


def detect_languages(project_root: Path, *, max_files: int = 80_000) -> list[str]:
    """
    Best-effort language detection by file extension counts.
    """
    counts: Counter[str] = Counter()
    scanned = 0
    for root, dirs, files in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".git")]
        for fn in files:
            scanned += 1
            if max_files > 0 and scanned > max_files:
                break
            ext = Path(fn).suffix.lower()
            lang = EXT_TO_LANG.get(ext)
            if lang:
                counts[lang] += 1
        if max_files > 0 and scanned > max_files:
            break

    if not counts:
        return []
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in items[:4]]


def detect_package_manager(project_root: Path) -> str:
    if (project_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_root / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _load_package_json(project_root: Path) -> dict[str, Any] | None:
    p = project_root / "package.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _ts_script_cmd(pm: str, script: str) -> str:
    if pm == "yarn":
        return f"yarn {script}"
    return f"{pm} run {script}"


def suggest_commands(project_root: Path, languages: list[str]) -> dict[str, dict[str, str]]:
    """
    Produce best-effort command suggestions. Empty strings mean "unknown / leave unconfigured".
    """
    out: dict[str, dict[str, str]] = {}

    if "python" in languages:
        out["python"] = {
            "format": "python -m ruff format .",
            "lint": "python -m ruff check .",
            "typecheck": "python -m mypy .",
            "test": "python -m pytest -q",
            "build": "",
        }

    if "go" in languages and (project_root / "go.mod").exists():
        out["go"] = {"format": "gofmt -w .", "lint": "", "typecheck": "", "test": "go test ./...", "build": "go build ./..."}

    if "rust" in languages and (project_root / "Cargo.toml").exists():
        out["rust"] = {"format": "cargo fmt", "lint": "cargo clippy", "typecheck": "", "test": "cargo test", "build": "cargo build"}

    if "typescript" in languages and (project_root / "package.json").exists():
        pm = detect_package_manager(project_root)
        pkg = _load_package_json(project_root) or {}
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        out["typescript"] = {
            "format": _ts_script_cmd(pm, "format") if isinstance(scripts.get("format"), str) else "",
            "lint": _ts_script_cmd(pm, "lint") if isinstance(scripts.get("lint"), str) else "",
            "typecheck": _ts_script_cmd(pm, "typecheck") if isinstance(scripts.get("typecheck"), str) else "",
            "test": _ts_script_cmd(pm, "test") if isinstance(scripts.get("test"), str) else "",
            "build": _ts_script_cmd(pm, "build") if isinstance(scripts.get("build"), str) else "",
        }

    return out


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_project_yaml(*, template_text: str, project_name: str, languages: list[str], commands_by_lang: dict[str, dict[str, str]]) -> str:
    """
    Render `.claude/project.yaml` from the plugin template with safe substitutions:
    - project.name
    - project.primary_languages
    - commands section (generated from detected languages / heuristics)
    """
    langs = [l for l in languages if isinstance(l, str) and l.strip()]
    if not langs:
        langs = ["python"]

    # Generate commands YAML block.
    cmd_lines: list[str] = []
    cmd_lines.append("commands:")
    cmd_lines.append("  allow_language_pack_defaults: false")
    for lang in langs:
        block = commands_by_lang.get(lang) if isinstance(commands_by_lang.get(lang), dict) else {}
        cmd_lines.append(f"  {lang}:")
        for step in ("format", "lint", "typecheck", "test", "build"):
            val = block.get(step, "") if isinstance(block, dict) else ""
            cmd_lines.append(f"    {step}: {_yaml_quote(str(val))}")

    lines = template_text.splitlines()

    # Replace project.name and primary_languages.
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == 'name: "CHANGE_ME"':
            out.append('  name: ' + _yaml_quote(project_name))
            i += 1
            continue
        if line.strip() == "primary_languages:":
            out.append("  primary_languages:")
            for lang in langs:
                out.append("    - " + _yaml_quote(lang))
            i += 1
            while i < len(lines) and lines[i].startswith("    - "):
                i += 1
            continue
        out.append(line)
        i += 1

    # Replace commands section (commands: ... up to policies: or EOF).
    final: list[str] = []
    j = 0
    replaced = False
    while j < len(out):
        line = out[j]
        if not replaced and line.strip() == "commands:":
            final.extend(cmd_lines)
            replaced = True
            j += 1
            while j < len(out) and out[j].strip() != "policies:":
                j += 1
            continue
        final.append(line)
        j += 1

    return "\n".join(final).rstrip() + "\n"
