#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate deterministic triage context for a session

Writes:
- SESSION_DIR/analysis/TRIAGE_CONTEXT.json
- SESSION_DIR/analysis/TRIAGE_CONTEXT.md

This is a deterministic artifact packer intended to help the root-cause-analyzer
agent focus on the most relevant failure evidence without relying on audit traces.

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
    "run_triage.py is deprecated and will be removed in v0.5.0. "
    "Triage orchestration will be merged into /at:run skill. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, safe_read_text, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _load_report(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None





def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic triage context artifacts for a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=8000)
    gates_summary = _load_report(session_dir, "status/gates_summary.json")

    failing_gates: list[dict[str, Any]] = []
    if isinstance(gates_summary, dict):
        gates = gates_summary.get("gates")
        if isinstance(gates, list):
            for g in gates[:50]:
                if not isinstance(g, dict):
                    continue
                if g.get("status") == "failed":
                    failing_gates.append(g)

    payload: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "request_head": request_text[:1200].strip(),
        "failing_gates": failing_gates,
        "artifact_paths": {
            "gates_summary_md": "status/gates_summary.md" if (session_dir / "status" / "gates_summary.md").exists() else None,
            "gates_summary_json": "status/gates_summary.json" if (session_dir / "status" / "gates_summary.json").exists() else None,
            "quality_report_json": "quality/quality_report.json" if (session_dir / "quality" / "quality_report.json").exists() else None,
            "plan_adherence_report_json": "quality/plan_adherence_report.json" if (session_dir / "quality" / "plan_adherence_report.json").exists() else None,
            "verifications_report_json": "quality/verifications_report.json" if (session_dir / "quality" / "verifications_report.json").exists() else None,
            "changed_files_report_json": "quality/changed_files_report.json" if (session_dir / "quality" / "changed_files_report.json").exists() else None,
            "docs_gate_report_json": "documentation/docs_gate_report.json" if (session_dir / "documentation" / "docs_gate_report.json").exists() else None,
            "compliance_report_json": "compliance/compliance_report.json" if (session_dir / "compliance" / "compliance_report.json").exists() else None,
        },
        "notes": [
            "This context is artifact-first and does not require audit traces.",
            "Use it as an input to the root-cause-analyzer agent.",
        ],
    }

    out_dir = session_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "TRIAGE_CONTEXT.json", payload)

    md: list[str] = []
    md.append("# Triage Context (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- session_id: `{payload['session_id']}`")
    md.append("")
    md.append("## Request (head)")
    md.append("")
    md.append("```md")
    md.append(request_text[:1200].rstrip())
    md.append("```")
    md.append("")
    md.append("## Failing gates")
    md.append("")
    if failing_gates:
        for g in failing_gates[:20]:
            md.append(f"- `{g.get('id','')}` — `{g.get('report_path','')}`")
            for s in (g.get("issues_sample") or [])[:6]:
                if isinstance(s, str) and s.strip():
                    md.append(f"  - {s.strip()}")
    else:
        md.append("- (none detected; gates_summary.json missing or all passed)")
    md.append("")
    md.append("## Key artifacts")
    md.append("")
    for k, v in payload["artifact_paths"].items():
        md.append(f"- `{k}`: `{v}`" if v else f"- `{k}`: (missing)")
    md.append("")
    write_text(out_dir / "TRIAGE_CONTEXT.md", "\n".join(md))

    print(str(out_dir / "TRIAGE_CONTEXT.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
