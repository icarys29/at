#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: User stories gate (coverage + consistency)

When `workflow.require_user_stories=true`, enforce:
- `planning/USER_STORIES.json` exists and is valid-ish
- every user story is referenced by at least one code task via `task.user_story_ids[]`

Writes:
- `SESSION_DIR/quality/user_stories_gate_report.{json,md}`

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "user_stories_gate.py is deprecated and will be removed in v0.5.0. "
    "Coverage validation will be in agent logic. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate user stories coverage against planning/actions.json.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    wf = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    require = wf.get("require_user_stories") is True

    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)
    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    issues: list[dict[str, Any]] = []
    ok = True

    if not require:
        report = {"version": 1, "generated_at": utc_now(), "ok": True, "require_user_stories": False, "issues": []}
        write_json(out_dir / "user_stories_gate_report.json", report)
        write_text(out_dir / "user_stories_gate_report.md", "# User Stories Gate Report (at)\n\n- ok: `true`\n- require_user_stories: `false`\n")
        return 0

    stories_path = session_dir / "planning" / "USER_STORIES.json"
    stories = load_json_safe(stories_path, default={})
    stories = stories if isinstance(stories, dict) else {}
    if stories.get("version") != 1:
        issues.append({"severity": "error", "message": "planning/USER_STORIES.json missing or invalid (expected version=1)"})

    story_ids: list[str] = []
    for it in stories.get("stories", []) if isinstance(stories.get("stories"), list) else []:
        if isinstance(it, dict) and isinstance(it.get("id"), str) and it.get("id").strip():
            story_ids.append(it.get("id").strip())

    if not story_ids:
        issues.append({"severity": "error", "message": "No stories found in planning/USER_STORIES.json"})

    actions = load_json_safe(session_dir / "planning" / "actions.json", default={})
    actions = actions if isinstance(actions, dict) else {}
    tasks = actions.get("tasks") if isinstance(actions.get("tasks"), list) else []

    covered: set[str] = set()
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("owner") not in {"implementor", "tests-builder"}:
            continue
        us = t.get("user_story_ids")
        if not isinstance(us, list):
            continue
        for x in us[:50]:
            if isinstance(x, str) and x.strip():
                covered.add(x.strip())

    missing = [sid for sid in story_ids if sid not in covered]
    if missing:
        issues.append({"severity": "error", "message": f"User stories not covered by any code task.user_story_ids[]: {missing[:20]}{' …' if len(missing) > 20 else ''}"})

    ok = not any(i.get("severity") == "error" for i in issues)
    report = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "require_user_stories": True,
        "stories_total": len(story_ids),
        "stories_covered": len([s for s in story_ids if s in covered]),
        "issues": issues,
    }
    write_json(out_dir / "user_stories_gate_report.json", report)

    md: list[str] = []
    md.append("# User Stories Gate Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- ok: `{str(ok).lower()}`")
    md.append(f"- stories: `{report['stories_covered']}` / `{report['stories_total']}` covered")
    md.append("")
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:50]:
            md.append(f"- `{it.get('severity','')}` — {it.get('message','')}")
        md.append("")
    write_text(out_dir / "user_stories_gate_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
