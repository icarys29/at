#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate deterministic compliance report (APPROVE/REJECT)

This is the mechanical compliance decision for a session based on gate artifacts.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "generate_compliance_report.py is deprecated and will be removed in v0.5.0. "
    "Compliance aggregation will be inlined in agent logic. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _run_best_effort(script_path: Path, *, project_root: Path, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, (proc.stdout or "")





def _load_ok(path: Path) -> bool | None:
    data = load_json_safe(path, default=None)
    if not isinstance(data, dict):
        return None
    v = data.get("ok")
    return bool(v) if isinstance(v, bool) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic compliance report for an at session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--rerun-supporting-checks", action="store_true", help="Best-effort rerun task artifacts + changed files checks if missing.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    out_dir = session_dir / "compliance"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Best-effort: ensure supporting deterministic reports exist when requested.
    task_artifacts_report = session_dir / "quality" / "task_artifacts_report.json"
    if args.rerun_supporting_checks and not task_artifacts_report.exists():
        _run_best_effort(SCRIPT_ROOT / "validate" / "validate_task_artifacts.py", project_root=project_root, args=["--session", str(session_dir)])

    changed_files_report = session_dir / "quality" / "changed_files_report.json"
    if args.rerun_supporting_checks and not changed_files_report.exists():
        _run_best_effort(SCRIPT_ROOT / "validate" / "validate_changed_files.py", project_root=project_root, args=["--session", str(session_dir)])

    required: list[tuple[str, Path]] = [
        ("task_artifacts", session_dir / "quality" / "task_artifacts_report.json"),
        ("plan_adherence", session_dir / "quality" / "plan_adherence_report.json"),
        ("parallel_conformance", session_dir / "quality" / "parallel_conformance_report.json"),
        ("quality", session_dir / "quality" / "quality_report.json"),
        ("docs", session_dir / "documentation" / "docs_gate_report.json"),
        ("changed_files", session_dir / "quality" / "changed_files_report.json"),
    ]

    gate_status: dict[str, Any] = {}
    missing: list[str] = []
    failing: list[str] = []
    for gid, path in required:
        ok = _load_ok(path)
        gate_status[gid] = {
            "path": str(path.relative_to(session_dir)).replace("\\", "/"),
            "ok": ok,
        }
        if ok is None:
            missing.append(gid)
        elif ok is False:
            failing.append(gid)

    decision = "APPROVE" if not missing and not failing else "REJECT"
    ok = decision == "APPROVE"

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "decision": decision,
        "missing": missing,
        "failing": failing,
        "gates": gate_status,
    }
    write_json(out_dir / "compliance_report.json", report)

    lines: list[str] = []
    lines.append("# Compliance Verification Report (at)")
    lines.append("")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- session: `{session_dir.name}`")
    lines.append("")
    lines.append(f"DECISION: {decision}")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    for gid, meta in gate_status.items():
        gok = meta.get("ok")
        status = "missing" if gok is None else ("pass" if gok else "fail")
        lines.append(f"- `{gid}`: `{status}` — `{meta.get('path','')}`")
    lines.append("")
    if missing:
        lines.append("## Missing")
        lines.append("")
        for gid in missing:
            lines.append(f"- `{gid}`")
        lines.append("")
    if failing:
        lines.append("## Failing")
        lines.append("")
        for gid in failing:
            lines.append(f"- `{gid}`")
        lines.append("")
    write_text(out_dir / "COMPLIANCE_VERIFICATION_REPORT.md", "\n".join(lines))

    print(str(out_dir / "COMPLIANCE_VERIFICATION_REPORT.md"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
