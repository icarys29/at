#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Retrospective (session-backed, controlled, deterministic)

Produces a concise retrospective report from low-sensitivity session artifacts.
This is intended to:
- summarize outcome (gates/quality/docs/compliance)
- capture actionable improvements for next runs
- provide a stable artifact that can be fed into learning extraction

Writes:
- SESSION_DIR/retrospective/RETROSPECTIVE.json
- SESSION_DIR/retrospective/RETROSPECTIVE.md

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
    "retrospective.py is deprecated and will be removed in v0.5.0. "
    "Agent reasoning task. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))


from lib.io import load_json_safe, safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _load_obj(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None


def _count_issue_severity(report: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(report, dict):
        return {"errors": 0, "warnings": 0}
    issues = report.get("issues")
    if not isinstance(issues, list):
        return {"errors": 0, "warnings": 0}
    errs = 0
    warns = 0
    for it in issues[:10_000]:
        if not isinstance(it, dict):
            continue
        sev = it.get("severity")
        if sev == "error":
            errs += 1
        elif sev == "warning":
            warns += 1
    return {"errors": errs, "warnings": warns}


def _quality_failed_ids(quality: dict[str, Any] | None) -> list[str]:
    if not isinstance(quality, dict):
        return []
    results = quality.get("results")
    if not isinstance(results, list):
        return []
    out: list[str] = []
    for r in results[:5000]:
        if not isinstance(r, dict):
            continue
        if r.get("status") != "failed":
            continue
        cid = r.get("id")
        if isinstance(cid, str) and cid.strip():
            out.append(cid.strip())
    # stable, dedup
    uniq: list[str] = []
    seen: set[str] = set()
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq[:100]


def _gates_status(gates_summary: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    failing: list[str] = []
    missing: list[str] = []
    if not isinstance(gates_summary, dict):
        return failing, missing
    gates = gates_summary.get("gates")
    if not isinstance(gates, list):
        return failing, missing
    for g in gates[:200]:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        st = g.get("status")
        if not isinstance(gid, str) or not gid.strip():
            continue
        if st == "failed":
            failing.append(gid.strip())
        elif st == "missing":
            missing.append(gid.strip())
    # stable order by appearance is fine; dedup anyway.
    out_fail: list[str] = []
    seen_f: set[str] = set()
    for x in failing:
        if x in seen_f:
            continue
        seen_f.add(x)
        out_fail.append(x)
    out_miss: list[str] = []
    seen_m: set[str] = set()
    for x in missing:
        if x in seen_m:
            continue
        seen_m.add(x)
        out_miss.append(x)
    return out_fail, out_miss


def _recommendations(
    *,
    session_dir: Path,
    failing_gates: list[str],
    missing_gates: list[str],
    quality_failed: list[str],
    docs_gate: dict[str, Any] | None,
    plan_adherence: dict[str, Any] | None,
    session_audit: dict[str, Any] | None,
) -> list[str]:
    recs: list[str] = []

    # Prefer existing auditor recommendations when present.
    if isinstance(session_audit, dict):
        sr = session_audit.get("recommendations")
        if isinstance(sr, list):
            for r in sr[:50]:
                if isinstance(r, str) and r.strip():
                    recs.append(r.strip())

    if missing_gates:
        recs.append("Generate missing gate artifacts (rerun deterministic gates for this session).")
        recs.append(f"Run: /at:verify --session \"{session_dir}\" (or rerun the missing gate scripts).")

    if failing_gates:
        if "docs_gate" in failing_gates:
            recs.append("Docs gate failed: run /at:docs-keeper sync to repair registry/drift.")
        if "quality_suite" in failing_gates or quality_failed:
            cid = quality_failed[0] if quality_failed else "<command_id>"
            recs.append(f"Quality suite failed: use /at:fix-quality {cid} --session \"{session_dir}\" (format-only) or rerun full suite.")
        if "plan_adherence" in failing_gates:
            recs.append("Plan adherence failed: ensure tasks include explicit acceptance_criteria.verifications and rerun plan adherence gate.")
        if "parallel_conformance" in failing_gates:
            recs.append("Parallel conformance failed: reduce overlapping write scopes / reorder tasks; rerun the parallel conformance gate.")
        if "changed_files" in failing_gates:
            recs.append("Changed-files gate failed: align git changes with declared task file_scope.writes.")
        if "task_artifacts" in failing_gates:
            recs.append("Task artifacts gate failed: ensure every task writes its YAML artifact (summary + changed_files).")
        if "compliance" in failing_gates:
            recs.append("Compliance gate failed: generate compliance report after required gates are green.")

    # Gate report issue hints (low sensitivity).
    docs_counts = _count_issue_severity(docs_gate)
    if docs_counts["errors"] > 0:
        recs.append("Docs issues detected: prioritize registry integrity (missing files/fields, broken links, or orphan docs).")

    plan_counts = _count_issue_severity(plan_adherence)
    if plan_counts["errors"] > 0:
        recs.append("Plan adherence issues detected: tighten verifications and avoid implicit acceptance checks.")

    # Dedup stable.
    out: list[str] = []
    seen: set[str] = set()
    for r in recs:
        rr = " ".join(str(r).split())
        if not rr or rr in seen:
            continue
        seen.add(rr)
        out.append(rr)
    return out[:30]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic retrospective report for an at session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=6000)

    gates_summary = _load_obj(session_dir, "status/gates_summary.json")
    compliance = _load_obj(session_dir, "compliance/compliance_report.json")
    quality = _load_obj(session_dir, "quality/quality_report.json")
    docs_gate = _load_obj(session_dir, "documentation/docs_gate_report.json")
    plan_adherence = _load_obj(session_dir, "quality/plan_adherence_report.json")
    parallel = _load_obj(session_dir, "quality/parallel_conformance_report.json")
    changed_files = _load_obj(session_dir, "quality/changed_files_report.json")
    session_audit = _load_obj(session_dir, "status/session_audit.json")
    session_diagnostics = _load_obj(session_dir, "status/session_diagnostics.json")

    failing_gates, missing_gates = _gates_status(gates_summary)
    quality_failed = _quality_failed_ids(quality)

    compliance_decision = compliance.get("decision") if isinstance(compliance, dict) else None
    compliance_ok = compliance.get("ok") if isinstance(compliance, dict) else None

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "request_head": request_text[:1200].strip(),
        "outcome": {
            "gates_ok": (gates_summary.get("ok") if isinstance(gates_summary, dict) else None),
            "compliance_decision": compliance_decision,
            "compliance_ok": compliance_ok,
            "quality_ok": (quality.get("ok") if isinstance(quality, dict) else None),
            "docs_ok": (docs_gate.get("ok") if isinstance(docs_gate, dict) else None),
        },
        "signals": {
            "failing_gates": failing_gates,
            "missing_gates": missing_gates,
            "quality_failed_command_ids": quality_failed,
            "issues": {
                "plan_adherence": _count_issue_severity(plan_adherence),
                "parallel_conformance": _count_issue_severity(parallel),
                "changed_files": _count_issue_severity(changed_files),
                "docs_gate": _count_issue_severity(docs_gate),
            },
        },
        "references": {
            "gates_summary": "status/gates_summary.json" if gates_summary else None,
            "compliance_report": "compliance/compliance_report.json" if compliance else None,
            "quality_report": "quality/quality_report.json" if quality else None,
            "docs_gate_report": "documentation/docs_gate_report.json" if docs_gate else None,
            "session_audit": "status/session_audit.json" if session_audit else None,
            "session_diagnostics": "status/session_diagnostics.json" if session_diagnostics else None,
        },
    }

    report["recommendations"] = _recommendations(
        session_dir=session_dir,
        failing_gates=failing_gates,
        missing_gates=missing_gates,
        quality_failed=quality_failed,
        docs_gate=docs_gate,
        plan_adherence=plan_adherence,
        session_audit=session_audit,
    )

    out_dir = session_dir / "retrospective"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "RETROSPECTIVE.json", report)

    md: list[str] = []
    md.append("# Retrospective (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- session_id: `{report['session_id']}`")
    if isinstance(compliance_decision, str) and compliance_decision:
        md.append(f"- compliance_decision: `{compliance_decision}`")
    if isinstance(compliance_ok, bool):
        md.append(f"- compliance_ok: `{str(compliance_ok).lower()}`")
    md.append("")

    md.append("## Outcome")
    md.append("")
    outcome = report.get("outcome") if isinstance(report.get("outcome"), dict) else {}
    for k in ("gates_ok", "quality_ok", "docs_ok", "compliance_ok"):
        if k in outcome:
            md.append(f"- {k}: `{outcome.get(k)}`")
    md.append("")

    md.append("## Signals")
    md.append("")
    if failing_gates:
        md.append("- failing_gates:")
        for g in failing_gates[:40]:
            md.append(f"  - `{g}`")
    if missing_gates:
        md.append("- missing_gates:")
        for g in missing_gates[:40]:
            md.append(f"  - `{g}`")
    if quality_failed:
        md.append("- quality_failed_command_ids:")
        for cid in quality_failed[:40]:
            md.append(f"  - `{cid}`")
    if not failing_gates and not missing_gates and not quality_failed:
        md.append("- (no major negative signals detected)")
    md.append("")

    md.append("## Recommendations")
    md.append("")
    recs = report.get("recommendations")
    if isinstance(recs, list) and recs:
        for r in recs[:30]:
            if isinstance(r, str) and r.strip():
                md.append(f"- {r.strip()}")
    else:
        md.append("- No recommendations (session appears healthy).")
    md.append("")

    if session_diagnostics and isinstance(session_diagnostics.get("next_steps"), list):
        md.append("## Next steps (from diagnostics)")
        md.append("")
        for s in (session_diagnostics.get("next_steps") or [])[:20]:
            if isinstance(s, str) and s.strip():
                md.append(f"- {s.strip()}")
        md.append("")

    write_text(out_dir / "RETROSPECTIVE.md", "\n".join(md))
    print(str(out_dir / "RETROSPECTIVE.md"))
    return 0 if compliance_ok is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
