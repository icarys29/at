#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate deliver dry-run report (plan-only preview)

This is intended for `/at:run deliver --dry-run ...` after planning + validation.

Writes:
- SESSION_DIR/final/dry_run_report.json
- SESSION_DIR/final/dry_run_report.md

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
    "generate_dry_run_report.py is deprecated and will be removed in v0.5.0. "
    "Agent will generate dry-run reports directly. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402



def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic dry-run report for a planned deliver session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    actions = load_json_safe(session_dir / "planning" / "actions.json", default={})
    actions = actions if isinstance(actions, dict) else {}
    tasks = actions.get("tasks", []) if isinstance(actions.get("tasks"), list) else []

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=6000)
    docs_req = load_json_safe(session_dir / "documentation" / "docs_requirements_for_plan.json", default=None)

    total_tasks = len([t for t in tasks if isinstance(t, dict)])
    code_tasks = [t for t in tasks if isinstance(t, dict) and t.get("owner") in {"implementor", "tests-builder"}]

    writes: list[str] = []
    for t in code_tasks:
        fs = t.get("file_scope") if isinstance(t.get("file_scope"), dict) else {}
        ws = fs.get("writes")
        if isinstance(ws, list):
            for w in ws:
                if isinstance(w, str) and w.strip():
                    writes.append(w.strip())
    writes = sorted(set(writes))

    doc_ids: list[str] = []
    for t in code_tasks:
        ctx = t.get("context") if isinstance(t.get("context"), dict) else {}
        ids = ctx.get("doc_ids")
        if isinstance(ids, list):
            for d in ids:
                if isinstance(d, str) and d.strip():
                    doc_ids.append(d.strip())
    doc_ids = sorted(set(doc_ids))

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "workflow": actions.get("workflow"),
        "request_head": request_text[:1200].strip(),
        "summary": {
            "total_tasks": total_tasks,
            "code_tasks": len(code_tasks),
            "unique_write_scopes": len(writes),
            "unique_doc_ids": len(doc_ids),
        },
        "planned_write_scopes": writes,
        "planned_doc_ids": doc_ids,
        "docs_requirements_for_plan": docs_req if isinstance(docs_req, dict) else None,
        "next_steps": [
            "Review planning/actions.json",
            "If acceptable, re-run /at:run deliver without --dry-run to execute tasks and gates.",
        ],
    }

    out_dir = session_dir / "final"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "dry_run_report.json", report)

    md: list[str] = []
    md.append("# Deliver Dry-Run Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- session_id: `{report['session_id']}`")
    md.append(f"- workflow: `{report.get('workflow')}`")
    md.append("")
    md.append("## Request (head)")
    md.append("")
    md.append("```md")
    md.append(request_text[:1200].rstrip())
    md.append("```")
    md.append("")
    md.append("## Summary")
    md.append("")
    summ = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    md.append(f"- total_tasks: `{summ.get('total_tasks')}`")
    md.append(f"- code_tasks: `{summ.get('code_tasks')}`")
    md.append(f"- unique_write_scopes: `{summ.get('unique_write_scopes')}`")
    md.append(f"- unique_doc_ids: `{summ.get('unique_doc_ids')}`")
    md.append("")
    md.append("## Planned write scopes")
    md.append("")
    for w in writes[:200]:
        md.append(f"- `{w}`")
    if len(writes) > 200:
        md.append(f"- … ({len(writes) - 200} more)")
    md.append("")
    md.append("## Planned docs")
    md.append("")
    for d in doc_ids[:200]:
        md.append(f"- `{d}`")
    if len(doc_ids) > 200:
        md.append(f"- … ({len(doc_ids) - 200} more)")
    md.append("")
    md.append("## Next steps")
    md.append("")
    for s in report["next_steps"]:
        md.append(f"- {s}")
    md.append("")
    write_text(out_dir / "dry_run_report.md", "\n".join(md))

    print(str(out_dir / "dry_run_report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
