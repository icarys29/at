#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Session auditor (deterministic scorecard + recommendations)

This is an artifact-first, low-sensitivity alternative to trace-heavy auditing.
It scores a session using deterministic artifacts and produces actionable
recommendations.

Writes:
- SESSION_DIR/status/session_audit.json
- SESSION_DIR/status/session_audit.md

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "session_auditor.py is deprecated and will be removed in v0.5.0. "
    "Agent reasoning task. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


@dataclass(frozen=True)
class Score:
    id: str
    label: str
    score: int  # 0..100
    details: str


def _load_obj(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None


def _count_issue_severity(report: dict[str, Any] | None) -> tuple[int, int]:
    """Return (errors, warnings) for report.issues[] where present."""
    if not isinstance(report, dict):
        return (0, 0)
    issues = report.get("issues")
    if not isinstance(issues, list):
        return (0, 0)
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
    return (errs, warns)


def _score_ok(report: dict[str, Any] | None) -> int | None:
    if not isinstance(report, dict):
        return None
    ok = report.get("ok")
    return 100 if ok is True else (0 if ok is False else None)


def _safe_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _quality_score(quality: dict[str, Any] | None) -> tuple[int | None, list[str]]:
    """
    Score based on quality_report.json:
    - 100 when ok=true
    - else: 100 - (commands_failed/commands_total)*100
    Returns (score_or_none, failed_ids)
    """
    if not isinstance(quality, dict):
        return (None, [])
    ok = quality.get("ok")
    if ok is True:
        return (100, [])
    results = quality.get("results")
    if not isinstance(results, list) or not results:
        return (0 if ok is False else None, [])
    total = len(results)
    failed_ids: list[str] = []
    failed = 0
    for r in results[:5000]:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "failed":
            failed += 1
            rid = r.get("id")
            if isinstance(rid, str) and rid.strip():
                failed_ids.append(rid.strip())
    score = int(round(max(0.0, 100.0 - (failed / max(1, total)) * 100.0)))
    return (score, failed_ids[:50])


def _gates_score(gates_summary: dict[str, Any] | None) -> tuple[int | None, dict[str, int]]:
    """
    Score based on gates_summary.json:
    - passed: +1
    - missing: counts as 0.5 failure
    - failed: counts as failure
    Returns (score_or_none, counts).
    """
    if not isinstance(gates_summary, dict):
        return (None, {"passed": 0, "failed": 0, "missing": 0, "total": 0})
    gates = gates_summary.get("gates")
    if not isinstance(gates, list) or not gates:
        return (None, {"passed": 0, "failed": 0, "missing": 0, "total": 0})
    passed = 0
    failed = 0
    missing = 0
    for g in gates[:200]:
        if not isinstance(g, dict):
            continue
        st = g.get("status")
        if st == "passed":
            passed += 1
        elif st == "failed":
            failed += 1
        elif st == "missing":
            missing += 1
    total = passed + failed + missing
    denom = passed + failed + (0.5 * missing)
    score = 100 if denom == 0 else int(round(max(0.0, (passed / denom) * 100.0)))
    return (score, {"passed": passed, "failed": failed, "missing": missing, "total": total})


def _status_label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Acceptable"
    if score >= 40:
        return "Needs Attention"
    return "Poor"


def _recommendations(
    *,
    session_dir: Path,
    gates_summary: dict[str, Any] | None,
    compliance: dict[str, Any] | None,
    quality_failed_ids: list[str],
    missing_artifacts: list[str],
) -> list[str]:
    recs: list[str] = []

    if missing_artifacts:
        recs.append("Rerun missing deterministic reports (see missing_artifacts list).")

    # Gate-specific suggestions.
    if isinstance(gates_summary, dict):
        gates = gates_summary.get("gates")
        if isinstance(gates, list):
            for g in gates[:50]:
                if not isinstance(g, dict):
                    continue
                gid = g.get("id")
                st = g.get("status")
                if not isinstance(gid, str) or not gid.strip():
                    continue
                if st not in {"failed", "missing"}:
                    continue
                gid_s = gid.strip()
                if gid_s == "task_artifacts":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/validate_task_artifacts.py\" --session \"{session_dir}\"")
                elif gid_s == "plan_adherence":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/plan_adherence.py\" --session \"{session_dir}\"")
                elif gid_s == "parallel_conformance":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/parallel_conformance.py\" --session \"{session_dir}\"")
                elif gid_s == "quality_suite":
                    if quality_failed_ids:
                        recs.append(f"Use: /at:fix-quality {quality_failed_ids[0]} --session \"{session_dir}\" (or rerun full suite)")
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/quality/run_quality_suite.py\" --session \"{session_dir}\"")
                elif gid_s == "e2e_gate":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/e2e_gate.py\" --session \"{session_dir}\"")
                elif gid_s == "docs_gate":
                    recs.append("Use: /at:docs-keeper lint (then /at:docs-keeper sync if needed).")
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/docs_gate.py\" --session \"{session_dir}\"")
                elif gid_s == "changed_files":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/validate/validate_changed_files.py\" --session \"{session_dir}\"")
                elif gid_s == "compliance":
                    recs.append(f"Run: uv run \"${{CLAUDE_PLUGIN_ROOT}}/scripts/compliance/generate_compliance_report.py\" --session \"{session_dir}\" --rerun-supporting-checks")

    if isinstance(compliance, dict):
        decision = compliance.get("decision")
        if decision == "REJECT":
            missing = compliance.get("missing") if isinstance(compliance.get("missing"), list) else []
            failing = compliance.get("failing") if isinstance(compliance.get("failing"), list) else []
            if missing:
                recs.append(f"Compliance rejected due to missing gates: {', '.join([str(x) for x in missing[:10]])}")
            if failing:
                recs.append(f"Compliance rejected due to failing gates: {', '.join([str(x) for x in failing[:10]])}")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for r in recs:
        rs = " ".join(str(r).split())
        if not rs or rs in seen:
            continue
        seen.add(rs)
        out.append(rs)
    return out[:20]


def _iter_jsonl(path: Path, *, max_lines: int = 200_000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if max_lines > 0 and i >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
    except Exception:
        return out
    return out


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _audit_tool_metrics(project_root: Path, *, session_id: str) -> dict[str, Any] | None:
    tools = (project_root / ".claude" / "audit_logs" / "tools.jsonl").resolve()
    if not tools.exists():
        return None
    rows = [r for r in _iter_jsonl(tools) if r.get("session_id") == session_id]
    if not rows:
        return None

    total_posts = 0
    failures = 0
    by_tool: dict[str, int] = {}
    # Pairing best-effort for durations.
    inflight: dict[str, list[dict[str, Any]]] = {}
    durations_ms: list[float] = []

    for r in rows:
        ev = r.get("event")
        tn = r.get("tool_name")
        if not isinstance(ev, str) or not isinstance(tn, str) or not tn.strip():
            continue
        tn_s = tn.strip()
        by_tool[tn_s] = by_tool.get(tn_s, 0) + 1

        call_id = r.get("tool_call_id")
        call_id_s = call_id.strip() if isinstance(call_id, str) and call_id.strip() else None
        ts = _parse_ts(r.get("ts"))

        if ev == "PreToolUse":
            inflight.setdefault(tn_s, []).append({"ts": ts, "tool_call_id": call_id_s})
            continue

        if ev != "PostToolUse":
            continue

        total_posts += 1
        result = r.get("result")
        if isinstance(result, dict):
            ec = result.get("exit_code")
            ok = result.get("ok")
            status = result.get("status")
            if isinstance(ec, int) and ec != 0:
                failures += 1
            elif isinstance(ok, bool) and ok is False:
                failures += 1
            elif isinstance(status, str) and status.strip().lower() in {"failed", "error", "timeout"}:
                failures += 1

        stack = inflight.get(tn_s) or []
        match_i = None
        if call_id_s:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i].get("tool_call_id") == call_id_s:
                    match_i = i
                    break
        if match_i is None:
            # LIFO match by tool name (best effort).
            match_i = len(stack) - 1 if stack else None
        if match_i is None:
            continue
        started = stack.pop(match_i)
        t0 = started.get("ts")
        if isinstance(t0, datetime) and isinstance(ts, datetime):
            dur_ms = (ts - t0).total_seconds() * 1000.0
            if dur_ms >= 0 and len(durations_ms) < 5000:
                durations_ms.append(dur_ms)

    fail_rate = (failures / max(1, total_posts)) if total_posts else 0.0
    # Conservative score: penalize failure rate heavily; ignore latency by default.
    tool_score = int(round(max(0.0, 100.0 - (fail_rate * 200.0))))

    durations_ms.sort()
    def _p(pct: float) -> float | None:
        if not durations_ms:
            return None
        idx = int(round((len(durations_ms) - 1) * pct))
        return float(durations_ms[idx])

    return {
        "version": 1,
        "tool_calls": total_posts,
        "tool_failures": failures,
        "tool_failure_rate": round(fail_rate, 4),
        "score": tool_score,
        "latency_ms": {"p50": _p(0.50), "p95": _p(0.95), "max": float(durations_ms[-1]) if durations_ms else None},
        "top_tools": sorted(by_tool.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "notes": [
            "Tool metrics are best-effort from audit logs (requires /at:setup-audit-hooks).",
            "Failure rate is computed from PostToolUse exit_code/ok/status fields when available.",
        ],
    }


def _load_previous_audit(project_root: Path, sessions_dir: str, *, current_session: Path, compare_with: str | None) -> dict[str, Any] | None:
    sessions_root = (project_root / sessions_dir).resolve()
    if compare_with and compare_with.strip():
        try:
            other = resolve_session_dir(project_root, sessions_dir, compare_with.strip())
        except Exception:
            other = None
        if other and (other / "status" / "session_audit.json").exists():
            data = load_json_safe(other / "status" / "session_audit.json", default=None)
            return data if isinstance(data, dict) else None
        return None

    if not sessions_root.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    try:
        for p in sessions_root.iterdir():
            if not p.is_dir() or p.resolve() == current_session.resolve():
                continue
            audit_path = p / "status" / "session_audit.json"
            if not audit_path.exists():
                continue
            try:
                mtime = audit_path.stat().st_mtime
            except Exception:
                continue
            candidates.append((mtime, p))
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    audit_path = candidates[0][1] / "status" / "session_audit.json"
    data = load_json_safe(audit_path, default=None)
    return data if isinstance(data, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic session audit scorecard and recommendations.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--format", default="full", choices=["full", "summary", "json"])
    parser.add_argument(
        "--compare",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compare against the previous session_audit.json (or --compare-with).",
    )
    parser.add_argument("--compare-with", default=None, help="Compare against a specific session id or directory.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    request_text, _ = safe_read_text(session_dir / "inputs" / "request.md", max_chars=6000)
    session_meta = _load_obj(session_dir, "session.json") or {}

    gates_summary = _load_obj(session_dir, "status/gates_summary.json")
    plan_adherence = _load_obj(session_dir, "quality/plan_adherence_report.json")
    parallel = _load_obj(session_dir, "quality/parallel_conformance_report.json")
    changed_files = _load_obj(session_dir, "quality/changed_files_report.json")
    quality = _load_obj(session_dir, "quality/quality_report.json")
    docs_gate = _load_obj(session_dir, "documentation/docs_gate_report.json")
    compliance = _load_obj(session_dir, "compliance/compliance_report.json")

    missing_artifacts: list[str] = []
    for rel in (
        "status/gates_summary.json",
        "quality/plan_adherence_report.json",
        "quality/parallel_conformance_report.json",
        "quality/quality_report.json",
        "documentation/docs_gate_report.json",
        "quality/changed_files_report.json",
        "compliance/compliance_report.json",
    ):
        if not (session_dir / rel).exists():
            missing_artifacts.append(rel)

    gate_score, gate_counts = _gates_score(gates_summary)
    quality_score, quality_failed_ids = _quality_score(quality)

    plan_score = _score_ok(plan_adherence)
    parallel_score = _score_ok(parallel)
    docs_score = _score_ok(docs_gate)
    scope_score = _score_ok(changed_files)
    compliance_score = _score_ok(compliance)

    # Evidence completeness (missing artifacts).
    evidence_score = max(0, 100 - (len(missing_artifacts) * 15))

    # Optional tool efficiency score (audit logs) when audit is enabled in config.
    audit_cfg = config.get("audit") if isinstance(config.get("audit"), dict) else {}
    audit_enabled = bool(audit_cfg.get("enabled") is True)
    tool_metrics = _audit_tool_metrics(project_root, session_id=session_dir.name) if audit_enabled else None
    tool_score = _safe_int(tool_metrics.get("score")) if isinstance(tool_metrics, dict) else None

    scores: list[Score] = []
    if gate_score is not None:
        scores.append(Score("gates", "Gates health", int(gate_score), f"passed={gate_counts['passed']} failed={gate_counts['failed']} missing={gate_counts['missing']}"))
    if quality_score is not None:
        scores.append(Score("quality", "Quality suite", int(quality_score), f"failed={len(quality_failed_ids)}"))
    if plan_score is not None:
        scores.append(Score("plan_adherence", "Plan adherence", int(plan_score), "ok=true means verifications satisfied (per policy)"))
    if parallel_score is not None:
        scores.append(Score("parallel_conformance", "Parallel conformance", int(parallel_score), "scope overlaps/out-of-order groups")
        )
    if docs_score is not None:
        scores.append(Score("docs_gate", "Docs gate", int(docs_score), "registry + drift + link/orphan checks"))
    if scope_score is not None:
        scores.append(Score("changed_files", "Changed files scope", int(scope_score), "git changes within planned write scopes"))
    if tool_score is not None:
        scores.append(Score("tool_efficiency", "Tool efficiency (audit)", int(tool_score), f"fail_rate={tool_metrics.get('tool_failure_rate') if isinstance(tool_metrics, dict) else None}"))
    if compliance_score is not None:
        scores.append(Score("compliance", "Compliance decision", int(compliance_score), "APPROVE requires all required gates ok"))
    scores.append(Score("evidence", "Evidence completeness", int(evidence_score), f"missing_artifacts={len(missing_artifacts)}"))

    # Overall score: weighted average over available metrics (stable weights).
    weights = {
        "compliance": 0.25,
        "gates": 0.23,
        "quality": 0.20,
        "plan_adherence": 0.10,
        "parallel_conformance": 0.05,
        "docs_gate": 0.05,
        "changed_files": 0.05,
        "tool_efficiency": 0.05,
        "evidence": 0.02,
    }
    total_w = 0.0
    weighted = 0.0
    for s in scores:
        w = float(weights.get(s.id, 0.0))
        if w <= 0:
            continue
        total_w += w
        weighted += w * float(s.score)
    overall = int(round(weighted / total_w)) if total_w > 0 else 0
    status = _status_label(overall)

    # Recommendation list.
    recs = _recommendations(
        session_dir=session_dir,
        gates_summary=gates_summary,
        compliance=compliance,
        quality_failed_ids=quality_failed_ids,
        missing_artifacts=missing_artifacts,
    )

    errs_plan, warns_plan = _count_issue_severity(plan_adherence)
    errs_parallel, warns_parallel = _count_issue_severity(parallel)
    errs_docs, warns_docs = _count_issue_severity(docs_gate)
    errs_changed, warns_changed = _count_issue_severity(changed_files)
    issue_counts = {
        "plan_adherence": {"errors": errs_plan, "warnings": warns_plan},
        "parallel_conformance": {"errors": errs_parallel, "warnings": warns_parallel},
        "docs_gate": {"errors": errs_docs, "warnings": warns_docs},
        "changed_files": {"errors": errs_changed, "warnings": warns_changed},
    }

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "workflow": session_meta.get("workflow"),
        "overall": {"score": overall, "status": status},
        "scores": [{"id": s.id, "label": s.label, "score": s.score, "details": s.details} for s in scores],
        "issue_counts": issue_counts,
        "quality_failed_command_ids": quality_failed_ids,
        "missing_artifacts": missing_artifacts,
        "audit": {"enabled": audit_enabled, "tool_metrics": tool_metrics},
        "recommendations": recs,
        "request_head": request_text[:1200].strip(),
    }

    if args.compare:
        prev = _load_previous_audit(project_root, sessions_dir, current_session=session_dir, compare_with=args.compare_with)
        if isinstance(prev, dict):
            prev_overall = prev.get("overall")
            prev_score = None
            if isinstance(prev_overall, dict) and isinstance(prev_overall.get("score"), int):
                prev_score = int(prev_overall.get("score"))
            delta_overall = (overall - prev_score) if isinstance(prev_score, int) else None

            prev_scores = prev.get("scores") if isinstance(prev.get("scores"), list) else []
            prev_map: dict[str, int] = {}
            for it in prev_scores[:50]:
                if isinstance(it, dict) and isinstance(it.get("id"), str) and isinstance(it.get("score"), int):
                    prev_map[it["id"]] = int(it["score"])
            delta_by_id: dict[str, int] = {}
            for s in scores:
                if s.id in prev_map:
                    delta_by_id[s.id] = int(s.score) - int(prev_map[s.id])
            report["comparison"] = {
                "baseline_session_id": prev.get("session_id"),
                "baseline_overall_score": prev_score,
                "delta_overall": delta_overall,
                "delta_by_metric": delta_by_id,
            }

    out_dir = session_dir / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "session_audit.json", report)

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if overall >= 60 else 1

    md: list[str] = []
    md.append("# Session Audit (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- session_id: `{report['session_id']}`")
    if isinstance(report.get("workflow"), str) and report.get("workflow"):
        md.append(f"- workflow: `{report.get('workflow')}`")
    md.append(f"- overall_score: `{overall}` ({status})")
    md.append("")

    if args.format == "full":
        md.append("## Request (head)")
        md.append("")
        md.append("```md")
        md.append(request_text[:1200].rstrip())
        md.append("```")
        md.append("")

    md.append("## Scorecard")
    md.append("")
    for s in scores:
        md.append(f"- `{s.id}`: `{s.score}` — {s.label} ({s.details})")
    md.append("")

    if missing_artifacts:
        md.append("## Missing artifacts")
        md.append("")
        for rel in missing_artifacts[:80]:
            md.append(f"- `{rel}`")
        md.append("")

    if quality_failed_ids:
        md.append("## Failed quality commands")
        md.append("")
        for cid in quality_failed_ids[:40]:
            md.append(f"- `{cid}`")
        md.append("")

    md.append("## Recommendations")
    md.append("")
    if recs:
        for r in recs:
            md.append(f"- {r}")
    else:
        md.append("- No recommendations (session appears healthy).")
    md.append("")

    comp = report.get("comparison")
    if isinstance(comp, dict) and args.format == "full":
        md.append("## Comparison")
        md.append("")
        md.append(f"- baseline_session_id: `{comp.get('baseline_session_id')}`")
        md.append(f"- delta_overall: `{comp.get('delta_overall')}`")
        deltas = comp.get("delta_by_metric")
        if isinstance(deltas, dict) and deltas:
            md.append("")
            md.append("### Delta by metric")
            md.append("")
            for k, v in sorted(deltas.items()):
                md.append(f"- `{k}`: `{v}`")
        md.append("")

    write_text(out_dir / "session_audit.md", "\n".join(md))
    print(str(out_dir / "session_audit.md"))
    return 0 if overall >= 60 else 1


if __name__ == "__main__":
    raise SystemExit(main())
