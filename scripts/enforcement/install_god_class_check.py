#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install optional god-class detection enforcement into a project overlay

Installs:
- .claude/at/scripts/check_god_classes.py
- Updates .claude/at/enforcement.json to include a `python.god_class` check (opt-in).

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "install_god_class_check.py is deprecated and will be removed in v0.5.0. "
    "Niche feature, moved to optional pack. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_plugin_root  # noqa: E402


CHECK_ID = "python.god_class"



def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / "templates" / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")


def _write_file(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install optional god-class enforcement into .claude/at/.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-methods", type=int, default=25)
    parser.add_argument("--max-lines", type=int, default=400)
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    script_path = project_root / ".claude" / "at" / "scripts" / "check_god_classes.py"
    status = _write_file(
        script_path,
        _read_template(plugin_root, "project_pack/enforcement/check_god_classes.py"),
        force=args.force,
    )
    try:
        script_path.chmod(0o755)
    except Exception:
        pass
    print(f"{status}\t.claude/at/scripts/check_god_classes.py")

    cfg_path = project_root / ".claude" / "at" / "enforcement.json"
    cfg = _load_json(cfg_path)
    mode = cfg.get("mode")
    if mode not in {"fail", "warn"}:
        cfg["mode"] = "fail"
    checks = cfg.get("checks")
    if not isinstance(checks, list):
        checks = []

    if not any(isinstance(c, dict) and c.get("id") == CHECK_ID for c in checks):
        checks.append(
            {
                "id": CHECK_ID,
                "type": "python",
                "script": ".claude/at/scripts/check_god_classes.py",
                "args": ["--project-root", ".", "--max-methods", str(int(args.max_methods)), "--max-lines", str(int(args.max_lines))],
                "timeout_ms": 60000,
            }
        )
        print(f"ADD\t.claude/at/enforcement.json\tcheck_id={CHECK_ID}")
    else:
        print(f"SKIP\t.claude/at/enforcement.json\tcheck_id={CHECK_ID} already present")

    cfg["version"] = int(cfg.get("version") or 1)
    cfg["checks"] = checks
    _write_json(cfg_path, cfg)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
