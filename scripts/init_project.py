#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Initialize project with at overlay

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_text  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


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


def _read_yaml(path: Path) -> dict:
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _install_language_pack(project_root: Path, *, lang: str, force: bool) -> list[tuple[str, str]]:
    plugin_root = _plugin_root()
    pack_path = plugin_root / "templates" / "languages" / lang / "pack.json"
    if not pack_path.exists():
        return []
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    if not isinstance(pack, dict) or pack.get("version") != 1 or pack.get("language") != lang:
        return []
    rules_md_template = pack.get("rules_md_template")
    if not isinstance(rules_md_template, str) or not rules_md_template.strip():
        return []
    rules_src = plugin_root / rules_md_template.strip()
    if not rules_src.exists():
        return []

    results: list[tuple[str, str]] = []
    results.append(
        (
            _write_if_missing(project_root / ".claude" / "rules" / "at" / "lang" / f"{lang}.md", rules_src.read_text(encoding="utf-8"), force=force),
            f".claude/rules/at/lang/{lang}.md",
        )
    )
    results.append(
        (
            _write_if_missing(project_root / ".claude" / "at" / "languages" / f"{lang}.json", json.dumps(pack, indent=2, sort_keys=True) + "\n", force=force),
            f".claude/at/languages/{lang}.json",
        )
    )
    return results


def _install_project_pack(project_root: Path, *, force: bool) -> list[tuple[str, str]]:
    """
    Install the repo-local project pack (enforcement runner + default checks).

    Best-effort: failures should not block initial overlay bootstrap.
    """
    try:
        import subprocess

        cmd = [sys.executable, str(_plugin_root() / "scripts" / "project_pack" / "install_project_pack.py"), "--project-dir", str(project_root)]
        if force:
            cmd.append("--force")
        proc = subprocess.run(
            cmd,
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        out: list[tuple[str, str]] = []
        for line in (proc.stdout or "").splitlines():
            if "\t" not in line:
                continue
            status, rel = line.split("\t", 1)
            status = status.strip()
            rel = rel.strip()
            if status and rel:
                out.append((status, rel))
        if proc.returncode != 0 and not out:
            out.append(("ERROR", ".claude/at/enforcement.json"))
        return out
    except Exception:
        return [("ERROR", ".claude/at/enforcement.json")]


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

    # Language packs + language rules (based on project.primary_languages when present).
    cfg = _read_yaml(project_root / ".claude" / "project.yaml")
    langs: list[str] = []
    proj = cfg.get("project") if isinstance(cfg.get("project"), dict) else {}
    primary = proj.get("primary_languages") if isinstance(proj.get("primary_languages"), list) else []
    for it in primary[:12]:
        if isinstance(it, str) and it.strip():
            langs.append(it.strip())
    # If missing/empty, install python pack by default (safe bootstrap).
    if not langs:
        langs = ["python"]
    for lang in langs:
        results.extend(_install_language_pack(project_root, lang=lang, force=False))

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
    results.append(
        (
            _write_if_missing(
                project_root / ".claude" / "rules" / "project" / "architecture.md",
                _read_template("rules/project/architecture.md"),
                force=False,
            ),
            ".claude/rules/project/architecture.md",
        )
    )

    # Docs scaffolding
    results.append(
        (
            _write_if_missing(project_root / "docs" / "DOCUMENTATION_REGISTRY.json", _read_template("docs/DOCUMENTATION_REGISTRY.json"), force=args.force),
            "docs/DOCUMENTATION_REGISTRY.json",
        )
    )

    # Docs templates (project-local; used by docs-keeper).
    for rel in (
        "docs/_templates/PROJECT_CONTEXT.md.tpl",
        "docs/_templates/ARCHITECTURE.md.tpl",
        "docs/_templates/ADR.md.tpl",
        "docs/_templates/ARD.md.tpl",
        "docs/_templates/PATTERN.md.tpl",
        "docs/_templates/RUNBOOK.md.tpl",
    ):
        results.append((_write_if_missing(project_root / rel, _read_template(rel), force=args.force), rel))

    # Core docs (initial copies from templates; safe placeholders).
    results.append(
        (
            _write_if_missing(project_root / "docs" / "PROJECT_CONTEXT.md", _read_template("docs/_templates/PROJECT_CONTEXT.md.tpl"), force=args.force),
            "docs/PROJECT_CONTEXT.md",
        )
    )
    results.append(
        (
            _write_if_missing(project_root / "docs" / "ARCHITECTURE.md", _read_template("docs/_templates/ARCHITECTURE.md.tpl"), force=args.force),
            "docs/ARCHITECTURE.md",
        )
    )

    # Taxonomy dirs + indexes
    results.append((_write_if_missing(project_root / "docs" / "adr" / "README.md", _read_template("docs/adr/README.md"), force=args.force), "docs/adr/README.md"))
    results.append((_write_if_missing(project_root / "docs" / "architecture" / "README.md", _read_template("docs/architecture/README.md"), force=args.force), "docs/architecture/README.md"))
    results.append((_write_if_missing(project_root / "docs" / "patterns" / "README.md", _read_template("docs/patterns/README.md"), force=args.force), "docs/patterns/README.md"))
    results.append((_write_if_missing(project_root / "docs" / "patterns" / "PAT_PUBLIC_API.md", _read_template("docs/patterns/PAT_PUBLIC_API.md"), force=args.force), "docs/patterns/PAT_PUBLIC_API.md"))
    results.append((_write_if_missing(project_root / "docs" / "runbooks" / "README.md", _read_template("docs/runbooks/README.md"), force=args.force), "docs/runbooks/README.md"))

    # Project-local docs keeper components (optional; meets corporate docs system structure)
    results.append((_write_if_missing(project_root / ".claude" / "agents" / "docs-keeper.md", _read_template("claude/agents/docs-keeper.md"), force=args.force), ".claude/agents/docs-keeper.md"))
    results.append((_write_if_missing(project_root / ".claude" / "skills" / "docs-keeper" / "SKILL.md", _read_template("claude/skills/docs-keeper/SKILL.md"), force=args.force), ".claude/skills/docs-keeper/SKILL.md"))
    # Wrapper skills for the requested /docs:* commands (thin delegators; no duplicated logic).
    for rel in (
        "skills/docs:sync/SKILL.md",
        "skills/docs:plan/SKILL.md",
        "skills/docs:lint/SKILL.md",
        "skills/docs:new/SKILL.md",
    ):
        tpl = "claude/" + rel
        dst = ".claude/" + rel
        results.append((_write_if_missing(project_root / dst, _read_template(tpl), force=args.force), dst))
    results.append((_write_if_missing(project_root / ".claude" / "hooks" / "README.md", _read_template("claude/hooks/README.md"), force=args.force), ".claude/hooks/README.md"))

    # Generate docs/DOCUMENTATION_REGISTRY.md (derived view for humans).
    # Best-effort and non-blocking; the docs gate can enforce drift later.
    try:
        import subprocess

        subprocess.run(
            [sys.executable, str(_plugin_root() / "scripts" / "docs" / "generate_registry_md.py")],
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        results.append(("CREATE", "docs/DOCUMENTATION_REGISTRY.md"))
    except Exception:
        pass

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

    # Learning scaffolding (P3; safe to create, never overwrites).
    learning_root = project_root / ".claude" / "agent-team" / "learning"
    learning_root.mkdir(parents=True, exist_ok=True)
    (learning_root / "sessions").mkdir(parents=True, exist_ok=True)
    (learning_root / "adr").mkdir(parents=True, exist_ok=True)
    learning_status = learning_root / "STATUS.md"
    if not learning_status.exists():
        learning_status.write_text("# Learning Status (at)\n\n- Initialized: " + utc_now() + "\n", encoding="utf-8")
        results.append(("CREATE", ".claude/agent-team/learning/STATUS.md"))
    else:
        results.append(("SKIP", ".claude/agent-team/learning/STATUS.md"))

    # Project pack (repo-local enforcements). Default-on and safe to re-run.
    results.extend(_install_project_pack(project_root, force=args.force))

    for status, rel in results:
        print(f"{status}\t{rel}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
