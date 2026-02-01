#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs lint (registry + consistency checks; no edits)

Use for pre-commit/PR gating and for docs-keeper verification.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.docs_validation import find_broken_links, find_orphan_docs, run_registry_md_check, validate_registry_v2  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, load_project_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Docs lint: validate registry + consistency checks (no edits).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--registry-path", default=None)
    parser.add_argument("--out-json", default=None, help="Optional output JSON path (repo-relative or absolute)")
    parser.add_argument("--out-md", default=None, help="Optional output MD path (repo-relative or absolute)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    cfg = load_project_config(project_root) or {}
    registry_path = args.registry_path or get_docs_registry_path(cfg)
    registry = load_docs_registry(project_root, registry_path)

    issues, summary, type_map = validate_registry_v2(project_root, registry_path=registry_path, registry=registry)

    # Drift check for generated markdown view.
    md_check = run_registry_md_check(project_root, registry_path=registry_path)
    if md_check.get("status") == "failed":
        issues.append({"severity": "error", "message": "docs/DOCUMENTATION_REGISTRY.md is out of sync (run scripts/docs/generate_registry_md.py)"})
    elif md_check.get("status") == "skipped":
        issues.append({"severity": "warning", "message": f"registry markdown check skipped: {md_check.get('reason','')}"})

    if registry and type_map:
        orphans = find_orphan_docs(project_root, registry, type_map)
        if orphans:
            issues.append({"severity": "error", "message": f"orphan docs detected under managed dirs: {len(orphans)}"})

        doc_paths: list[str] = []
        docs = registry.get("docs") if isinstance(registry.get("docs"), list) else []
        for it in docs:
            if isinstance(it, dict) and isinstance(it.get("path"), str) and it.get("path").strip():
                doc_paths.append(it.get("path").strip())
        broken = find_broken_links(project_root, doc_paths=doc_paths)
        if broken:
            issues.append({"severity": "error", "message": f"broken markdown links detected: {len(broken)}"})

    ok = not any(i.get("severity") == "error" for i in issues)

    payload: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "registry_path": registry_path,
        "summary": summary,
        "issues": issues,
    }

    def _resolve_out(p: str) -> Path:
        cand = Path(p)
        if cand.is_absolute():
            return cand
        return (project_root / cand).resolve()

    if isinstance(args.out_json, str) and args.out_json.strip():
        outp = _resolve_out(args.out_json.strip())
        write_json(outp, payload)

    if isinstance(args.out_md, str) and args.out_md.strip():
        outp = _resolve_out(args.out_md.strip())
        md: list[str] = []
        md.append("# Docs Lint Report (at)")
        md.append("")
        md.append(f"- generated_at: `{payload['generated_at']}`")
        md.append(f"- ok: `{str(ok).lower()}`")
        md.append(f"- registry_path: `{registry_path}`")
        md.append("")
        if issues:
            md.append("## Issues")
            md.append("")
            for it in issues[:200]:
                md.append(f"- `{it.get('severity','')}` — {it.get('message','')}")
            md.append("")
        write_text(outp, "\n".join(md))

    if ok:
        print("OK: docs lint passed.")
        return 0

    print("FAIL: docs lint issues found:", file=sys.stderr)
    for it in issues[:60]:
        print(f"- {it.get('severity','')}: {it.get('message','')}", file=sys.stderr)
    if len(issues) > 60:
        print(f"- … ({len(issues) - 60} more)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

