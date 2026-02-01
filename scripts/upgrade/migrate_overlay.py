#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Overlay migrations framework (plan/apply/rollback)

Scope: ONLY writes under `.claude/**` and `docs/**`.

Subcommands:
- plan:    compute a deterministic migration plan (no writes)
- apply:   apply migrations with backups
- rollback: restore from a backup directory created by apply

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


def _guard_overlay_path(rel: str) -> None:
    if rel.startswith(".claude/") or rel.startswith("docs/"):
        return
    raise RuntimeError(f"Refusing to write outside overlay/docs: {rel}")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _insert_after(lines: list[str], *, anchor_pred: Callable[[str], bool], new_lines: list[str]) -> list[str]:
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and anchor_pred(line):
            out.extend(new_lines)
            inserted = True
    if not inserted:
        out.extend(new_lines)
    return out


def _has_top_level_key(lines: list[str], key: str) -> bool:
    needle = key.rstrip(":") + ":"
    return any(line.strip() == needle and not line.startswith(" ") for line in lines)


def _ensure_project_yaml_fields(text: str) -> tuple[str, list[str]]:
    """
    Best-effort text-based migration of `.claude/project.yaml` to include:
    - workflow.strategy (nested)
    - lsp section (top-level)
    """
    changed: list[str] = []
    lines = text.splitlines()

    # Add workflow.strategy if missing.
    in_workflow = False
    workflow_indent = None
    has_strategy = False
    for line in lines:
        if line.strip() == "workflow:" and not line.startswith(" "):
            in_workflow = True
            workflow_indent = 0
            continue
        if in_workflow:
            if line and not line.startswith(" "):
                in_workflow = False
                workflow_indent = None
                continue
            if line.strip().startswith("strategy:") and line.startswith("  "):
                has_strategy = True
    if not has_strategy:
        def _anchor(l: str) -> bool:
            return l.startswith("  max_remediation_loops:") or l.strip() == "workflow:"

        lines = _insert_after(
            lines,
            anchor_pred=_anchor,
            new_lines=['  # default|tdd — influences action-planner output (task ordering/dependencies).', '  strategy: "default"'],
        )
        changed.append("add workflow.strategy")

    # Add lsp section if missing.
    if not _has_top_level_key(lines, "lsp"):
        def _before_audit(l: str) -> bool:
            return l.strip() == "audit:" and not l.startswith(" ")

        if any(_before_audit(l) for l in lines):
            # Insert right before audit:
            out: list[str] = []
            inserted = False
            for l in lines:
                if not inserted and _before_audit(l):
                    out.extend(["", "lsp:", "  enabled: false", '  mode: "skip"', ""])
                    inserted = True
                out.append(l)
            lines = out
        else:
            lines.extend(["", "lsp:", "  enabled: false", '  mode: "skip"'])
        changed.append("add lsp section")

    return ("\n".join(lines).rstrip() + "\n"), changed


@dataclass(frozen=True)
class PlannedAction:
    path: str
    kind: str  # CREATE|MODIFY|WARN|RUN
    details: str


def _plan(project_root: Path, plugin_root: Path) -> list[PlannedAction]:
    actions: list[PlannedAction] = []

    # docs registry standardization
    if (project_root / "docs" / "REGISTRY.json").exists():
        actions.append(PlannedAction("docs/REGISTRY.json", "WARN", "legacy registry name detected (manual cleanup recommended)"))
    if not (project_root / "docs" / "DOCUMENTATION_REGISTRY.json").exists():
        actions.append(PlannedAction("docs/DOCUMENTATION_REGISTRY.json", "CREATE", "seed docs registry v2 from template"))
    if (project_root / "docs" / "DOCUMENTATION_REGISTRY.json").exists() and not (project_root / "docs" / "DOCUMENTATION_REGISTRY.md").exists():
        actions.append(PlannedAction("docs/DOCUMENTATION_REGISTRY.md", "RUN", "generate derived MD registry view"))

    # project.yaml migrations
    cfg = project_root / ".claude" / "project.yaml"
    if cfg.exists():
        migrated, changes = _ensure_project_yaml_fields(_read(cfg))
        if changes and migrated != _read(cfg):
            actions.append(PlannedAction(".claude/project.yaml", "MODIFY", ", ".join(changes)))
    else:
        actions.append(PlannedAction(".claude/project.yaml", "CREATE", "seed project.yaml from template"))

    return actions


def _apply(project_root: Path, plugin_root: Path, *, backup_root: Path) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []

    def backup(rel: str) -> str | None:
        _guard_overlay_path(rel)
        src = (project_root / rel).resolve()
        if not src.exists():
            return None
        dst = (backup_root / rel).resolve()
        _copy_file(src, dst)
        return str(dst.relative_to(backup_root)).replace("\\", "/")

    def write(rel: str, content: str) -> None:
        _guard_overlay_path(rel)
        dst = (project_root / rel).resolve()
        existed = dst.exists()
        b = backup(rel) if existed else None
        _write(dst, content)
        applied.append({"path": rel, "action": "OVERWRITE" if existed else "CREATE", "backup_rel": b})

    # docs registry json
    docs_reg = project_root / "docs" / "DOCUMENTATION_REGISTRY.json"
    if not docs_reg.exists():
        write("docs/DOCUMENTATION_REGISTRY.json", _read(plugin_root / "templates" / "docs" / "DOCUMENTATION_REGISTRY.json"))

    # derived md registry view
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
            applied.append({"path": "docs/DOCUMENTATION_REGISTRY.md", "action": "CREATE_OR_UPDATE", "note": "generated from registry json"})
    except Exception:
        applied.append({"path": "docs/DOCUMENTATION_REGISTRY.md", "action": "WARN", "note": "registry md generation failed"})

    # project.yaml
    cfg = project_root / ".claude" / "project.yaml"
    if cfg.exists():
        migrated, changes = _ensure_project_yaml_fields(_read(cfg))
        if changes and migrated != _read(cfg):
            write(".claude/project.yaml", migrated)
        else:
            applied.append({"path": ".claude/project.yaml", "action": "SKIP"})
    else:
        tpl = _read(plugin_root / "templates" / "project.yaml").replace("CHANGE_ME", project_root.name)
        write(".claude/project.yaml", tpl)

    # Write manifest for rollback.
    write_json(backup_root / "backup_manifest.json", {"version": 1, "generated_at": utc_now(), "applied": applied})
    return applied


def _rollback(project_root: Path, backup_root: Path) -> list[dict[str, Any]]:
    manifest = backup_root / "backup_manifest.json"
    if not manifest.exists():
        raise RuntimeError(f"Missing backup manifest: {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    applied = data.get("applied") if isinstance(data, dict) else None
    if not isinstance(applied, list):
        raise RuntimeError("Invalid backup manifest: applied[] missing")

    results: list[dict[str, Any]] = []
    for it in applied:
        if not isinstance(it, dict):
            continue
        rel = it.get("path")
        action = it.get("action")
        if not isinstance(rel, str) or not rel:
            continue
        _guard_overlay_path(rel)
        dst = (project_root / rel).resolve()
        backup_rel = it.get("backup_rel")
        if isinstance(backup_rel, str) and backup_rel:
            src = (backup_root / backup_rel).resolve()
            if src.exists():
                _copy_file(src, dst)
                results.append({"path": rel, "action": "RESTORE"})
                continue
        if action == "CREATE" and dst.exists():
            try:
                dst.unlink()
            except Exception:
                pass
            results.append({"path": rel, "action": "DELETE"})
    return results


def _write_plan_report(project_root: Path, *, out_dir: Path, actions: list[PlannedAction]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "generated_at": utc_now(), "actions": [a.__dict__ for a in actions]}
    write_json(out_dir / "overlay_migration_plan.json", payload)
    md: list[str] = []
    md.append("# Overlay Migration Plan (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append("")
    md.append("## Actions")
    md.append("")
    for a in actions:
        md.append(f"- `{a.kind}` `{a.path}` — {a.details}")
    md.append("")
    write_text(out_dir / "overlay_migration_plan.md", "\n".join(md))


def _write_apply_report(project_root: Path, *, out_dir: Path, backup_root: Path, applied: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "generated_at": utc_now(), "backup_root": str(backup_root).replace("\\", "/"), "applied": applied}
    write_json(out_dir / "overlay_migration_apply.json", payload)
    md: list[str] = []
    md.append("# Overlay Migration Apply Report (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- backup_root: `{payload['backup_root']}`")
    md.append("")
    md.append("## Applied")
    md.append("")
    for it in applied[:500]:
        if isinstance(it, dict):
            md.append(f"- `{it.get('action','')}` `{it.get('path','')}`")
    md.append("")
    write_text(out_dir / "overlay_migration_apply.md", "\n".join(md))


def main() -> int:
    parser = argparse.ArgumentParser(description="Overlay migrations framework (plan/apply/rollback).")
    parser.add_argument("--project-dir", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan", help="Compute plan (no writes).")

    sub_apply = sub.add_parser("apply", help="Apply migrations with backups.")
    sub_apply.add_argument("--backup-dir", default=None, help="Override backup dir (default: .claude/at/backups/overlay_migrate/<timestamp>)")

    sub_rb = sub.add_parser("rollback", help="Rollback from a backup directory.")
    sub_rb.add_argument("--backup-dir", required=True, help="Backup dir created by apply.")

    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()
    out_dir = (project_root / ".claude" / "at" / "upgrade").resolve()

    if args.cmd == "plan":
        actions = _plan(project_root, plugin_root)
        _write_plan_report(project_root, out_dir=out_dir, actions=actions)
        print(str(out_dir / "overlay_migration_plan.md"))
        return 0

    if args.cmd == "apply":
        backup_dir = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else (project_root / ".claude" / "at" / "backups" / "overlay_migrate" / utc_now().replace(":", "").replace("-", "")).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        applied = _apply(project_root, plugin_root, backup_root=backup_dir)
        _write_apply_report(project_root, out_dir=out_dir, backup_root=backup_dir, applied=applied)
        print(str(out_dir / "overlay_migration_apply.md"))
        return 0

    if args.cmd == "rollback":
        backup_dir = Path(args.backup_dir).expanduser().resolve()
        applied = _rollback(project_root, backup_dir)
        payload = {"version": 1, "generated_at": utc_now(), "rolled_back": applied, "backup_root": str(backup_dir).replace("\\", "/")}
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "overlay_migration_rollback.json", payload)
        md = ["# Overlay Migration Rollback Report (at)", "", f"- generated_at: `{payload['generated_at']}`", f"- backup_root: `{payload['backup_root']}`", "", "## Restored", ""]
        for it in applied[:500]:
            if isinstance(it, dict):
                md.append(f"- `{it.get('action','')}` `{it.get('path','')}`")
        md.append("")
        write_text(out_dir / "overlay_migration_rollback.md", "\n".join(md))
        print(str(out_dir / "overlay_migration_rollback.md"))
        return 0

    raise RuntimeError(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
