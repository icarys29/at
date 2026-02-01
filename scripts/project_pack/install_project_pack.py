#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install a minimal "project pack" (rules + enforcement runner) into the repo overlay.

Installs:
- .claude/rules/project/README.md (if missing; already created by init-project)
- .claude/at/enforcement.json
- .claude/at/scripts/run_enforcements.py

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

from lib.io import utc_now  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _write_if_missing(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def _write_json_if_missing(path: Path, data: dict[str, Any], *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


RUNNER = """#!/usr/bin/env python3
\"\"\"Run project enforcements declared in .claude/at/enforcement.json (deterministic, CI-friendly).

This script is installed into the project so CI can run it without the at plugin.
\"\"\"
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _run(cmd: str, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return (proc.returncode, proc.stdout or "")


def main() -> int:
    root = Path.cwd().resolve()
    cfg_path = root / ".claude" / "at" / "enforcement.json"
    cfg = _load_json(cfg_path)
    if cfg is None:
        print(f"ERROR: missing/invalid {cfg_path}", file=sys.stderr)
        return 2

    checks = cfg.get("checks")
    if not isinstance(checks, list):
        print("ERROR: enforcement.json checks must be a list", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    ok = True
    for item in checks[:200]:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        cmd = item.get("command")
        if not isinstance(cid, str) or not cid.strip() or not isinstance(cmd, str) or not cmd.strip():
            continue
        code, out = _run(cmd.strip(), root)
        passed = code == 0
        if not passed:
            ok = False
        results.append({"id": cid.strip(), "command": cmd.strip(), "exit_code": code, "passed": passed, "output_head": out[:4000]})

    report = {"version": 1, "ok": ok, "results": results}
    out_path = root / ".claude" / "at" / "enforcement_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print(f"OK={ok} report={out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Install minimal at project pack (rules + enforcement runner).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)

    results: list[tuple[str, str]] = []
    enforcement_cfg = {
        "version": 1,
        "generated_at": utc_now(),
        "checks": [
            {"id": "enf-ruff-format", "command": "python3 -m ruff format --check ."},
            {"id": "enf-ruff-lint", "command": "python3 -m ruff check ."},
        ],
    }
    results.append((_write_json_if_missing(project_root / ".claude" / "at" / "enforcement.json", enforcement_cfg, force=args.force), ".claude/at/enforcement.json"))
    results.append((_write_if_missing(project_root / ".claude" / "at" / "scripts" / "run_enforcements.py", RUNNER, force=args.force), ".claude/at/scripts/run_enforcements.py"))

    # Ensure executable bit best-effort.
    try:
        (project_root / ".claude" / "at" / "scripts" / "run_enforcements.py").chmod(0o755)
    except Exception:
        pass

    for status, rel in results:
        print(f"{status}\t{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

