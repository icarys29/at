#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install docs-keeper hooks into project/user scope (idempotent)

Adds exactly two hooks:
1) SubagentStop warning for docs drift
2) PreToolUse(Bash) gate for commit/PR commands via docs lint

Updates: <project>/.claude/settings.local.json (or user settings)

Version: 0.1.0
Updated: 2026-02-01
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


MANAGED_TAG = "docs-keeper-hooks"


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
    parser = argparse.ArgumentParser(description="Install docs-keeper hooks (idempotent).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--scope", default="project", choices=["project", "user"], help="Install hooks into project or user settings.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()
    settings_path = (
        project_root / ".claude" / "settings.local.json"
        if args.scope == "project"
        else (Path.home() / ".claude" / "settings.json")
    )
    settings = _load_json(settings_path)
    hooks_cfg = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}

    # Preserve existing non-managed hooks.
    pre = _filter_managed(hooks_cfg.get("PreToolUse"))
    sub_stop = _filter_managed(hooks_cfg.get("SubagentStop"))

    # Hook 1: Post-task drift detection (warning only).
    sub_stop.append(
        _managed_hook(
            f"uv run \"{plugin_root}/scripts/hooks/docs_post_task_drift.py\"",
            timeout=10,
        )
    )

    # Hook 2: Pre-commit/PR gate (blocks on docs lint failures).
    pre.append(
        _managed_hook(
            f"uv run \"{plugin_root}/scripts/hooks/docs_pre_commit_gate.py\"",
            timeout=15,
            matcher="Bash",
        )
    )

    hooks_cfg["PreToolUse"] = pre
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

