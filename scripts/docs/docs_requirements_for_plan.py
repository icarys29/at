#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Compute deterministic docs requirements for a planning/actions.json (no edits)

This helps the action planner pick doc_ids by providing, per code task:
- required_doc_ids from docs.coverage_rules (based on planned file_scope.writes)
- required_create_types (informational; creation is handled by docs-keeper during sync)

Outputs to SESSION_DIR/documentation/docs_requirements_for_plan.{json,md}

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
    "docs_requirements_for_plan.py is deprecated and will be removed in v0.5.0. "
    "Coverage rules will be in agent instructions. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from docs.coverage_rules import evaluate_coverage_rules_for_write_scopes  # noqa: E402
from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


CODE_OWNERS = {"implementor", "tests-builder"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute deterministic docs requirements for planning/actions.json.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    actions_path = session_dir / "planning" / "actions.json"
    try:
        actions = _read_json(actions_path)
    except FileNotFoundError:
        print(f"ERROR: missing planning/actions.json: {actions_path}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: invalid JSON in planning/actions.json: {exc}", file=sys.stderr)
        return 2

    registry_path = get_docs_registry_path(config)
    registry = load_docs_registry(project_root, registry_path)
    if registry is None:
        print(f"ERROR: missing or invalid docs registry JSON: {registry_path}", file=sys.stderr)
        return 2

    rules = registry.get("coverage_rules")
    if not isinstance(rules, list):
        rules = []

    tasks = actions.get("tasks")
    if not isinstance(tasks, list):
        print("ERROR: planning/actions.json.tasks must be an array", file=sys.stderr)
        return 2

    per_task: list[dict[str, Any]] = []
    for t in tasks[:5000]:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        owner = t.get("owner")
        if not isinstance(tid, str) or not tid.strip():
            continue
        if owner not in CODE_OWNERS:
            continue
        summary_text_for_keywords = ""
        summary = t.get("summary")
        if isinstance(summary, str) and summary.strip():
            summary_text_for_keywords += summary.strip()
        desc = t.get("description")
        if isinstance(desc, str) and desc.strip():
            summary_text_for_keywords += "\n" + desc.strip()
        acs = t.get("acceptance_criteria")
        if isinstance(acs, list):
            for ac in acs[:200]:
                if isinstance(ac, dict) and isinstance(ac.get("statement"), str) and ac.get("statement").strip():
                    summary_text_for_keywords += "\n" + ac.get("statement").strip()
        fs = t.get("file_scope") if isinstance(t.get("file_scope"), dict) else {}
        writes = fs.get("writes") if isinstance(fs.get("writes"), list) else []
        write_scopes = [w for w in writes if isinstance(w, str) and w.strip()]
        plan = evaluate_coverage_rules_for_write_scopes(rules, write_scopes=write_scopes, keywords_text=summary_text_for_keywords)
        per_task.append(
            {
                "task_id": tid.strip(),
                "owner": owner,
                "writes": write_scopes,
                "required_doc_ids": plan.required_doc_ids,
                "required_create_types": plan.required_create_types,
                "triggered_rules": [
                    {"id": tr.rule_id, "matched_paths": tr.matched_paths, "matched_keywords": tr.matched_keywords, "note": tr.note or ""}
                    for tr in plan.triggered
                ],
            }
        )

    out_dir = session_dir / "documentation"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "registry_path": registry_path,
        "tasks": per_task,
    }
    write_json(out_dir / "docs_requirements_for_plan.json", payload)

    md: list[str] = []
    md.append("# Docs Requirements For Plan (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- session_id: `{payload['session_id']}`")
    md.append(f"- registry_path: `{registry_path}`")
    md.append("")
    if not per_task:
        md.append("- (no code tasks found)")
        md.append("")
    else:
        for t in per_task[:200]:
            md.append(f"## {t['task_id']}")
            md.append("")
            md.append(f"- owner: `{t['owner']}`")
            if t.get("required_doc_ids"):
                md.append("- required_doc_ids:")
                for d in t["required_doc_ids"][:50]:
                    md.append(f"  - `{d}`")
            else:
                md.append("- required_doc_ids: (none)")
            if t.get("required_create_types"):
                md.append("- required_create_types:")
                for typ in t["required_create_types"][:20]:
                    md.append(f"  - `{typ}`")
            triggered = t.get("triggered_rules")
            if isinstance(triggered, list) and triggered:
                md.append("- triggered_rules:")
                for r in triggered[:10]:
                    if not isinstance(r, dict):
                        continue
                    rid = r.get("id", "")
                    md.append(f"  - `{rid}`")
                    kws = r.get("matched_keywords") if isinstance(r.get("matched_keywords"), list) else []
                    if kws:
                        md.append("    - matched_keywords: " + ", ".join([f"`{k}`" for k in kws[:10]]))
            md.append("")

    write_text(out_dir / "docs_requirements_for_plan.md", "\n".join(md))
    print(str(out_dir / "docs_requirements_for_plan.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
