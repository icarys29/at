#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Uninstall audit hooks (best-effort, idempotent)

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

from lib.project import detect_project_dir  # noqa: E402


MANAGED_TAG = "at-audit-hooks"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prune(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        hooks = it.get("hooks")
        if not isinstance(hooks, list):
            out.append(it)
            continue
        if any(isinstance(h, dict) and (h.get("metadata") or {}).get("managed_by") == MANAGED_TAG for h in hooks):
            continue
        out.append(it)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove at audit hooks from project or user settings (idempotent).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--scope", default="project", choices=["project", "team", "user"])
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    if args.scope == "project":
        settings_path = project_root / ".claude" / "settings.local.json"
    elif args.scope == "team":
        settings_path = project_root / ".claude" / "settings.json"
    else:
        settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        print(f"SKIP\t(no settings file: {settings_path})")
        return 0

    settings = _load_json(settings_path)
    hooks_cfg = settings.get("hooks")
    if not isinstance(hooks_cfg, dict):
        print("SKIP\t(no hooks config)")
        return 0

    for ev in ("PreToolUse", "PostToolUse", "SessionStart", "SessionEnd", "SubagentStop"):
        if ev in hooks_cfg:
            hooks_cfg[ev] = _prune(hooks_cfg.get(ev))
    settings["hooks"] = hooks_cfg
    _write_json(settings_path, settings)
    print(f"OK\t{settings_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
