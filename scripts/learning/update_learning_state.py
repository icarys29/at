#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Update learning state from a session (writes only under .claude/agent-team/learning)

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

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from learning.learning_state import ensure_learning_dirs, learning_root  # noqa: E402


def _read_optional(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        s = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return s[:max_chars]


def _session_digest(session_dir: Path) -> dict[str, Any]:
    request = _read_optional(session_dir / "inputs" / "request.md", 5000)
    progress = load_json_safe(session_dir / "status" / "session_progress.json", default=None)
    compliance = _read_optional(session_dir / "compliance" / "COMPLIANCE_VERIFICATION_REPORT.md", 8000)
    quality = load_json_safe(session_dir / "quality" / "quality_report.json", default=None)

    digest: dict[str, Any] = {
        "version": 1,
        "session_id": session_dir.name,
        "updated_at": utc_now(),
        "request_head": request.strip(),
        "overall_status": (progress.get("overall_status") if isinstance(progress, dict) else None),
        "compliance_head": compliance.strip(),
        "quality_ok": (quality.get("ok") if isinstance(quality, dict) else None),
    }
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Update learning state from a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--emit-adr", action="store_true", help="Emit an ADR stub when the session decision is REJECT (best-effort).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    ensure_learning_dirs(project_root)
    root = learning_root(project_root)

    digest = _session_digest(session_dir)
    sess_path = root / "sessions" / f"{session_dir.name}.json"
    write_json(sess_path, digest)

    # Update STATUS.md (small, stable)
    all_digests = sorted((root / "sessions").glob("*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    latest = all_digests[:10]

    md = ["# Learning Status (at)", "", f"- updated_at: `{utc_now()}`", f"- sessions_tracked: `{len(all_digests)}`", "", "## Recent", ""]
    for p in latest:
        data = load_json_safe(p, default={})
        sid = data.get("session_id", p.stem)
        status = data.get("overall_status")
        qok = data.get("quality_ok")
        md.append(f"- `{sid}` — overall=`{status}` quality_ok=`{qok}`")
    md.append("")
    write_text(root / "STATUS.md", "\n".join(md))

    # Optional ADR stub (very lightweight, never blocks)
    if args.emit_adr:
        compliance_md = (session_dir / "compliance" / "COMPLIANCE_VERIFICATION_REPORT.md")
        compliance_text = _read_optional(compliance_md, 12000)
        if "REJECT" in compliance_text.upper():
            adr = (
                "# ADR (stub)\n\n"
                f"- created_at: `{utc_now()}`\n"
                f"- session: `{session_dir.name}`\n"
                "- decision: (fill in)\n\n"
                "## Context\n\n"
                "(fill in)\n\n"
                "## Decision\n\n"
                "(fill in)\n\n"
                "## Consequences\n\n"
                "(fill in)\n"
            )
            (root / "adr" / f"ADR_{session_dir.name}.md").write_text(adr, encoding="utf-8")

    print(f"OK\t{sess_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

