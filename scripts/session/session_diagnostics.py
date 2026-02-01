#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Session diagnostics report (artifact-first)

Writes:
- SESSION_DIR/status/session_diagnostics.json
- SESSION_DIR/status/session_diagnostics.md

This script prefers low-sensitivity session artifacts and only consults audit logs
when audit is explicitly enabled in `.claude/project.yaml`.

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

from lib.io import load_json_safe, safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _load_report(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an artifact-first diagnostics report for a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=6000)
    session_meta = _load_report(session_dir, "session.json")
    actions = _load_report(session_dir, "planning/actions.json")
    gates_summary = _load_report(session_dir, "status/gates_summary.json")

    failing_gates: list[dict[str, Any]] = []
    missing_gates: list[dict[str, Any]] = []
    if isinstance(gates_summary, dict):
        gates = gates_summary.get("gates")
        if isinstance(gates, list):
            for g in gates[:100]:
                if not isinstance(g, dict):
                    continue
                status = g.get("status")
                if status == "failed":
                    failing_gates.append(g)
                elif status == "missing":
                    missing_gates.append(g)

    quality = _load_report(session_dir, "quality/quality_report.json")
    quality_failed: list[str] = []
    if isinstance(quality, dict):
        results = quality.get("results")
        if isinstance(results, list):
            for r in results[:200]:
                if isinstance(r, dict) and r.get("status") == "failed" and isinstance(r.get("id"), str):
                    quality_failed.append(r.get("id").strip())

    plan_adherence = _load_report(session_dir, "quality/plan_adherence_report.json")
    parallel = _load_report(session_dir, "quality/parallel_conformance_report.json")
    docs_gate = _load_report(session_dir, "documentation/docs_gate_report.json")
    compliance = _load_report(session_dir, "compliance/compliance_report.json")

    missing_artifacts: list[str] = []
    for rel in (
        "planning/actions.json",
        "status/gates_summary.json",
        "quality/plan_adherence_report.json",
        "quality/parallel_conformance_report.json",
        "quality/quality_report.json",
        "documentation/docs_gate_report.json",
        "compliance/compliance_report.json",
    ):
        if not (session_dir / rel).exists():
            missing_artifacts.append(rel)

    audit_cfg = config.get("audit") if isinstance(config.get("audit"), dict) else {}
    audit_enabled = bool(audit_cfg.get("enabled") is True)

    next_steps: list[str] = []
    if failing_gates:
        next_steps.append("Review status/gates_summary.md and the failing gate report(s).")
    if missing_gates:
        next_steps.append("Generate missing gate reports by rerunning deterministic gates for this session.")
    if quality_failed:
        next_steps.append("Consider /at:fix-quality <command_id> for one failing quality command (format-only by default).")
    if not missing_artifacts:
        next_steps.append("If the session is blocked, use /at:run triage --session <id|dir> to generate an RCA.")
    if audit_enabled:
        next_steps.append("Audit is enabled: consider /at:audit-report for tool-level timing/failure summaries.")

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "ok": bool(gates_summary.get("ok") is True) if isinstance(gates_summary, dict) else None,
        "request_head": request_text[:1200].strip(),
        "summary": {
            "has_actions": isinstance(actions, dict),
            "failing_gates": len(failing_gates),
            "missing_gates": len(missing_gates),
            "quality_failed": len(quality_failed),
            "missing_artifacts": len(missing_artifacts),
        },
        "key_artifacts": {
            "session_json": "session.json" if session_meta else None,
            "actions_json": "planning/actions.json" if actions else None,
            "gates_summary_json": "status/gates_summary.json" if gates_summary else None,
            "plan_adherence_report_json": "quality/plan_adherence_report.json" if plan_adherence else None,
            "parallel_conformance_report_json": "quality/parallel_conformance_report.json" if parallel else None,
            "quality_report_json": "quality/quality_report.json" if quality else None,
            "docs_gate_report_json": "documentation/docs_gate_report.json" if docs_gate else None,
            "compliance_report_json": "compliance/compliance_report.json" if compliance else None,
        },
        "failing_gate_ids": [str(g.get("id", "")).strip() for g in failing_gates if isinstance(g, dict) and str(g.get("id", "")).strip()],
        "quality_failed_command_ids": quality_failed,
        "missing_artifacts": missing_artifacts,
        "audit": {"enabled": audit_enabled},
        "next_steps": next_steps,
    }

    out_dir = session_dir / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "session_diagnostics.json", report)

    md: list[str] = []
    md.append("# Session Diagnostics (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- session_id: `{report['session_id']}`")
    if report.get("ok") is not None:
        md.append(f"- ok: `{str(bool(report.get('ok'))).lower()}`")
    md.append("")
    md.append("## Request (head)")
    md.append("")
    md.append("```md")
    md.append(request_text[:1200].rstrip())
    md.append("```")
    md.append("")
    md.append("## Summary")
    md.append("")
    summ = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    for k in ("has_actions", "failing_gates", "missing_gates", "quality_failed", "missing_artifacts"):
        md.append(f"- {k}: `{summ.get(k)}`")
    md.append("")
    if failing_gates:
        md.append("## Failing gates")
        md.append("")
        for g in failing_gates[:30]:
            md.append(f"- `{g.get('id','')}` — `{g.get('report_path','')}`")
            for s in (g.get("issues_sample") or [])[:6]:
                if isinstance(s, str) and s.strip():
                    md.append(f"  - {s.strip()}")
        md.append("")
    if quality_failed:
        md.append("## Failed quality commands")
        md.append("")
        for cid in quality_failed[:40]:
            md.append(f"- `{cid}`")
        md.append("")
    if missing_artifacts:
        md.append("## Missing artifacts")
        md.append("")
        for rel in missing_artifacts[:60]:
            md.append(f"- `{rel}`")
        md.append("")
    md.append("## Next steps")
    md.append("")
    for s in next_steps[:20]:
        md.append(f"- {s}")
    md.append("")
    write_text(out_dir / "session_diagnostics.md", "\n".join(md))

    print(str(out_dir / "session_diagnostics.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

