#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Run configured quality suite (format/lint/typecheck/test/build)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


@dataclass(frozen=True)
class CommandSpec:
    id: str
    command: str
    requires_env: list[str]
    requires_files: list[str]


def _has_glob_chars(s: str) -> bool:
    return any(ch in s for ch in ["*", "?", "[", "]"])


def _files_exist(project_root: Path, patterns: list[str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for pat in patterns:
        if not isinstance(pat, str) or not pat.strip():
            continue
        p = pat.strip()
        if _has_glob_chars(p):
            matches = list((project_root).glob(p))
            if not matches:
                missing.append(p)
        else:
            if not (project_root / p).exists():
                missing.append(p)
    return (len(missing) == 0, missing)


def _build_suite_from_config(config: dict[str, Any] | None) -> list[CommandSpec]:
    cfg = config if isinstance(config, dict) else {}
    commands = cfg.get("commands") if isinstance(cfg.get("commands"), dict) else {}

    # Preferred: explicit list under commands.quality_suite
    explicit = commands.get("quality_suite")
    if isinstance(explicit, list) and explicit:
        suite: list[CommandSpec] = []
        for i, item in enumerate(explicit[:200]):
            if not isinstance(item, dict):
                continue
            cid = item.get("id")
            cmd = item.get("command")
            if not isinstance(cid, str) or not cid.strip():
                cid = f"cmd-{i+1:02d}"
            if not isinstance(cmd, str) or not cmd.strip():
                continue
            req_env = item.get("requires_env") if isinstance(item.get("requires_env"), list) else []
            req_files = item.get("requires_files") if isinstance(item.get("requires_files"), list) else []
            suite.append(
                CommandSpec(
                    id=str(cid).strip(),
                    command=str(cmd).strip(),
                    requires_env=[str(x).strip() for x in req_env if isinstance(x, str) and x.strip()],
                    requires_files=[str(x).strip() for x in req_files if isinstance(x, str) and x.strip()],
                )
            )
        return suite

    # Legacy: derive from commands.<language>.{format,lint,typecheck,test,build}
    project = cfg.get("project") if isinstance(cfg.get("project"), dict) else {}
    langs = project.get("primary_languages") if isinstance(project.get("primary_languages"), list) else []
    lang_ids = [str(x).strip() for x in langs if isinstance(x, str) and str(x).strip()]
    selected = [l for l in lang_ids if isinstance(commands.get(l), dict)]
    if not selected:
        selected = [k for k, v in commands.items() if isinstance(k, str) and isinstance(v, dict) and k != "allow_unlisted"]

    suite = []
    for lang in selected[:8]:
        block = commands.get(lang)
        if not isinstance(block, dict):
            continue
        for step in ("format", "lint", "typecheck", "test", "build"):
            cmd = block.get(step)
            if isinstance(cmd, str) and cmd.strip():
                suite.append(CommandSpec(id=f"{lang}:{step}", command=cmd.strip(), requires_env=[], requires_files=[]))
    return suite


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_command(project_root: Path, spec: CommandSpec, log_path: Path) -> dict[str, Any]:
    missing_env = [k for k in spec.requires_env if not os.environ.get(k)]
    if missing_env:
        return {"id": spec.id, "status": "skipped", "reason": f"missing env: {', '.join(missing_env)}"}

    ok_files, missing = _files_exist(project_root, spec.requires_files)
    if not ok_files:
        return {"id": spec.id, "status": "skipped", "reason": f"missing files: {', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}"}

    start = time.time()
    proc = subprocess.run(
        spec.command,
        cwd=str(project_root),
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    dur_ms = int((time.time() - start) * 1000)

    _write_log(
        log_path,
        f"$ {spec.command}\n\n"
        f"[exit_code={proc.returncode} duration_ms={dur_ms}]\n\n"
        f"{proc.stdout}",
    )

    return {
        "id": spec.id,
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "duration_ms": dur_ms,
        "log_path": str(log_path).replace("\\", "/"),
        "command": spec.command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic quality commands configured in .claude/project.yaml.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    suite = _build_suite_from_config(config)
    out_dir = session_dir / "quality"
    logs_dir = out_dir / "command_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for spec in suite:
        safe_id = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", ":") else "_" for ch in spec.id)[:120]
        log_path = logs_dir / f"{safe_id}.log"
        results.append(_run_command(project_root, spec, log_path))

    # Optional: run repo-local enforcements if installed (CI-friendly).
    enforcement_report: dict[str, Any] | None = None
    runner = project_root / ".claude" / "at" / "scripts" / "run_enforcements.py"
    if runner.exists():
        start = time.time()
        # Prefer writing enforcement evidence under the session for deterministic auditing.
        enforcement_out = out_dir / "enforcement_report.json"

        proc = subprocess.run(
            [sys.executable, str(runner), "--project-root", str(project_root), "--config", str(project_root / ".claude" / "at" / "enforcement.json"), "--json", str(enforcement_out)],
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.returncode != 0:
            # Back-compat: older runners may not support args; retry with no args.
            proc2 = subprocess.run(
                f"python3 \"{runner}\"",
                cwd=str(project_root),
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if proc2.returncode == 0 or proc2.stdout:
                proc = proc2

        dur_ms = int((time.time() - start) * 1000)
        _write_log(logs_dir / "enforcements.log", f"$ {sys.executable} \"{runner}\" …\n\n[exit_code={proc.returncode} duration_ms={dur_ms}]\n\n{proc.stdout}")
        # Best-effort read of generated report (prefer session-scoped file; fallback to repo-local).
        try:
            src = enforcement_out if enforcement_out.exists() else (project_root / ".claude" / "at" / "enforcement_report.json")
            enforcement_report = json.loads(src.read_text(encoding="utf-8"))
        except Exception:
            enforcement_report = {"version": 1, "ok": proc.returncode == 0, "note": "missing/invalid enforcement_report.json"}
        results.append(
            {
                "id": "enforcement",
                "status": "passed" if proc.returncode == 0 else "failed",
                "exit_code": proc.returncode,
                "duration_ms": dur_ms,
                "log_path": str((logs_dir / "enforcements.log")).replace("\\", "/"),
                "command": f"{sys.executable} \"{runner}\"",
            }
        )

    failed = [r for r in results if r.get("status") == "failed"]
    ok = len(failed) == 0

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "commands_total": len(results),
        "commands_failed": len(failed),
        "results": results,
    }
    write_json(out_dir / "quality_report.json", report)
    if enforcement_report is not None:
        write_json(out_dir / "enforcement_report.json", enforcement_report)

    md_lines = [
        "# Quality Report (at)",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- ok: `{str(ok).lower()}`",
        f"- failed: `{len(failed)}` / `{len(results)}`",
        "",
        "## Commands",
        "",
    ]
    for r in results:
        rid = r.get("id", "")
        status = r.get("status", "")
        if status == "skipped":
            md_lines.append(f"- `{rid}`: `skipped` — {r.get('reason','')}")
        elif status == "passed":
            md_lines.append(f"- `{rid}`: `passed` — log: `{r.get('log_path','')}`")
        else:
            md_lines.append(f"- `{rid}`: `failed` (exit={r.get('exit_code','')}) — log: `{r.get('log_path','')}`")
    md_lines.append("")
    write_text(out_dir / "quality_report.md", "\n".join(md_lines))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
