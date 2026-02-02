#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate git changed files against plan scope (best-effort)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.git import git_changed_files  # noqa: E402
from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path  # noqa: E402
from lib.paths import path_matches_scope  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _allowed_by_any_scope(path_posix: str, scopes: list[str]) -> bool:
    # Use the canonical path_matches_scope from lib/paths.py
    return path_matches_scope(path_posix, scopes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that git-changed files are within the union of plan write scopes.")
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

    scopes: list[str] = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        if t.get("owner") not in {"implementor", "tests-builder"}:
            continue
        fs = t.get("file_scope")
        if not isinstance(fs, dict):
            continue
        writes = fs.get("writes")
        if isinstance(writes, list):
            scopes.extend([str(x) for x in writes if isinstance(x, str) and str(x).strip()])

    changed, warnings = git_changed_files(project_root)
    ignored_prefix = sessions_dir.rstrip("/") + "/"
    changed_effective = {p.replace("\\", "/") for p in changed if p != sessions_dir.rstrip("/") and not p.startswith(ignored_prefix)}

    violations: list[str] = []
    if changed and scopes:
        for p in sorted(changed_effective):
            norm = normalize_repo_relative_posix_path(p)
            if not norm:
                violations.append(p)
                continue
            if not _allowed_by_any_scope(norm, scopes):
                violations.append(norm)

    ok = True
    if "git not available" in warnings:
        ok = True  # fail-open when git is unavailable
    elif changed and violations:
        ok = False

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "git_warnings": warnings,
        "violations": violations,
        "scopes_count": len(scopes),
    }
    write_json(out_dir / "changed_files_report.json", report)

    md = [
        "# Changed Files Scope Report (at)",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- ok: `{str(ok).lower()}`",
        "",
    ]
    if warnings:
        md.append("## Git warnings")
        md.append("")
        for w in warnings[:50]:
            md.append(f"- {w}")
        md.append("")
    if violations:
        md.append("## Violations")
        md.append("")
        for v in violations[:200]:
            md.append(f"- `{v}`")
        md.append("")
    write_text(out_dir / "changed_files_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
