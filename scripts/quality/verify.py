#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Verify runner (CI-friendly)

Composes:
1) Quality suite (format/lint/typecheck/test/build + optional enforcements)
2) Docs lint (registry + consistency checks; no edits)

Writes one report + exit code suitable for CI:
- SESSION_DIR/quality/verify_report.json
- SESSION_DIR/quality/verify_report.md

If --session is omitted, a new workflow=review session is created to store evidence.

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
    "verify.py is deprecated and will be removed in v0.5.0. "
    "Merged into quality suite. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _create_session(project_root: Path, *, workflow: str) -> Path:
    proc = subprocess.run(
        [sys.executable, str((SCRIPT_ROOT / "session" / "create_session.py").resolve()), "--project-dir", str(project_root), "--workflow", workflow],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"create_session failed: exit={proc.returncode}\n{proc.stdout}")
    s = (proc.stdout or "").strip().splitlines()[-1].strip()
    if not s:
        raise RuntimeError("create_session did not print a session dir")
    p = Path(s).expanduser()
    if not p.is_absolute():
        p = (project_root / p).resolve()
    if not p.exists():
        raise RuntimeError(f"create_session returned non-existent path: {p}")
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify runner: quality suite + docs lint (CI-friendly).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: create new)")
    parser.add_argument("--e2e-profile", default=None, help="E2E profile name from .claude/at/e2e.json (passed through to quality suite).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)

    session_dir: Path
    if args.session:
        session_dir = resolve_session_dir(project_root, sessions_dir, args.session)
    else:
        session_dir = _create_session(project_root, workflow="review")

    # 1) Quality suite (writes SESSION_DIR/quality/*)
    quality_cmd = [sys.executable, str((SCRIPT_ROOT / "quality" / "run_quality_suite.py").resolve()), "--project-dir", str(project_root), "--session", str(session_dir)]
    if isinstance(args.e2e_profile, str) and args.e2e_profile.strip():
        quality_cmd.extend(["--e2e-profile", args.e2e_profile.strip()])
    proc_quality = subprocess.run(quality_cmd, cwd=str(project_root))

    # 2) Docs lint (writes SESSION_DIR/documentation/*)
    doc_json = session_dir / "documentation" / "docs_lint_report.json"
    doc_md = session_dir / "documentation" / "docs_lint_report.md"
    docs_cmd = [
        sys.executable,
        str((SCRIPT_ROOT / "docs" / "docs_lint.py").resolve()),
        "--project-dir",
        str(project_root),
        "--out-json",
        str(doc_json),
        "--out-md",
        str(doc_md),
    ]
    proc_docs = subprocess.run(docs_cmd, cwd=str(project_root))

    quality_report = load_json_safe(session_dir / "quality" / "quality_report.json", default=None)
    docs_report = load_json_safe(doc_json, default=None)

    ok = proc_quality.returncode == 0 and proc_docs.returncode == 0
    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "session_id": session_dir.name,
        "steps": [
            {"id": "quality", "exit_code": proc_quality.returncode, "report_path": "quality/quality_report.json"},
            {"id": "docs_lint", "exit_code": proc_docs.returncode, "report_path": "documentation/docs_lint_report.json"},
        ],
        "reports": {
            "quality": quality_report if isinstance(quality_report, dict) else None,
            "docs_lint": docs_report if isinstance(docs_report, dict) else None,
        },
    }

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "verify_report.json", report)

    md: list[str] = []
    md.append("# Verify Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- ok: `{str(ok).lower()}`")
    md.append(f"- session_id: `{report['session_id']}`")
    md.append("")
    md.append("## Steps")
    md.append("")
    for s in report["steps"]:
        md.append(f"- `{s['id']}`: exit=`{s['exit_code']}` — `{s['report_path']}`")
    md.append("")
    write_text(out_dir / "verify_report.md", "\n".join(md))

    print(str(out_dir / "verify_report.md"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
