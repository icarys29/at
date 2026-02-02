#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Track and report session progress

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.session_env import get_session_from_env  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


def _extract_compliance_decision(report_path: Path) -> str | None:
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    for pat in [
        r"(?im)^\s*(decision|status)\s*:\s*(APPROVE|REJECT)\s*$",
        r"(?im)^\s*#\s*(APPROVE|REJECT)\s*$",
    ]:
        m = re.search(pat, text)
        if m:
            return m.group(m.lastindex).upper()
    if re.search(r"\bREJECT\b", text):
        return "REJECT"
    if re.search(r"\bAPPROVE\b", text):
        return "APPROVE"
    return None


def _load_task_yaml_status(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    st = data.get("status")
    return str(st).strip().upper() if isinstance(st, str) and st.strip() else None


def _load_ok_flag(path: Path) -> bool | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    v = data.get("ok")
    return bool(v) if isinstance(v, bool) else None


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    status: str  # pending|done|partial|blocked|skipped|unknown
    details: str = ""


def _render_markdown(progress: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Session Progress (at)")
    lines.append("")
    lines.append(f"- Generated: {progress.get('generated_at','')}")
    lines.append(f"- Session: `{progress.get('session_id','')}`")
    lines.append(f"- Workflow: `{progress.get('workflow','')}`")
    lines.append(f"- Overall: `{progress.get('overall_status','')}`")
    lines.append("")

    nxt = progress.get("next", {})
    if isinstance(nxt, dict) and nxt.get("step_id"):
        lines.append("## Next")
        lines.append("")
        lines.append(f"- Step: `{nxt.get('step_id')}` — {nxt.get('summary','')}")
        missing = nxt.get("missing_task_ids", [])
        if isinstance(missing, list) and missing:
            lines.append(f"- Missing tasks: {', '.join(f'`{x}`' for x in missing[:20])}{' …' if len(missing) > 20 else ''}")
        lines.append("")

    steps = progress.get("steps", [])
    if isinstance(steps, list) and steps:
        lines.append("## Steps")
        lines.append("")
        for s in steps:
            if not isinstance(s, dict):
                continue
            sid = s.get("id", "")
            status = s.get("status", "")
            label = s.get("label", "")
            details = s.get("details", "")
            tail = f" — {details}" if isinstance(details, str) and details.strip() else ""
            lines.append(f"- `{sid}`: `{status}` — {label}{tail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize session progress and suggest the next step (best-effort, portable)")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)

    # Prefer environment-based resolution (set by orchestrator) over heuristics
    session_ctx = get_session_from_env()
    if session_ctx and not args.session:
        session_dir = session_ctx.session_dir
    else:
        session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    session_json = load_json_safe(session_dir / "session.json", default=None) or {}
    workflow = session_json.get("workflow") if isinstance(session_json.get("workflow"), str) else "deliver"

    actions = load_json_safe(session_dir / "planning" / "actions.json", default=None) or {}
    tasks_list = actions.get("tasks", []) if isinstance(actions.get("tasks"), list) else []

    def _task_ids(owner: str) -> list[str]:
        out: list[str] = []
        for t in tasks_list:
            if not isinstance(t, dict):
                continue
            if t.get("owner") != owner:
                continue
            tid = t.get("id")
            if isinstance(tid, str) and tid.strip():
                out.append(tid.strip())
        return out

    implementor_ids = _task_ids("implementor")
    tests_ids = _task_ids("tests-builder")

    steps: list[Step] = []

    request_ok = (session_dir / "inputs" / "request.md").exists()
    steps.append(Step("request", "inputs/request.md exists", "done" if request_ok else "pending"))

    context_pack_ok = (session_dir / "inputs" / "context_pack.md").exists()
    steps.append(Step("context_pack", "inputs/context_pack.md generated", "done" if context_pack_ok else "pending"))

    planning_ok = bool(actions.get("version") == 1 and isinstance(tasks_list, list) and tasks_list)
    steps.append(Step("planning", "planning/actions.json exists + version=1 + tasks[]", "done" if planning_ok else "pending"))

    tcm = load_json_safe(session_dir / "inputs" / "task_context_manifest.json", default=None)
    if not planning_ok:
        steps.append(Step("task_contexts", "inputs/task_context_manifest.json generated", "pending"))
    elif tcm is None:
        steps.append(Step("task_contexts", "inputs/task_context_manifest.json generated", "pending"))
    else:
        manifest_tasks = tcm.get("tasks") if isinstance(tcm, dict) else None
        manifest_n = len(manifest_tasks) if isinstance(manifest_tasks, dict) else 0
        code_n = len(implementor_ids) + len(tests_ids)
        status = "done" if code_n == 0 or manifest_n >= code_n else "partial"
        steps.append(Step("task_contexts", "inputs/task_context/* generated for code tasks", status, details=f"{manifest_n}/{code_n}"))

    def _artifact_summary(owner: str, task_ids: list[str]) -> tuple[int, int, int, list[str]]:
        done = 0
        blocked = 0
        missing = 0
        missing_ids: list[str] = []
        for tid in task_ids:
            artifact = (
                session_dir / "implementation" / "tasks" / f"{tid}.yaml"
                if owner == "implementor"
                else session_dir / "testing" / "tasks" / f"{tid}.yaml"
            )
            st = _load_task_yaml_status(artifact)
            if st is None:
                missing += 1
                missing_ids.append(tid)
                continue
            if st in {"DONE", "COMPLETED"}:
                done += 1
                continue
            blocked += 1
        return done, blocked, missing, missing_ids

    imp_done, imp_blocked, imp_missing, imp_missing_ids = _artifact_summary("implementor", implementor_ids)
    tst_done, tst_blocked, tst_missing, tst_missing_ids = _artifact_summary("tests-builder", tests_ids)

    total_code = len(implementor_ids) + len(tests_ids)
    total_done = imp_done + tst_done
    total_missing = imp_missing + tst_missing
    total_blocked = imp_blocked + tst_blocked

    if total_code == 0 and planning_ok:
        exec_status = "skipped"
        exec_details = "no code tasks"
    elif total_done == total_code and total_code > 0:
        exec_status = "done"
        exec_details = f"{total_done}/{total_code}"
    elif total_done == 0 and total_missing == total_code:
        exec_status = "pending"
        exec_details = f"{total_done}/{total_code}"
    else:
        exec_status = "partial"
        exec_details = f"{total_done}/{total_code}"

    steps.append(Step("execution", "task artifacts present under implementation/tasks and testing/tasks", exec_status, exec_details))

    # Checkpoint + gates (P2)
    checkpoints_dir = session_dir / "checkpoints"
    if checkpoints_dir.exists() and any(p.is_dir() for p in checkpoints_dir.iterdir()):
        steps.append(Step("checkpoint", "checkpoints/* created", "done"))
    else:
        steps.append(Step("checkpoint", "checkpoints/* created", "pending"))

    plan_ok = _load_ok_flag(session_dir / "quality" / "plan_adherence_report.json")
    if plan_ok is None:
        steps.append(Step("plan_adherence", "quality/plan_adherence_report.json present", "pending"))
    else:
        steps.append(Step("plan_adherence", "plan adherence gate", "done" if plan_ok else "blocked"))

    par_ok = _load_ok_flag(session_dir / "quality" / "parallel_conformance_report.json")
    if par_ok is None:
        steps.append(Step("parallel_conformance", "quality/parallel_conformance_report.json present", "pending"))
    else:
        steps.append(Step("parallel_conformance", "parallel conformance gate", "done" if par_ok else "blocked"))

    qual_ok = _load_ok_flag(session_dir / "quality" / "quality_report.json")
    if qual_ok is None:
        steps.append(Step("quality", "quality/quality_report.json present", "pending"))
    else:
        steps.append(Step("quality", "quality suite", "done" if qual_ok else "blocked"))

    docs_ok = _load_ok_flag(session_dir / "documentation" / "docs_gate_report.json")
    if docs_ok is None:
        steps.append(Step("docs", "documentation/docs_gate_report.json present", "pending"))
    else:
        steps.append(Step("docs", "docs gate", "done" if docs_ok else "blocked"))

    decision = _extract_compliance_decision(session_dir / "compliance" / "COMPLIANCE_VERIFICATION_REPORT.md")
    if decision is None:
        steps.append(Step("compliance", "compliance decision report present", "pending"))
    elif decision == "APPROVE":
        steps.append(Step("compliance", "compliance decision", "done", details="APPROVE"))
    else:
        steps.append(Step("compliance", "compliance decision", "blocked", details=decision))

    overall = "in_progress"
    if any(s.status == "blocked" for s in steps):
        overall = "blocked"
    elif all(s.status in {"done", "skipped"} for s in steps):
        overall = "done"

    missing_task_ids = imp_missing_ids + tst_missing_ids
    nxt = {"step_id": "", "summary": "", "missing_task_ids": missing_task_ids}
    for s in steps:
        if s.status in {"pending", "partial", "blocked"}:
            nxt = {"step_id": s.id, "summary": s.label, "missing_task_ids": missing_task_ids}
            break

    progress: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "workflow": workflow,
        "overall_status": overall,
        "next": nxt,
        "steps": [s.__dict__ for s in steps],
        "counts": {
            "tasks": {
                "implementor": len(implementor_ids),
                "tests_builder": len(tests_ids),
            },
            "task_artifacts": {
                "implementor": {"done": imp_done, "blocked": imp_blocked, "missing": imp_missing},
                "tests_builder": {"done": tst_done, "blocked": tst_blocked, "missing": tst_missing},
            },
        },
    }

    write_json(session_dir / "status" / "session_progress.json", progress)
    write_text(session_dir / "status" / "session_progress.md", _render_markdown(progress))

    print(str(session_dir / "status" / "session_progress.md"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
