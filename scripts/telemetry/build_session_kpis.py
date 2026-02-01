#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Build per-session KPIs (deterministic, best-effort)

Writes:
- SESSION_DIR/telemetry/session_kpis.json
- SESSION_DIR/telemetry/session_kpis.md

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


def _bool(v: Any) -> bool | None:
    return bool(v) if isinstance(v, bool) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic per-session KPIs (best-effort).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    progress = load_json_safe(session_dir / "status" / "session_progress.json", default=None)
    actions = load_json_safe(session_dir / "planning" / "actions.json", default=None)
    quality = load_json_safe(session_dir / "quality" / "quality_report.json", default=None)
    plan_gate = load_json_safe(session_dir / "quality" / "plan_adherence_report.json", default=None)
    par_gate = load_json_safe(session_dir / "quality" / "parallel_conformance_report.json", default=None)
    docs_gate = load_json_safe(session_dir / "documentation" / "docs_gate_report.json", default=None)

    def _count_tasks(owner: str) -> int:
        if not isinstance(actions, dict):
            return 0
        tasks = actions.get("tasks")
        if not isinstance(tasks, list):
            return 0
        n = 0
        for t in tasks:
            if isinstance(t, dict) and t.get("owner") == owner:
                n += 1
        return n

    kpis: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "workflow": (actions.get("workflow") if isinstance(actions, dict) else None),
        "overall_status": (progress.get("overall_status") if isinstance(progress, dict) else None),
        "counts": {
            "tasks": {
                "implementor": _count_tasks("implementor"),
                "tests_builder": _count_tasks("tests-builder"),
            }
        },
        "gates": {
            "plan_adherence_ok": _bool(plan_gate.get("ok") if isinstance(plan_gate, dict) else None),
            "parallel_conformance_ok": _bool(par_gate.get("ok") if isinstance(par_gate, dict) else None),
            "quality_ok": _bool(quality.get("ok") if isinstance(quality, dict) else None),
            "docs_ok": _bool(docs_gate.get("ok") if isinstance(docs_gate, dict) else None),
        },
    }

    out_dir = session_dir / "telemetry"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "session_kpis.json", kpis)

    md = [
        "# Session KPIs (at)",
        "",
        f"- generated_at: `{kpis['generated_at']}`",
        f"- session_id: `{kpis['session_id']}`",
        f"- workflow: `{kpis.get('workflow','')}`",
        f"- overall_status: `{kpis.get('overall_status','')}`",
        "",
        "## Gates",
        "",
    ]
    for k, v in (kpis.get("gates") or {}).items():
        md.append(f"- `{k}`: `{v}`")
    md.append("")
    write_text(out_dir / "session_kpis.md", "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

