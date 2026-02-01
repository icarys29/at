#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Run project enforcements declared in .claude/at/enforcement.json (deterministic, CI-friendly)

This script is installed into the project so CI can run it without the at plugin.
It is intentionally portable and offline.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    id: str
    ok: bool
    exit_code: int
    stdout: str
    stderr: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing enforcement config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def _resolve(project_root: Path, maybe_rel: str) -> Path:
    p = Path(maybe_rel)
    return p if p.is_absolute() else (project_root / p)


def _run_check(project_root: Path, check: dict[str, Any]) -> CheckResult:
    check_id = str(check.get("id") or "unnamed")
    check_type = str(check.get("type") or "command")
    timeout_ms = int(check.get("timeout_ms") or 60000)

    env = os.environ.copy()
    cwd = str(project_root)

    if check_type == "python":
        script = check.get("script")
        args = check.get("args") or []
        if not isinstance(script, str) or not script.strip():
            raise RuntimeError(f"Check {check_id}: python checks require script")
        if not isinstance(args, list):
            raise RuntimeError(f"Check {check_id}: args must be a list")
        argv = [sys.executable, str(_resolve(project_root, script.strip()))] + [str(a) for a in args]
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000.0,
        )
        return CheckResult(
            id=check_id,
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    if check_type == "command":
        command = check.get("command")
        if not isinstance(command, str) or not command.strip():
            raise RuntimeError(f"Check {check_id}: command checks require command")
        completed = subprocess.run(
            command.strip(),
            cwd=cwd,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000.0,
        )
        return CheckResult(
            id=check_id,
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    raise RuntimeError(f"Check {check_id}: unsupported type {check_type!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default=".claude/at/enforcement.json")
    parser.add_argument("--json", dest="json_out", default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    config_path = _resolve(project_root, args.config).resolve()
    cfg = _load_json(config_path)

    mode = str(cfg.get("mode") or "fail").lower()
    checks = cfg.get("checks") or []
    if mode not in {"fail", "warn"}:
        raise RuntimeError("enforcement.json mode must be 'fail' or 'warn'")
    if not isinstance(checks, list):
        raise RuntimeError("enforcement.json checks must be a list")

    results: list[CheckResult] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        results.append(_run_check(project_root, check))

    failed = [r for r in results if not r.ok]
    ok = (len(failed) == 0) if mode == "fail" else True

    report = {
        "version": 1,
        "mode": mode,
        "ok": ok,
        "checks_total": len(results),
        "checks_failed": len(failed),
        "results": [
            {
                "id": r.id,
                "ok": r.ok,
                "exit_code": r.exit_code,
                "stdout_tail": (r.stdout or "")[-4000:],
                "stderr_tail": (r.stderr or "")[-4000:],
            }
            for r in results
        ],
    }

    if args.json_out:
        out_path = _resolve(project_root, args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        out_path = _resolve(project_root, ".claude/at/enforcement_report.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if ok:
        print(f"OK: enforcement checks passed (mode={mode})")
        return 0

    print(f"FAIL: enforcement checks failed (mode={mode})", file=sys.stderr)
    for r in failed[:20]:
        print(f"- {r.id}: exit={r.exit_code}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

