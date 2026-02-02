#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs status (registry health summary; no edits)

Writes (optional):
- <out-json>
- <out-md>

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
    "docs_status.py is deprecated and will be removed in v0.5.0. "
    "Agent can read and report directly. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.docs_validation import run_registry_md_check, validate_registry_v2  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, load_project_config  # noqa: E402



def _resolve_out(project_root: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (project_root / p).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Docs status: registry health overview (no edits).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--out-json", default=None, help="Optional output JSON path (repo-relative or absolute)")
    parser.add_argument("--out-md", default=None, help="Optional output MD path (repo-relative or absolute)")
    parser.add_argument("--format", default="summary", choices=["summary", "full", "json"], help="Console output format")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    cfg = load_project_config(project_root) or {}
    registry_path = get_docs_registry_path(cfg)
    registry = load_docs_registry(project_root, registry_path)

    issues, summary, _type_map = validate_registry_v2(project_root, registry_path=registry_path, registry=registry)
    md_check = run_registry_md_check(project_root, registry_path=registry_path)
    if md_check.get("status") == "failed":
        issues.append({"severity": "error", "message": "docs/DOCUMENTATION_REGISTRY.md is out of sync (run scripts/docs/generate_registry_md.py)"})
    elif md_check.get("status") == "skipped":
        issues.append({"severity": "warning", "message": f"registry markdown check skipped: {md_check.get('reason','')}"})

    ok = not any(isinstance(i, dict) and i.get("severity") == "error" for i in issues)

    payload: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "registry_path": registry_path,
        "summary": summary,
        "registry_md_check": md_check,
        "issues": issues,
    }

    if isinstance(args.out_json, str) and args.out_json.strip():
        write_json(_resolve_out(project_root, args.out_json.strip()), payload)

    if isinstance(args.out_md, str) and args.out_md.strip():
        md: list[str] = []
        md.append("# Docs Status (at)")
        md.append("")
        md.append(f"- generated_at: `{payload['generated_at']}`")
        md.append(f"- ok: `{str(ok).lower()}`")
        md.append(f"- registry_path: `{registry_path}`")
        md.append("")
        md.append("## Summary")
        md.append("")
        md.append(f"- docs_total: `{summary.get('docs_total', 0)}`")
        md.append(f"- docs_missing_files: `{summary.get('docs_missing_files', 0)}`")
        md.append(f"- docs_missing_when: `{summary.get('docs_missing_when', 0)}`")
        md.append(f"- docs_missing_required_fields: `{summary.get('docs_missing_required_fields', 0)}`")
        tiers = summary.get("tiers") if isinstance(summary.get("tiers"), dict) else {}
        types = summary.get("types") if isinstance(summary.get("types"), dict) else {}
        if tiers:
            md.append("- tiers:")
            for k in sorted(tiers):
                md.append(f"  - `{k}`: `{tiers.get(k)}`")
        if types:
            md.append("- types:")
            for k in sorted(types):
                md.append(f"  - `{k}`: `{types.get(k)}`")
        md.append("")
        if issues:
            md.append("## Issues")
            md.append("")
            for it in issues[:200]:
                if not isinstance(it, dict):
                    continue
                md.append(f"- `{it.get('severity','')}` — {it.get('message','')}")
            md.append("")
        write_text(_resolve_out(project_root, args.out_md.strip()), "\n".join(md))

    if args.format == "json":
        import json as _json

        print(_json.dumps(payload, indent=2, sort_keys=True))
        return 0 if ok else 1

    # Console output: summary by default.
    print("Docs Status (at)")
    print("================")
    print(f"ok: {str(ok).lower()}")
    print(f"registry_path: {registry_path}")
    print(f"docs_total: {summary.get('docs_total', 0)}")
    print(f"docs_missing_files: {summary.get('docs_missing_files', 0)}")
    print(f"docs_missing_when: {summary.get('docs_missing_when', 0)}")
    print(f"docs_missing_required_fields: {summary.get('docs_missing_required_fields', 0)}")

    if args.format == "full":
        tiers = summary.get("tiers") if isinstance(summary.get("tiers"), dict) else {}
        types = summary.get("types") if isinstance(summary.get("types"), dict) else {}
        if tiers:
            print("tiers:")
            for k in sorted(tiers):
                print(f"  {k}: {tiers.get(k)}")
        if types:
            print("types:")
            for k in sorted(types):
                print(f"  {k}: {types.get(k)}")
        if issues:
            print("issues:")
            for it in issues[:40]:
                if not isinstance(it, dict):
                    continue
                print(f"- {it.get('severity','')}: {it.get('message','')}")
            if len(issues) > 40:
                print(f"- … ({len(issues) - 40} more)")

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
