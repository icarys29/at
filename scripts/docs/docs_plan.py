#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Compute deterministic documentation plan for a session (no edits)

This turns session artifacts + docs registry coverage rules into a minimal plan:
- which existing docs must be reviewed/updated
- which doc types must be created (when rules mandate creation)

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

from docs.coverage_rules import evaluate_coverage_rules  # noqa: E402
from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _collect_changed_files(session_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted((session_dir / "implementation" / "tasks").glob("*.yaml")) + sorted((session_dir / "testing" / "tasks").glob("*.yaml")):
        data = _load_yaml(p)
        if not data:
            continue
        changed = data.get("changed_files")
        if not isinstance(changed, list):
            continue
        for it in changed[:500]:
            if not isinstance(it, dict):
                continue
            fp = it.get("path")
            act = it.get("action")
            if isinstance(fp, str) and fp.strip() and act in {"created", "modified", "deleted"}:
                out.append({"path": fp.strip().replace("\\", "/"), "action": act})
    # Dedup while keeping action granularity.
    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for it in out:
        k = (it["path"], it["action"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a deterministic docs plan for a session (no edits).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    registry_path = get_docs_registry_path(config)
    registry = load_docs_registry(project_root, registry_path)
    if registry is None:
        print(f"ERROR: missing or invalid docs registry JSON: {registry_path}", file=sys.stderr)
        return 2

    changed_files = _collect_changed_files(session_dir)
    rules = registry.get("coverage_rules")
    plan = evaluate_coverage_rules(rules, changed_files=changed_files)

    out_dir = session_dir / "documentation"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": 1,
        "generated_at": utc_now(),
        "registry_path": registry_path,
        "session_id": session_dir.name,
        "changed_files_total": len(changed_files),
        "required_doc_ids": plan.required_doc_ids,
        "required_create_types": plan.required_create_types,
        "triggered_rules": [
            {"id": t.rule_id, "matched_paths": t.matched_paths, "note": t.note or ""} for t in plan.triggered
        ],
    }
    write_json(out_dir / "docs_plan.json", payload)

    md: list[str] = []
    md.append("# Docs Plan (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- session_id: `{payload['session_id']}`")
    md.append(f"- registry_path: `{registry_path}`")
    md.append(f"- changed_files_total: `{payload['changed_files_total']}`")
    md.append("")
    md.append("## Required doc ids")
    md.append("")
    if payload["required_doc_ids"]:
        for d in payload["required_doc_ids"]:
            md.append(f"- `{d}`")
    else:
        md.append("- (none)")
    md.append("")
    md.append("## Required doc types to create")
    md.append("")
    if payload["required_create_types"]:
        for t in payload["required_create_types"]:
            md.append(f"- `{t}`")
    else:
        md.append("- (none)")
    md.append("")
    md.append("## Triggered rules")
    md.append("")
    if payload["triggered_rules"]:
        for r in payload["triggered_rules"][:50]:
            md.append(f"- `{r['id']}`")
            if r.get("note"):
                md.append(f"  - note: {r['note']}")
            paths = r.get("matched_paths") if isinstance(r.get("matched_paths"), list) else []
            for p in paths[:10]:
                md.append(f"  - `{p}`")
    else:
        md.append("- (none)")
    md.append("")

    write_text(out_dir / "docs_plan.md", "\n".join(md))
    print(str(out_dir / "docs_plan.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

