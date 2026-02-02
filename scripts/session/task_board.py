#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate a deterministic session task board (actions + artifacts)

This is a session-backed analogue to Claude Code's task list / TodoWrite:
- source of truth remains SESSION_DIR artifacts (planning/actions.json + reports)
- outputs are deterministic JSON + Markdown for fast operator scanning

The board is designed to help with parallel execution:
- shows parallel_execution groups in execution_order
- shows per-task status from task artifacts (completed/partial/failed/missing)
- shows gate statuses from deterministic reports

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.session_env import get_session_from_env  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402



CODE_OWNERS = {"implementor", "tests-builder"}


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


def _load_task_artifact_status(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    st = data.get("status")
    return str(st).strip().lower() if isinstance(st, str) and st.strip() else None


def _artifact_path_for_task(session_dir: Path, *, owner: str, task_id: str) -> Path | None:
    if owner == "implementor":
        return session_dir / "implementation" / "tasks" / f"{task_id}.yaml"
    if owner == "tests-builder":
        return session_dir / "testing" / "tasks" / f"{task_id}.yaml"
    return None


def _normalize_task_state(status: str | None, *, artifact_exists: bool) -> str:
    # States are intentionally minimal (portable + deterministic).
    if not artifact_exists:
        return "pending"
    if status in {"completed", "done"}:
        return "done"
    if status == "partial":
        return "in_progress"
    if status == "failed":
        return "blocked"
    return "unknown"


def _group_state(task_states: list[str]) -> str:
    if not task_states:
        return "pending"
    if any(s == "blocked" for s in task_states):
        return "blocked"
    if all(s == "done" for s in task_states):
        return "done"
    if any(s in {"done", "in_progress", "unknown"} for s in task_states):
        return "in_progress"
    return "pending"


def _load_ok_flag(path: Path) -> bool | None:
    obj = load_json_safe(path, default=None)
    if not isinstance(obj, dict):
        return None
    v = obj.get("ok")
    return bool(v) if isinstance(v, bool) else None


@dataclass(frozen=True)
class BoardTask:
    id: str
    owner: str
    summary: str
    state: str  # pending|in_progress|done|blocked|unknown
    artifact: str | None
    doc_ids: list[str]


def _render_md(board: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Task Board (at)")
    lines.append("")
    lines.append(f"- generated_at: `{board.get('generated_at','')}`")
    lines.append(f"- session_id: `{board.get('session_id','')}`")
    lines.append(f"- workflow: `{board.get('workflow','')}`")
    lines.append("")

    summary = board.get("summary")
    if isinstance(summary, dict):
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- tasks_total: `{summary.get('tasks_total','')}`")
        lines.append(f"- tasks_done: `{summary.get('tasks_done','')}`")
        lines.append(f"- tasks_blocked: `{summary.get('tasks_blocked','')}`")
        lines.append(f"- tasks_in_progress: `{summary.get('tasks_in_progress','')}`")
        lines.append(f"- tasks_pending: `{summary.get('tasks_pending','')}`")
        lines.append("")

    groups = board.get("parallel_groups")
    if isinstance(groups, list) and groups:
        lines.append("## Parallel Groups")
        lines.append("")
        for g in groups[:200]:
            if not isinstance(g, dict):
                continue
            gid = g.get("group_id", "")
            st = g.get("state", "")
            order = g.get("execution_order", "")
            lines.append(f"### {gid}")
            lines.append("")
            lines.append(f"- state: `{st}`")
            lines.append(f"- execution_order: `{order}`")
            deps = g.get("depends_on_groups")
            if isinstance(deps, list) and deps:
                lines.append("- depends_on_groups: " + ", ".join([f"`{d}`" for d in deps[:30] if isinstance(d, str)]))
            lines.append("")
            tasks = g.get("tasks")
            if isinstance(tasks, list) and tasks:
                lines.append("| Task | Owner | State | Summary |")
                lines.append("|---|---|---|---|")
                for t in tasks[:200]:
                    if not isinstance(t, dict):
                        continue
                    lines.append(f"| `{t.get('id','')}` | {t.get('owner','')} | `{t.get('state','')}` | {t.get('summary','')} |")
                lines.append("")

    ungrouped = board.get("ungrouped_tasks")
    if isinstance(ungrouped, list) and ungrouped:
        lines.append("## Ungrouped Tasks")
        lines.append("")
        lines.append("| Task | Owner | State | Summary |")
        lines.append("|---|---|---|---|")
        for t in ungrouped[:400]:
            if not isinstance(t, dict):
                continue
            lines.append(f"| `{t.get('id','')}` | {t.get('owner','')} | `{t.get('state','')}` | {t.get('summary','')} |")
        lines.append("")

    gates = board.get("gates")
    if isinstance(gates, dict) and gates:
        lines.append("## Gates")
        lines.append("")
        for key in [
            "task_artifacts",
            "plan_adherence",
            "parallel_conformance",
            "quality_suite",
            "docs_gate",
            "changed_files",
            "compliance",
        ]:
            g = gates.get(key)
            if not isinstance(g, dict):
                continue
            st = g.get("state", "")
            details = g.get("details", "")
            tail = f" — {details}" if isinstance(details, str) and details.strip() else ""
            lines.append(f"- `{key}`: `{st}`{tail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic task board for a session.")
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

    session_json = load_json_safe(session_dir / "session.json", default={})
    workflow = session_json.get("workflow") if isinstance(session_json.get("workflow"), str) else "deliver"

    actions = load_json_safe(session_dir / "planning" / "actions.json", default={})
    actions = actions if isinstance(actions, dict) else {}
    tasks = actions.get("tasks") if isinstance(actions.get("tasks"), list) else []

    # Build per-task status.
    tasks_by_id: dict[str, BoardTask] = {}
    for t in tasks[:8000]:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        owner = t.get("owner")
        if not isinstance(tid, str) or not tid.strip():
            continue
        if not isinstance(owner, str) or not owner.strip():
            continue
        summary = t.get("summary") if isinstance(t.get("summary"), str) else ""
        doc_ids: list[str] = []
        ctx = t.get("context")
        if isinstance(ctx, dict):
            d = ctx.get("doc_ids")
            if isinstance(d, list):
                doc_ids = [str(x).strip() for x in d if isinstance(x, str) and str(x).strip()][:30]

        artifact_path = _artifact_path_for_task(session_dir, owner=owner, task_id=tid.strip())
        status = _load_task_artifact_status(artifact_path) if artifact_path else None
        state = _normalize_task_state(status, artifact_exists=bool(artifact_path and artifact_path.exists())) if owner in CODE_OWNERS else "planned"

        tasks_by_id[tid.strip()] = BoardTask(
            id=tid.strip(),
            owner=owner.strip(),
            summary=summary.strip(),
            state=state,
            artifact=str(artifact_path.relative_to(session_dir)) if artifact_path else None,
            doc_ids=doc_ids,
        )

    # Parallel groups (preserve deterministic order by execution_order then group_id).
    par = actions.get("parallel_execution") if isinstance(actions.get("parallel_execution"), dict) else {}
    enabled = bool(par.get("enabled")) if isinstance(par.get("enabled"), bool) else False
    groups_raw = par.get("groups") if isinstance(par.get("groups"), list) else []

    groups: list[dict[str, Any]] = []
    grouped_task_ids: set[str] = set()
    if enabled and groups_raw:
        for g in groups_raw[:2000]:
            if not isinstance(g, dict):
                continue
            gid = g.get("group_id")
            if not isinstance(gid, str) or not gid.strip():
                continue
            order = g.get("execution_order")
            order_i = int(order) if isinstance(order, int) else 0
            dep_groups = g.get("depends_on_groups") if isinstance(g.get("depends_on_groups"), list) else []
            dep_groups_s = [str(x).strip() for x in dep_groups if isinstance(x, str) and str(x).strip()][:50]
            task_ids = g.get("tasks") if isinstance(g.get("tasks"), list) else []
            task_ids_s = [str(x).strip() for x in task_ids if isinstance(x, str) and str(x).strip()]

            items: list[dict[str, Any]] = []
            states: list[str] = []
            for tid in task_ids_s:
                bt = tasks_by_id.get(tid)
                if bt is None:
                    continue
                grouped_task_ids.add(tid)
                items.append({"id": bt.id, "owner": bt.owner, "state": bt.state, "summary": bt.summary})
                if bt.owner in CODE_OWNERS:
                    states.append(bt.state)

            groups.append(
                {
                    "group_id": gid.strip(),
                    "execution_order": order_i,
                    "depends_on_groups": dep_groups_s,
                    "state": _group_state(states),
                    "tasks": items,
                }
            )

        groups.sort(key=lambda x: (int(x.get("execution_order") or 0), str(x.get("group_id") or "")))

    ungrouped_tasks: list[dict[str, Any]] = []
    for tid, bt in tasks_by_id.items():
        if bt.owner not in CODE_OWNERS:
            continue
        if tid in grouped_task_ids:
            continue
        ungrouped_tasks.append({"id": bt.id, "owner": bt.owner, "state": bt.state, "summary": bt.summary})
    ungrouped_tasks.sort(key=lambda x: str(x.get("id") or ""))

    # Gate statuses from deterministic reports.
    gates: dict[str, Any] = {}
    qa_dir = session_dir / "quality"
    doc_dir = session_dir / "documentation"
    comp_dir = session_dir / "compliance"

    def _gate_from_ok(ok: bool | None) -> str:
        if ok is None:
            return "pending"
        return "done" if ok else "blocked"

    gates["task_artifacts"] = {"state": _gate_from_ok(_load_ok_flag(qa_dir / "task_artifacts_report.json")), "details": ""}
    gates["plan_adherence"] = {"state": _gate_from_ok(_load_ok_flag(qa_dir / "plan_adherence_report.json")), "details": ""}
    gates["parallel_conformance"] = {"state": _gate_from_ok(_load_ok_flag(qa_dir / "parallel_conformance_report.json")), "details": ""}
    gates["quality_suite"] = {"state": _gate_from_ok(_load_ok_flag(qa_dir / "quality_report.json")), "details": ""}
    gates["docs_gate"] = {"state": _gate_from_ok(_load_ok_flag(doc_dir / "docs_gate_report.json")), "details": ""}
    gates["changed_files"] = {"state": _gate_from_ok(_load_ok_flag(qa_dir / "changed_files_report.json")), "details": ""}

    decision = _extract_compliance_decision(comp_dir / "COMPLIANCE_VERIFICATION_REPORT.md")
    if decision is None:
        gates["compliance"] = {"state": "pending", "details": ""}
    elif decision == "APPROVE":
        gates["compliance"] = {"state": "done", "details": "APPROVE"}
    else:
        gates["compliance"] = {"state": "blocked", "details": decision}

    # Summary counts (code tasks only).
    code_tasks = [t for t in tasks_by_id.values() if t.owner in CODE_OWNERS]
    counts = {
        "tasks_total": len(code_tasks),
        "tasks_done": len([t for t in code_tasks if t.state == "done"]),
        "tasks_blocked": len([t for t in code_tasks if t.state == "blocked"]),
        "tasks_in_progress": len([t for t in code_tasks if t.state == "in_progress"]),
        "tasks_pending": len([t for t in code_tasks if t.state == "pending"]),
    }

    payload: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "workflow": workflow,
        "parallel_execution": {"enabled": enabled},
        "parallel_groups": groups,
        "ungrouped_tasks": ungrouped_tasks,
        "gates": gates,
        "summary": counts,
    }

    out_dir = session_dir / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "task_board.json", payload)
    write_text(out_dir / "task_board.md", _render_md(payload))
    print(str(out_dir / "task_board.md"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
