#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Validate per-task YAML artifacts

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    severity: str  # error|warning


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _validate_changed_files(value: Any, path_prefix: str) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(value, list):
        issues.append(Issue(path_prefix, "changed_files must be a list", "error"))
        return issues
    if not value:
        issues.append(Issue(path_prefix, "changed_files must be non-empty", "error"))
        return issues
    for i, item in enumerate(value[:500]):
        p = f"{path_prefix}[{i}]"
        if not isinstance(item, dict):
            issues.append(Issue(p, "Must be an object with {path, action}", "error"))
            continue
        fp = item.get("path")
        act = item.get("action")
        if not isinstance(fp, str) or not fp.strip():
            issues.append(Issue(f"{p}.path", "Missing/invalid path", "error"))
        if act not in {"created", "modified", "deleted"}:
            issues.append(Issue(f"{p}.action", "Invalid action (created|modified|deleted)", "error"))
    return issues


def validate_task_artifact(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    data = _load_yaml(path)
    if data is None:
        return [Issue(str(path), "Failed to parse YAML (unsupported shape or invalid YAML)", "error")]

    required = ["version", "task_id", "status", "summary", "changed_files"]
    for f in required:
        if f not in data:
            issues.append(Issue(f"{path}:{f}", f"Missing required field: {f}", "error"))

    if data.get("version") != 1:
        issues.append(Issue(f"{path}:version", f"Expected version 1, got {data.get('version')!r}", "error"))

    status = data.get("status")
    if status not in {"completed", "failed", "partial"}:
        issues.append(Issue(f"{path}:status", f"Invalid status: {status!r}", "error"))

    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        issues.append(Issue(f"{path}:task_id", "task_id must be a non-empty string", "error"))

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        issues.append(Issue(f"{path}:summary", "summary must be a non-empty string", "error"))

    if "changed_files" in data:
        issues.extend(_validate_changed_files(data.get("changed_files"), f"{path}:changed_files"))

    # Optional lists
    for key in ("errors", "warnings"):
        if key in data and not isinstance(data.get(key), list):
            issues.append(Issue(f"{path}:{key}", f"{key} must be a list", "warning"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate per-task artifacts under a session directory.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--owner", default="all", choices=["all", "implementor", "tests-builder"])
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    if args.owner in {"all", "implementor"}:
        paths.extend(sorted((session_dir / "implementation" / "tasks").glob("*.yaml")))
    if args.owner in {"all", "tests-builder"}:
        paths.extend(sorted((session_dir / "testing" / "tasks").glob("*.yaml")))

    if not paths:
        report = {
            "version": 1,
            "generated_at": utc_now(),
            "ok": False,
            "owner": args.owner,
            "paths_checked": 0,
            "issues": [{"severity": "error", "path": "task_artifacts", "message": "No task artifacts found"}],
        }
        write_json(out_dir / "task_artifacts_report.json", report)
        write_text(out_dir / "task_artifacts_report.md", "# Task Artifacts Report (at)\n\n- ok: `false`\n- issue: no task artifacts found\n")
        print("No task artifacts found.", file=sys.stderr)
        return 1

    issues: list[Issue] = []
    for p in paths:
        issues.extend(validate_task_artifact(p))

    ok = len([i for i in issues if i.severity == "error"]) == 0
    report = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "owner": args.owner,
        "paths_checked": len(paths),
        "issues": [i.__dict__ for i in issues],
    }
    write_json(out_dir / "task_artifacts_report.json", report)

    md: list[str] = []
    md.append("# Task Artifacts Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- ok: `{str(ok).lower()}`")
    md.append(f"- owner: `{args.owner}`")
    md.append(f"- paths_checked: `{len(paths)}`")
    md.append("")
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            md.append(f"- `{it.severity}` — {it.path}: {it.message}")
        md.append("")
    write_text(out_dir / "task_artifacts_report.md", "\n".join(md))

    if issues:
        print("FAIL: task artifacts validation issues found:", file=sys.stderr)
        for i in issues[:100]:
            print(f"- {i.severity.upper()}: {i.path}: {i.message}", file=sys.stderr)
        if len(issues) > 100:
            print(f"- … ({len(issues) - 100} more)", file=sys.stderr)
        return 1

    print("OK: task artifacts look valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
