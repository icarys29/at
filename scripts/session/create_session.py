#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Create new workflow session

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now_full, write_json  # noqa: E402
from lib.project import detect_project_dir, get_plugin_version, get_sessions_dir  # noqa: E402
from lib.active_session import write_active_session  # noqa: E402
from lib.session_env import set_session_env  # noqa: E402


def _new_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{secrets.token_hex(3)}"


def _resolve_resume_arg(project_root: Path, sessions_root: Path, resume: str) -> Path:
    p = Path(resume).expanduser()
    # Accept explicit directory paths (absolute or relative to project root).
    for cand in (p, project_root / p):
        try:
            resolved = cand.resolve()
        except Exception:
            continue
        if resolved.is_dir() and (resolved / "session.json").exists():
            return resolved

    # Otherwise treat it as a session id under sessions_root.
    cand = (sessions_root / resume).resolve()
    if cand.is_dir() and (cand / "session.json").exists():
        return cand

    raise RuntimeError(f"Session not found: {resume!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--workflow", default="deliver", choices=["deliver", "triage", "review", "ideate"])
    parser.add_argument(
        "--strategy",
        default=None,
        choices=["default", "tdd"],
        help="Optional workflow strategy override for this session (default|tdd). Used by planning validation and action-planner.",
    )
    parser.add_argument("--sessions-dir", default=None, help="Override sessions dir (else read from .claude/project.yaml)")
    parser.add_argument("--resume", default=None, help="Resume by session id or session directory")
    # Alias for consistency with skills that use --session. Semantics match --resume.
    parser.add_argument("--session", default=None, help="Alias for --resume (session id or session directory)")
    args = parser.parse_args()

    project_dir = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_dir)
    sessions_root = (project_dir / sessions_dir).resolve()

    resume_arg = None
    if args.resume and args.session:
        raise RuntimeError("Provide only one of --resume or --session")
    if args.resume:
        resume_arg = args.resume
    elif args.session:
        resume_arg = args.session

    if resume_arg:
        session_dir = _resolve_resume_arg(project_dir, sessions_root, str(resume_arg))
    else:
        session_dir = (sessions_root / _new_session_id()).resolve()
        session_dir.mkdir(parents=True, exist_ok=True)

    # Create the canonical session subdirectories (safe to re-run).
    for sub in (
        "inputs",
        "inputs/task_context",
        "planning",
        "analysis",
        "implementation",
        "implementation/tasks",
        "testing",
        "testing/tasks",
        "review",
        "quality",
        "compliance",
        "documentation",
        "telemetry",
        "status",
        "final",
        "logs",
    ):
        (session_dir / sub).mkdir(parents=True, exist_ok=True)

    session_json = session_dir / "session.json"
    if session_json.exists():
        try:
            data = json.loads(session_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if isinstance(data, dict):
            data["updated_at"] = utc_now_full()
            if args.strategy:
                data["workflow_strategy"] = args.strategy
            write_json(session_json, data)
    else:
        payload = {
            "version": 1,
            "session_id": session_dir.name,
            "workflow": args.workflow,
            "status": "in_progress",
            "created_at": utc_now_full(),
            "updated_at": utc_now_full(),
            "project_dir": str(project_dir),
            "sessions_dir": sessions_dir,
            "plugin_version": get_plugin_version(),
        }
        if args.strategy:
            payload["workflow_strategy"] = args.strategy
        write_json(
            session_json,
            payload,
        )

    # Best-effort: link this Claude session to the at SESSION_DIR to help hooks resolve context
    # without transcript heuristics. Uses CLAUDE_SESSION_ID when present.
    try:
        claude_session_id = os.environ.get("CLAUDE_SESSION_ID")
        write_active_session(sessions_root, session_id=session_dir.name, claude_session_id=claude_session_id)
    except Exception:
        pass

    # Set session environment variables for hooks and downstream scripts
    set_session_env(session_dir)

    print(str(session_dir))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
