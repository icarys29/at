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
from lib.path_policy import normalize_repo_relative_posix_path, resolve_path_under_project_root  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _validate_registry(project_root: Path, registry_path: str, registry: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"registry_path": registry_path, "docs_total": 0, "docs_missing_files": 0, "tiers": {}}

    if registry is None:
        issues.append({"severity": "error", "message": "docs registry missing or invalid JSON"})
        return (issues, summary)

    if registry.get("version") != 1:
        issues.append({"severity": "error", "message": f"registry.version must be 1 (got {registry.get('version')!r})"})

    docs = registry.get("docs")
    if not isinstance(docs, list) or not docs:
        issues.append({"severity": "error", "message": "registry.docs must be a non-empty array"})
        return (issues, summary)

    seen_ids: set[str] = set()
    tiers: dict[str, int] = {}
    missing_files = 0
    missing_when = 0
    for item in docs[:2000]:
        if not isinstance(item, dict):
            continue
        doc_id = item.get("id")
        path = item.get("path")
        tier = item.get("tier")
        when = item.get("when")
        if not isinstance(doc_id, str) or not doc_id.strip():
            issues.append({"severity": "error", "message": "doc entry missing id"})
            continue
        did = doc_id.strip()
        if did in seen_ids:
            issues.append({"severity": "error", "message": f"duplicate doc id: {did!r}"})
        seen_ids.add(did)
        if not isinstance(path, str) or not path.strip():
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing path"})
            continue
        norm = normalize_repo_relative_posix_path(path.strip())
        if not norm:
            issues.append({"severity": "error", "doc_id": did, "message": f"invalid doc path: {path!r}"})
            continue
        resolved = resolve_path_under_project_root(project_root, norm)
        if resolved is None or not resolved.exists():
            missing_files += 1
            issues.append({"severity": "error", "doc_id": did, "path": norm, "message": "doc file missing"})
        if isinstance(tier, int):
            tiers[str(tier)] = tiers.get(str(tier), 0) + 1
        if not isinstance(when, str) or not when.strip():
            missing_when += 1
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required 'when' (used for planner context selection)"})

    summary["docs_total"] = len(seen_ids)
    summary["docs_missing_files"] = missing_files
    summary["docs_missing_when"] = missing_when
    summary["tiers"] = tiers
    return (issues, summary)


def _run_registry_md_check(project_root: Path, registry_path: str) -> dict[str, Any]:
    """
    Deterministic check: docs/DOCUMENTATION_REGISTRY.md must be in sync with the JSON registry.
    We do not auto-fix in the gate; the docs-keeper should run the generator.
    """
    import subprocess

    script = (project_root / "scripts" / "docs" / "generate_registry_md.py").resolve()
    # When running inside a project that uses the plugin, the generator script will typically
    # be in the plugin root, not the project root. Try plugin root via env; fallback to no-check.
    plugin_root = Path((__import__("os").environ.get("CLAUDE_PLUGIN_ROOT") or "")).expanduser()
    if plugin_root and plugin_root.is_dir():
        cand = (plugin_root / "scripts" / "docs" / "generate_registry_md.py").resolve()
        if cand.exists():
            script = cand

    if not script.exists():
        return {"status": "skipped", "reason": "missing scripts/docs/generate_registry_md.py"}

    proc = subprocess.run(
        [sys.executable, str(script), "--project-dir", str(project_root), "--registry-path", registry_path, "--check"],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = (proc.stdout or "")[-4000:]
    return {"status": "passed" if proc.returncode == 0 else "failed", "exit_code": proc.returncode, "output_tail": out}


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
        summary = {"registry_path": reg_path, "docs_total": 0, "docs_missing_files": 0, "tiers": {}}
    else:
        registry = load_docs_registry(project_root, reg_path)
        if registry is None and not require:
            issues = [{"severity": "warning", "message": f"docs.require_registry=false and registry missing: {reg_path!r}"}]
            ok = True
            summary = {"registry_path": reg_path, "docs_total": 0, "docs_missing_files": 0, "docs_missing_when": 0, "tiers": {}}
        else:
            issues, summary = _validate_registry(project_root, reg_path, registry)
            # Additional strictness: require the human-readable markdown view to match the JSON registry.
            md_check = _run_registry_md_check(project_root, reg_path)
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
    write_json(out_dir / "docs_gate_report.json", report)

    sum_md = [
        "# Docs Summary (at)",
        "",
        f"- generated_at: `{docs_summary['generated_at']}`",
        f"- registry_path: `{docs_summary.get('registry_path','')}`",
        f"- docs_total: `{docs_summary.get('docs_total','')}`",
        f"- docs_missing_files: `{docs_summary.get('docs_missing_files','')}`",
        f"- docs_missing_when: `{docs_summary.get('docs_missing_when','')}`",
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
    write_text(out_dir / "docs_gate_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
