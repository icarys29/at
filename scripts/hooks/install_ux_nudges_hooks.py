#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install UX nudge hooks (opt-in, idempotent)

Adds non-blocking UX nudges:
- PostToolUse(Write/Edit): debug statement detection warning
- Stop: compaction suggestion when transcript is large

Installs into:
- project: <project>/.claude/settings.local.json
- team:    <project>/.claude/settings.json
- user:    ~/.claude/settings.json

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


MANAGED_TAG = "at-ux-nudges-hooks"


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


def _managed_hook(command: str, timeout: int, matcher: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
                "metadata": {"managed_by": MANAGED_TAG},
            }
        ]
    }
    if matcher is not None:
        out["matcher"] = matcher
    return out


def _filter_managed(items: Any) -> list[dict[str, Any]]:
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
    parser = argparse.ArgumentParser(description="Install at UX nudge hooks into project or user settings (idempotent).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--scope", default="project", choices=["project", "team", "user"])
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()
    settings_path = (
        (project_root / ".claude" / "settings.local.json")
        if args.scope == "project"
        else ((project_root / ".claude" / "settings.json") if args.scope == "team" else (Path.home() / ".claude" / "settings.json"))
    )

    settings = _load_json(settings_path)
    hooks_cfg = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}

    post = _filter_managed(hooks_cfg.get("PostToolUse"))
    stop = _filter_managed(hooks_cfg.get("Stop"))

    dbg_cmd = f"uv run \"{plugin_root}/scripts/hooks/nudge_debug_detection.py\""
    post.append(_managed_hook(dbg_cmd, timeout=12, matcher="Write"))
    post.append(_managed_hook(dbg_cmd, timeout=12, matcher="Edit"))

    stop.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/nudge_compaction.py\"", timeout=10))

    hooks_cfg["PostToolUse"] = post
    hooks_cfg["Stop"] = stop
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
