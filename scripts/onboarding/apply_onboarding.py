#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Apply onboarding proposal (overlay + docs only, with backups)

Writes under:
- .claude/**
- docs/**

Backups are stored under:
- .claude/at/backups/onboarding/<timestamp>/

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_plugin_root  # noqa: E402
from onboarding.onboarding_utils import detect_languages, render_project_yaml, suggest_commands  # noqa: E402


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / "templates" / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copy_to_backup(project_root: Path, backup_root: Path, rel_path: str) -> str | None:
    src = (project_root / rel_path).resolve()
    if not src.exists():
        return None
    dst = (backup_root / rel_path).resolve()
    _ensure_parent(dst)
    shutil.copy2(src, dst)
    return str(dst.relative_to(backup_root)).replace("\\", "/")


def _write_file(project_root: Path, backup_root: Path, rel_path: str, content: str, *, force: bool) -> dict[str, Any]:
    dst = (project_root / rel_path).resolve()
    existed = dst.exists()
    if existed and not force:
        return {"path": rel_path, "action": "SKIP"}
    backup_rel = _copy_to_backup(project_root, backup_root, rel_path) if existed else None
    _ensure_parent(dst)
    dst.write_text(content, encoding="utf-8")
    return {"path": rel_path, "action": "OVERWRITE" if existed else "CREATE", "backup_rel": backup_rel}


def _guard_overlay_path(rel_path: str) -> None:
    if rel_path.startswith(".claude/") or rel_path.startswith("docs/"):
        return
    raise RuntimeError(f"Refusing to write outside overlay/docs: {rel_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply onboarding changes (overlay + docs only).")
    parser.add_argument("--project-dir", default=None)
    # Accept to allow skills to forward $ARGUMENTS safely.
    parser.add_argument("--apply", action="store_true", help="No-op (this script always applies).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing overlay/docs files.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    ts = utc_now().replace(":", "").replace("-", "")
    backup_root = (project_root / ".claude" / "at" / "backups" / "onboarding" / ts).resolve()
    backup_root.mkdir(parents=True, exist_ok=True)

    languages = detect_languages(project_root) or ["python"]
    commands_by_lang = suggest_commands(project_root, languages)
    template_project_yaml = _read_template(plugin_root, "project.yaml")
    project_yaml = render_project_yaml(
        template_text=template_project_yaml,
        project_name=project_root.name,
        languages=languages,
        commands_by_lang=commands_by_lang,
    )

    actions: list[dict[str, Any]] = []

    def write(rel_path: str, content: str, *, force: bool) -> None:
        _guard_overlay_path(rel_path)
        actions.append(_write_file(project_root, backup_root, rel_path, content, force=force))

    # Core overlay
    write(".claude/project.yaml", project_yaml, force=args.force)
    write(".claude/rules/at/global.md", _read_template(plugin_root, "rules/global.md"), force=args.force)
    write(
        ".claude/rules/project/README.md",
        "# Project Rules\n\nPut repo-specific rules here.\n",
        force=False,
    )

    # Language packs (safe + deterministic)
    supported_packs = {"python", "go", "typescript", "rust"}
    for lang in [l for l in languages if l in supported_packs]:
        pack_json = _read_template(plugin_root, f"languages/{lang}/pack.json")
        write(f".claude/at/languages/{lang}.json", pack_json, force=args.force)
        # rules_md_template is embedded in pack.json; follow it.
        try:
            import json

            pack = json.loads(pack_json)
        except Exception:
            pack = {}
        rules_tpl = pack.get("rules_md_template") if isinstance(pack, dict) else None
        if isinstance(rules_tpl, str) and rules_tpl.strip():
            rules_md = (plugin_root / rules_tpl.strip()).read_text(encoding="utf-8")
            write(f".claude/rules/at/lang/{lang}.md", rules_md, force=args.force)

    # Docs scaffolding (registry v2 + core placeholders)
    write("docs/DOCUMENTATION_REGISTRY.json", _read_template(plugin_root, "docs/DOCUMENTATION_REGISTRY.json"), force=args.force)
    write("docs/_templates/PROJECT_CONTEXT.md.tpl", _read_template(plugin_root, "docs/_templates/PROJECT_CONTEXT.md.tpl"), force=args.force)
    write("docs/_templates/ARCHITECTURE.md.tpl", _read_template(plugin_root, "docs/_templates/ARCHITECTURE.md.tpl"), force=args.force)
    write("docs/_templates/ADR.md.tpl", _read_template(plugin_root, "docs/_templates/ADR.md.tpl"), force=args.force)
    write("docs/_templates/ARD.md.tpl", _read_template(plugin_root, "docs/_templates/ARD.md.tpl"), force=args.force)
    write("docs/_templates/PATTERN.md.tpl", _read_template(plugin_root, "docs/_templates/PATTERN.md.tpl"), force=args.force)
    write("docs/_templates/RUNBOOK.md.tpl", _read_template(plugin_root, "docs/_templates/RUNBOOK.md.tpl"), force=args.force)
    write("docs/PROJECT_CONTEXT.md", _read_template(plugin_root, "docs/_templates/PROJECT_CONTEXT.md.tpl"), force=args.force)
    write("docs/ARCHITECTURE.md", _read_template(plugin_root, "docs/_templates/ARCHITECTURE.md.tpl"), force=args.force)
    write("docs/adr/README.md", _read_template(plugin_root, "docs/adr/README.md"), force=args.force)
    write("docs/architecture/README.md", _read_template(plugin_root, "docs/architecture/README.md"), force=args.force)
    write("docs/patterns/README.md", _read_template(plugin_root, "docs/patterns/README.md"), force=args.force)
    write("docs/patterns/PAT_PUBLIC_API.md", _read_template(plugin_root, "docs/patterns/PAT_PUBLIC_API.md"), force=args.force)
    write("docs/runbooks/README.md", _read_template(plugin_root, "docs/runbooks/README.md"), force=args.force)

    # Best-effort: generate docs/DOCUMENTATION_REGISTRY.md for humans (non-blocking).
    try:
        subprocess.run(
            [sys.executable, str((plugin_root / "scripts" / "docs" / "generate_registry_md.py").resolve()), "--project-dir", str(project_root)],
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if (project_root / "docs" / "DOCUMENTATION_REGISTRY.md").exists():
            actions.append({"path": "docs/DOCUMENTATION_REGISTRY.md", "action": "CREATE_OR_UPDATE", "note": "generated from registry json"})
    except Exception:
        pass

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "project_root": str(project_root).replace("\\", "/"),
        "ok": True,
        "backup_root": str(backup_root).replace("\\", "/"),
        "actions": actions,
    }
    out_dir = (project_root / ".claude" / "at").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "onboarding_apply_report.json", report)

    md: list[str] = []
    md.append("# Onboarding Apply Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- project_root: `{report['project_root']}`")
    md.append(f"- backup_root: `{report['backup_root']}`")
    md.append("")
    md.append("## Actions")
    md.append("")
    for a in actions[:500]:
        if not isinstance(a, dict):
            continue
        md.append(f"- `{a.get('action')}` `{a.get('path')}`")
    if len(actions) > 500:
        md.append(f"- … ({len(actions) - 500} more)")
    md.append("")
    write_text(out_dir / "onboarding_apply_report.md", "\n".join(md))

    print(str(out_dir / "onboarding_apply_report.md"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
