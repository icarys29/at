#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Rerun one configured quality command for a session (targeted remediation helper)

Reads:
- SESSION_DIR/quality/quality_report.json

Writes:
- SESSION_DIR/quality/command_logs/<id>.rerun.log
- SESSION_DIR/quality/quality_report.json (updates the selected command result)
- SESSION_DIR/quality/quality_report.md (regenerated summary)
- SESSION_DIR/quality/fix_quality_report.{json,md}

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "rerun_quality_command.py is deprecated and will be removed in v0.5.0. "
    "Command rerun will be in quality suite. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".", ":") else "_" for ch in value)[:120]





def _render_quality_md(report: dict[str, Any]) -> str:
    results = report.get("results") if isinstance(report.get("results"), list) else []
    failed = [r for r in results if isinstance(r, dict) and r.get("status") == "failed"]
    md_lines = [
        "# Quality Report (at)",
        "",
        f"- generated_at: `{report.get('generated_at','')}`",
        f"- ok: `{str(bool(report.get('ok') is True)).lower()}`",
        f"- failed: `{len(failed)}` / `{len(results)}`",
        "",
        "## Commands",
        "",
    ]
    for r in results:
        if not isinstance(r, dict):
            continue
        rid = r.get("id", "")
        status = r.get("status", "")
        if status == "skipped":
            md_lines.append(f"- `{rid}`: `skipped` — {r.get('reason','')}")
        elif status == "passed":
            md_lines.append(f"- `{rid}`: `passed` — log: `{r.get('log_path','')}`")
        else:
            md_lines.append(f"- `{rid}`: `failed` (exit={r.get('exit_code','')}) — log: `{r.get('log_path','')}`")
    md_lines.append("")
    return "\n".join(md_lines)


def _git_changed_files(project_root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun one configured quality command for a session (targeted remediation helper).")
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Either a command id from quality_report.json (e.g. 'python:lint') OR a path to quality_report.json",
    )
    parser.add_argument(
        "command_id",
        nargs="?",
        default=None,
        help="Optional command id when target is a quality_report.json path (defaults to first failing command).",
    )
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)

    if not args.target or not str(args.target).strip():
        raise RuntimeError("Provide a command id or a path to quality_report.json.")

    target = str(args.target).strip()

    # Mode A: target is a quality_report.json path.
    report_path: Path
    session_dir: Path
    cmd_id: str | None = None
    cand = Path(target).expanduser()
    report_path_is_file = False
    try:
        abs_cand = cand if cand.is_absolute() else (project_root / cand).resolve()
        report_path_is_file = abs_cand.is_file() and abs_cand.name.endswith(".json")
    except Exception:
        abs_cand = cand

    if report_path_is_file:
        if args.session:
            raise RuntimeError("When providing an explicit quality_report.json path, do not also pass --session.")
        report_path = abs_cand.resolve()
        if report_path.name != "quality_report.json" and report_path.suffix.lower() != ".json":
            raise RuntimeError(f"Expected a JSON report path, got: {report_path}")
        # Expected layout: <SESSION_DIR>/quality/quality_report.json
        session_dir = report_path.parent.parent
        if not (session_dir / "session.json").exists():
            raise RuntimeError(f"Report does not appear to be under a session dir: {report_path}")
        if args.command_id and str(args.command_id).strip():
            cmd_id = str(args.command_id).strip()
    else:
        # Mode B: target is a command id; resolve session normally.
        cmd_id = target
        session_dir = resolve_session_dir(project_root, sessions_dir, args.session)
        report_path = session_dir / "quality" / "quality_report.json"

    report = load_json_safe(report_path, default=None)
    if not isinstance(report, dict):
        raise RuntimeError(f"Missing/invalid quality_report.json: {report_path}")

    results = report.get("results")
    if not isinstance(results, list):
        raise RuntimeError("Invalid quality_report.json: results[] missing")

    if cmd_id is None:
        # Default: pick the first failing command.
        for r in results[:5000]:
            if not isinstance(r, dict):
                continue
            status = r.get("status")
            if status in {"failed", "error", "timeout"}:
                rid = r.get("id")
                if isinstance(rid, str) and rid.strip():
                    cmd_id = rid.strip()
                    break
    if not cmd_id:
        raise RuntimeError("No failing command found in quality_report.json (or no command id provided).")

    target: dict[str, Any] | None = None
    for r in results:
        if isinstance(r, dict) and r.get("id") == cmd_id:
            target = r
            break
    if target is None:
        raise RuntimeError(f"Command id not found in quality_report.json: {cmd_id!r}")

    command = target.get("command")
    if not isinstance(command, str) or not command.strip():
        raise RuntimeError(f"Selected command has no runnable 'command' field: {cmd_id!r}")

    before = _git_changed_files(project_root)

    logs_dir = session_dir / "quality" / "command_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_id(cmd_id)
    log_path = logs_dir / f"{safe}.rerun.log"

    start = time.time()
    proc = subprocess.run(
        command.strip(),
        cwd=str(project_root),
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    dur_ms = int((time.time() - start) * 1000)
    log_path.write_text(
        f"$ {command.strip()}\n\n[exit_code={proc.returncode} duration_ms={dur_ms}]\n\n{proc.stdout}",
        encoding="utf-8",
    )

    after = _git_changed_files(project_root)
    changed_files = None
    if before is not None and after is not None:
        changed_files = sorted(set(after) - set(before))

    new_status = "passed" if proc.returncode == 0 else "failed"
    new_entry = {
        "id": cmd_id,
        "status": new_status,
        "exit_code": proc.returncode,
        "duration_ms": dur_ms,
        "log_path": str(log_path).replace("\\", "/"),
        "command": command.strip(),
        "rerun_of": target.get("log_path"),
    }

    # Replace the entry.
    new_results: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, dict) and r.get("id") == cmd_id:
            new_results.append(new_entry)
        elif isinstance(r, dict):
            new_results.append(r)

    failed = [r for r in new_results if isinstance(r, dict) and r.get("status") == "failed"]
    report["generated_at"] = utc_now()
    report["results"] = new_results
    report["commands_total"] = len(new_results)
    report["commands_failed"] = len(failed)
    report["ok"] = len(failed) == 0
    write_json(report_path, report)
    write_text(session_dir / "quality" / "quality_report.md", _render_quality_md(report))

    fix_report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "command_id": cmd_id,
        "exit_code": proc.returncode,
        "status": new_status,
        "duration_ms": dur_ms,
        "log_path": str(log_path.relative_to(session_dir)).replace("\\", "/"),
        "changed_files": changed_files,
    }
    write_json(session_dir / "quality" / "fix_quality_report.json", fix_report)

    md: list[str] = []
    md.append("# Fix Quality Report (at)")
    md.append("")
    md.append(f"- generated_at: `{fix_report['generated_at']}`")
    md.append(f"- session_id: `{fix_report['session_id']}`")
    md.append(f"- command_id: `{cmd_id}`")
    md.append(f"- status: `{new_status}` (exit={proc.returncode})")
    md.append(f"- log_path: `{fix_report['log_path']}`")
    md.append("")
    if changed_files is not None:
        md.append("## Changed files (git diff)")
        md.append("")
        if changed_files:
            for p in changed_files[:80]:
                md.append(f"- `{p}`")
        else:
            md.append("- (none)")
        md.append("")
    write_text(session_dir / "quality" / "fix_quality_report.md", "\n".join(md))

    print(str(session_dir / "quality" / "fix_quality_report.md"))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
