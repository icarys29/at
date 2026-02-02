#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install audit hooks (opt-in, idempotent)

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


def _managed_hook(command: str, timeout: int, matcher: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
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
        item["matcher"] = matcher
    return item


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
    parser = argparse.ArgumentParser(description="Install at audit hooks into project or user settings (idempotent).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--scope", default="project", choices=["project", "team", "user"])
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    if args.scope == "project":
        settings_path = project_root / ".claude" / "settings.local.json"
    elif args.scope == "team":
        settings_path = project_root / ".claude" / "settings.json"
    else:
        settings_path = Path.home() / ".claude" / "settings.json"

    settings = _load_json(settings_path)
    hooks_cfg = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}

    # Keep existing non-managed hooks.
    pre = _filter_managed(hooks_cfg.get("PreToolUse"))
    post = _filter_managed(hooks_cfg.get("PostToolUse"))
    sess_start = _filter_managed(hooks_cfg.get("SessionStart"))
    sess_end = _filter_managed(hooks_cfg.get("SessionEnd"))
    sub_stop = _filter_managed(hooks_cfg.get("SubagentStop"))

    pre.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/audit_pre_tool_use.py\"", timeout=15, matcher="*"))
    post.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/audit_post_tool_use.py\"", timeout=15, matcher="*"))
    sess_start.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/audit_session_lifecycle.py\"", timeout=15))
    sess_end.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/audit_session_lifecycle.py\"", timeout=15))
    sub_stop.append(_managed_hook(f"uv run \"{plugin_root}/scripts/hooks/audit_subagent_stop.py\"", timeout=15, matcher="*"))

    hooks_cfg["PreToolUse"] = pre
    hooks_cfg["PostToolUse"] = post
    hooks_cfg["SessionStart"] = sess_start
    hooks_cfg["SessionEnd"] = sess_end
    hooks_cfg["SubagentStop"] = sub_stop
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
