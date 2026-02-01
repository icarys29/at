#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs gate (registry validation + deterministic summary)

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

from lib.docs_registry import get_docs_registry_path, get_docs_require_registry, load_docs_registry  # noqa: E402
from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.docs_validation import find_broken_links, find_orphan_docs, run_registry_md_check, validate_registry_v2  # noqa: E402


def _validate_registry(
    project_root: Path, registry_path: str, registry: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    issues, summary, type_map = validate_registry_v2(project_root, registry_path=registry_path, registry=registry)
    orphan_docs: list[str] = []
    broken_links: list[dict[str, str]] = []
    if registry and type_map:
        # Orphan docs under managed dirs.
        orphan_docs = find_orphan_docs(project_root, registry, type_map)
        if orphan_docs:
            issues.append(
                {"severity": "error", "message": f"orphan docs detected under managed dirs: {len(orphan_docs)} (register or delete)"}
            )

        # Broken link detection (best-effort; avoid deep analysis).
        doc_paths: list[str] = []
        docs = registry.get("docs") if isinstance(registry.get("docs"), list) else []
        for it in docs:
            if isinstance(it, dict) and isinstance(it.get("path"), str) and it.get("path").strip():
                doc_paths.append(it.get("path").strip())
        broken_links = find_broken_links(project_root, doc_paths=[p for p in doc_paths if isinstance(p, str)])
        if broken_links:
            issues.append(
                {"severity": "error", "message": f"broken markdown links detected: {len(broken_links)} (fix links or remove)"}
            )

    details = {
        "orphan_docs": {"count": len(orphan_docs), "sample": orphan_docs[:20]},
        "broken_links": {"count": len(broken_links), "sample": broken_links[:20]},
    }
    return (issues, summary, details)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate docs registry + write docs summary + docs gate report.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    reg_path = get_docs_registry_path(config)
    require = get_docs_require_registry(config)

    # Hard rule to prevent drift.
    if (project_root / "docs" / "REGISTRY.json").exists():
        drift_issue = {"severity": "error", "message": "docs/REGISTRY.json exists; standardize on docs/DOCUMENTATION_REGISTRY.json"}
        issues = [drift_issue]
        ok = False
        summary = {"registry_path": reg_path, "docs_total": 0, "docs_missing_files": 0, "docs_missing_when": 0, "docs_missing_required_fields": 0, "tiers": {}, "types": {}}
        details = {"orphan_docs": {"count": 0, "sample": []}, "broken_links": {"count": 0, "sample": []}}
    else:
        registry = load_docs_registry(project_root, reg_path)
        if registry is None and not require:
            issues = [{"severity": "warning", "message": f"docs.require_registry=false and registry missing: {reg_path!r}"}]
            ok = True
            summary = {"registry_path": reg_path, "docs_total": 0, "docs_missing_files": 0, "docs_missing_when": 0, "docs_missing_required_fields": 0, "tiers": {}, "types": {}}
            details = {"orphan_docs": {"count": 0, "sample": []}, "broken_links": {"count": 0, "sample": []}}
        else:
            issues, summary, details = _validate_registry(project_root, reg_path, registry)
            # Additional strictness: require the human-readable markdown view to match the JSON registry.
            md_check = run_registry_md_check(project_root, registry_path=reg_path)
            if md_check.get("status") == "failed":
                issues.append({"severity": "error", "message": "docs/DOCUMENTATION_REGISTRY.md is out of sync (run scripts/docs/generate_registry_md.py)"})
            elif md_check.get("status") == "skipped":
                # Don't block deliver if the generator isn't available; report warning.
                issues.append({"severity": "warning", "message": f"registry markdown check skipped: {md_check.get('reason','')}"})

            ok = not any(i.get("severity") == "error" for i in issues)

    out_dir = session_dir / "documentation"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs_summary = {"version": 1, "generated_at": utc_now(), **summary}
    write_json(out_dir / "docs_summary.json", docs_summary)

    report = {"version": 1, "generated_at": utc_now(), "ok": ok, "require_registry": bool(require), "issues": issues}
    report["details"] = details if isinstance(details, dict) else {}
    write_json(out_dir / "docs_gate_report.json", report)

    sum_md = [
        "# Docs Summary (at)",
        "",
        f"- generated_at: `{docs_summary['generated_at']}`",
        f"- registry_path: `{docs_summary.get('registry_path','')}`",
        f"- docs_total: `{docs_summary.get('docs_total','')}`",
        f"- docs_missing_files: `{docs_summary.get('docs_missing_files','')}`",
        f"- docs_missing_when: `{docs_summary.get('docs_missing_when','')}`",
        f"- docs_missing_required_fields: `{docs_summary.get('docs_missing_required_fields','')}`",
        "",
    ]
    write_text(out_dir / "docs_summary.md", "\n".join(sum_md))

    md = ["# Docs Gate Report (at)", "", f"- generated_at: `{report['generated_at']}`", f"- ok: `{str(ok).lower()}`", ""]
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            sev = it.get("severity", "")
            msg = it.get("message", "")
            doc_id = it.get("doc_id", "")
            tag = doc_id if doc_id else "docs"
            md.append(f"- `{sev}` `{tag}` — {msg}")
        md.append("")
    orphan_sample = ((report.get("details") or {}).get("orphan_docs") or {}).get("sample") if isinstance(report.get("details"), dict) else None
    if isinstance(orphan_sample, list) and orphan_sample:
        md.append("## Orphan Docs (sample)")
        md.append("")
        for p in orphan_sample[:20]:
            if isinstance(p, str) and p.strip():
                md.append(f"- `{p.strip()}`")
        md.append("")
    broken_sample = ((report.get("details") or {}).get("broken_links") or {}).get("sample") if isinstance(report.get("details"), dict) else None
    if isinstance(broken_sample, list) and broken_sample:
        md.append("## Broken Links (sample)")
        md.append("")
        for it in broken_sample[:20]:
            if not isinstance(it, dict):
                continue
            md.append(f"- `{it.get('doc','')}` → `{it.get('link','')}` — {it.get('reason','')}")
        md.append("")
    write_text(out_dir / "docs_gate_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
