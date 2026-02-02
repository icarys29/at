#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate deterministic review context for a session

Writes:
- SESSION_DIR/review/REVIEW_CONTEXT.json
- SESSION_DIR/review/REVIEW_CONTEXT.md

This is a deterministic artifact packer intended to help the reviewer agent
produce an evidence-backed report quickly.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "run_review.py is deprecated and will be removed in v0.5.0. "
    "Review orchestration will be merged into /at:run skill. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _load_report(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None





def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic review context artifacts for a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=8000)
    actions = _load_report(session_dir, "planning/actions.json")
    gates_summary = _load_report(session_dir, "status/gates_summary.json")

    tasks_summary: list[dict[str, Any]] = []
    if isinstance(actions, dict):
        tasks = actions.get("tasks")
        if isinstance(tasks, list):
            for t in tasks[:200]:
                if not isinstance(t, dict):
                    continue
                tid = t.get("id")
                owner = t.get("owner")
                summary = t.get("summary")
                if isinstance(tid, str) and isinstance(owner, str) and isinstance(summary, str):
                    tasks_summary.append({"id": tid.strip(), "owner": owner.strip(), "summary": summary.strip()})

    payload: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "request_head": request_text[:1200].strip(),
        "tasks_summary": tasks_summary,
        "gates_summary": gates_summary,
        "artifact_paths": {
            "actions_json": "planning/actions.json" if (session_dir / "planning" / "actions.json").exists() else None,
            "gates_summary_md": "status/gates_summary.md" if (session_dir / "status" / "gates_summary.md").exists() else None,
            "changed_files_report_json": "quality/changed_files_report.json" if (session_dir / "quality" / "changed_files_report.json").exists() else None,
            "quality_report_json": "quality/quality_report.json" if (session_dir / "quality" / "quality_report.json").exists() else None,
            "docs_gate_report_json": "documentation/docs_gate_report.json" if (session_dir / "documentation" / "docs_gate_report.json").exists() else None,
            "compliance_report_json": "compliance/compliance_report.json" if (session_dir / "compliance" / "compliance_report.json").exists() else None,
        },
        "notes": [
            "This context is artifact-first and does not require audit traces.",
            "Use it as an input to the reviewer agent.",
        ],
    }

    out_dir = session_dir / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "REVIEW_CONTEXT.json", payload)

    md: list[str] = []
    md.append("# Review Context (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- session_id: `{payload['session_id']}`")
    md.append("")
    md.append("## Request (head)")
    md.append("")
    md.append("```md")
    md.append(request_text[:1200].rstrip())
    md.append("```")
    md.append("")
    md.append("## Planned tasks (summary)")
    md.append("")
    if tasks_summary:
        for t in tasks_summary[:60]:
            md.append(f"- `{t.get('id','')}` ({t.get('owner','')}): {t.get('summary','')}")
    else:
        md.append("- (missing planning/actions.json)")
    md.append("")
    md.append("## Key artifacts")
    md.append("")
    for k, v in payload["artifact_paths"].items():
        md.append(f"- `{k}`: `{v}`" if v else f"- `{k}`: (missing)")
    md.append("")
    write_text(out_dir / "REVIEW_CONTEXT.md", "\n".join(md))

    print(str(out_dir / "REVIEW_CONTEXT.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
