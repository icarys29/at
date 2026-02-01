#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Summarize gate results into a single artifact (for remediation efficiency)

Writes:
- SESSION_DIR/status/gates_summary.json
- SESSION_DIR/status/gates_summary.md

This is best-effort: missing reports are recorded as "missing", not fatal.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import json
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _load_report(session_dir: Path, rel: str) -> dict[str, Any] | None:
    path = (session_dir / rel).resolve()
    if not path.exists():
        return None
    data = load_json_safe(path, default=None)
    return data if isinstance(data, dict) else None


def _ok_field(report: dict[str, Any] | None) -> bool | None:
    if not report:
        return None
    ok = report.get("ok")
    return bool(ok) if isinstance(ok, bool) else None


def _issues_sample(report: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    if not report:
        return []
    issues = report.get("issues")
    if not isinstance(issues, list) or not issues:
        return []
    out: list[str] = []
    for it in issues[:200]:
        if not isinstance(it, dict):
            continue
        sev = str(it.get("severity", "")).strip()
        msg = str(it.get("message", "")).strip()
        if not msg:
            continue
        tag_bits: list[str] = []
        if isinstance(it.get("task_id"), str) and it.get("task_id").strip():
            tag_bits.append(it.get("task_id").strip())
        if isinstance(it.get("criterion_id"), str) and it.get("criterion_id").strip():
            tag_bits.append(it.get("criterion_id").strip())
        tag = "/".join(tag_bits) if tag_bits else ""
        prefix = f"{sev} {tag}".strip()
        out.append(f"{prefix} — {msg}" if prefix else msg)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize deterministic gate reports into a single session artifact.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    # Known report locations (source of truth: scripts under scripts/validate + scripts/quality).
    gates = [
        ("task_artifacts", "quality/task_artifacts_report.json", "Validate task YAML artifacts"),
        ("plan_adherence", "quality/plan_adherence_report.json", "Run acceptance verifications"),
        ("parallel_conformance", "quality/parallel_conformance_report.json", "Validate task scopes and overlaps"),
        ("quality_suite", "quality/quality_report.json", "Run configured quality suite"),
        ("docs_gate", "documentation/docs_gate_report.json", "Validate docs registry and doc drift"),
        ("changed_files", "quality/changed_files_report.json", "Validate git changed files vs planned scope"),
        ("compliance", "compliance/compliance_report.json", "Generate compliance report"),
    ]

    results: list[dict[str, Any]] = []
    overall_ok = True
    for gate_id, rel, label in gates:
        report = _load_report(session_dir, rel)
        ok = _ok_field(report)
        status = "missing" if report is None else ("passed" if ok is True else "failed")
        if status == "failed":
            overall_ok = False
        results.append(
            {
                "id": gate_id,
                "label": label,
                "report_path": rel,
                "status": status,
                "issues_sample": _issues_sample(report),
            }
        )

    out_dir = session_dir / "status"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {"version": 1, "generated_at": utc_now(), "ok": overall_ok, "gates": results}
    write_json(out_dir / "gates_summary.json", payload)

    md: list[str] = []
    md.append("# Gates Summary (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- ok: `{str(overall_ok).lower()}`")
    md.append("")
    md.append("## Gates")
    md.append("")
    for g in results:
        md.append(f"- `{g['id']}`: `{g['status']}` — {g['label']} (`{g['report_path']}`)")
        for s in (g.get("issues_sample") or [])[:6]:
            if isinstance(s, str) and s.strip():
                md.append(f"  - {s.strip()}")
    md.append("")
    write_text(out_dir / "gates_summary.md", "\n".join(md))

    print(str(out_dir / "gates_summary.md"))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

