#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Parallel conformance gate (scope + overlaps + attribution)

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

from lib.git import git_changed_files  # noqa: E402
from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


def _allowed_by_writes(path_posix: str, writes: list[str]) -> bool:
    for w in writes:
        if not isinstance(w, str) or not w.strip():
            continue
        raw = w.strip().replace("\\", "/")
        is_dir = raw.endswith("/")
        norm = normalize_repo_relative_posix_path(raw)
        if not norm:
            continue
        if is_dir and not norm.endswith("/"):
            norm = norm + "/"
        if is_dir:
            if path_posix.startswith(norm):
                return True
        else:
            if path_posix == norm:
                return True
    return False


def _load_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate parallel-safe conformance (scope + overlaps + git attribution).")
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
    parallel = actions.get("parallel_execution") if isinstance(actions.get("parallel_execution"), dict) else {}
    groups = parallel.get("groups") if isinstance(parallel.get("groups"), list) else []

    task_by_id: dict[str, dict[str, Any]] = {}
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if isinstance(tid, str) and tid.strip():
            task_by_id[tid.strip()] = t

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    issues: list[dict[str, Any]] = []
    actual_changes: dict[str, set[str]] = {}

    # Validate each task artifact's changed_files against declared write scopes.
    for tid, t in task_by_id.items():
        owner = t.get("owner")
        if owner not in {"implementor", "tests-builder"}:
            continue
        fs = t.get("file_scope") if isinstance(t.get("file_scope"), dict) else {}
        writes = fs.get("writes") if isinstance(fs.get("writes"), list) else []

        artifact_path = (
            session_dir / "implementation" / "tasks" / f"{tid}.yaml"
            if owner == "implementor"
            else session_dir / "testing" / "tasks" / f"{tid}.yaml"
        )
        art = _load_yaml(artifact_path)
        if art is None:
            issues.append({"severity": "error", "task_id": tid, "message": "missing task artifact"})
            continue
        changed = art.get("changed_files") if isinstance(art.get("changed_files"), list) else []
        paths: set[str] = set()
        for item in changed[:800]:
            if not isinstance(item, dict):
                continue
            p = item.get("path")
            if not isinstance(p, str) or not p.strip():
                continue
            norm = normalize_repo_relative_posix_path(p)
            if not norm:
                issues.append({"severity": "error", "task_id": tid, "message": f"invalid changed_files path: {p!r}"})
                continue
            paths.add(norm)
            if writes and not _allowed_by_writes(norm, [str(x) for x in writes if isinstance(x, str)]):
                issues.append({"severity": "error", "task_id": tid, "path": norm, "message": "changed file is outside task file_scope.writes"})
        actual_changes[tid] = paths

    # Detect overlaps within each parallel group using actual changed paths.
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = g.get("group_id")
        tids = g.get("tasks") if isinstance(g.get("tasks"), list) else []
        ids = [str(x).strip() for x in tids if isinstance(x, str) and str(x).strip()]
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                aset = actual_changes.get(a, set())
                bset = actual_changes.get(b, set())
                overlap = sorted(aset.intersection(bset))
                if overlap:
                    issues.append(
                        {
                            "severity": "error",
                            "group_id": gid,
                            "message": f"overlap between tasks {a!r} and {b!r}",
                            "paths": overlap[:20],
                        }
                    )

    # Best-effort git attribution: all changed files should be attributable to a task artifact.
    changed, warnings = git_changed_files(project_root)
    ignored_prefix = sessions_dir.rstrip("/") + "/"
    changed_effective = {p for p in changed if p != sessions_dir.rstrip("/") and not p.startswith(ignored_prefix)}

    declared_changed = set().union(*actual_changes.values()) if actual_changes else set()
    unattributed = sorted([p for p in changed_effective if p not in declared_changed])
    if changed and unattributed:
        issues.append({"severity": "error", "message": "git shows changed files not listed in any task artifact (unattributed)", "paths": unattributed[:50]})

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": not any(i.get("severity") == "error" for i in issues),
        "git_warnings": warnings,
        "issues": issues,
        "tasks": {k: sorted(list(v)) for k, v in actual_changes.items()},
    }
    write_json(out_dir / "parallel_conformance_report.json", report)

    md = [
        "# Parallel Conformance Report (at)",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- ok: `{str(report['ok']).lower()}`",
        "",
    ]
    if warnings:
        md.append("## Git warnings")
        md.append("")
        for w in warnings[:50]:
            md.append(f"- {w}")
        md.append("")
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            sev = it.get("severity", "")
            msg = it.get("message", "")
            tid = it.get("task_id", "")
            gid = it.get("group_id", "")
            tag = tid or gid or "gate"
            md.append(f"- `{sev}` `{tag}` — {msg}")
        md.append("")
    write_text(out_dir / "parallel_conformance_report.md", "\n".join(md))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

