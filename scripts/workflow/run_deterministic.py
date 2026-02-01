#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Deterministic runner for non-agent phases (gates + utilities)

This script exists to make reruns/resume deterministic and testable, without
moving planning/implementation (agentic tasks) into code.

Phases are best-effort and will error if required artifacts are missing.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    script: Path
    args: list[str]


PHASE_ORDER = ["validate_plan", "task_contexts", "checkpoint", "gates", "progress"]


def _run(step: Step, *, project_root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(step.script), *step.args],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = (proc.stdout or "")[-8000:]
    return {"id": step.id, "label": step.label, "command": f"{step.script.name} {' '.join(step.args)}", "exit_code": proc.returncode, "output_tail": out}


def _steps_for_gate(session_dir: Path, gate: str) -> list[Step]:
    s = str(session_dir)
    if gate == "validate_actions":
        return [Step("validate_actions", "validate planning/actions.json", SCRIPT_ROOT / "validate" / "validate_actions.py", ["--session", s])]
    if gate == "build_task_contexts":
        return [Step("build_task_contexts", "build per-task contexts", SCRIPT_ROOT / "context" / "build_task_contexts.py", ["--session", s])]
    if gate == "checkpoint":
        return [Step("checkpoint", "create checkpoint", SCRIPT_ROOT / "checkpoint" / "create_checkpoint.py", ["--session", s])]
    if gate == "validate_task_artifacts":
        return [Step("validate_task_artifacts", "validate per-task YAML artifacts", SCRIPT_ROOT / "validate" / "validate_task_artifacts.py", ["--session", s])]
    if gate == "plan_adherence":
        return [Step("plan_adherence", "run plan adherence gate", SCRIPT_ROOT / "validate" / "plan_adherence.py", ["--session", s])]
    if gate == "parallel_conformance":
        return [Step("parallel_conformance", "run parallel conformance gate", SCRIPT_ROOT / "validate" / "parallel_conformance.py", ["--session", s])]
    if gate == "quality":
        return [Step("quality", "run quality suite", SCRIPT_ROOT / "quality" / "run_quality_suite.py", ["--session", s])]
    if gate == "docs_gate":
        return [Step("docs_gate", "run docs gate", SCRIPT_ROOT / "validate" / "docs_gate.py", ["--session", s])]
    if gate == "changed_files":
        return [Step("changed_files", "validate git changed files scope", SCRIPT_ROOT / "validate" / "validate_changed_files.py", ["--session", s])]
    if gate == "compliance":
        return [Step("compliance", "generate compliance report", SCRIPT_ROOT / "compliance" / "generate_compliance_report.py", ["--session", s, "--rerun-supporting-checks"])]
    if gate == "progress":
        return [Step("progress", "update session progress", SCRIPT_ROOT / "session" / "session_progress.py", ["--session", s])]
    raise ValueError(f"Unknown gate: {gate}")


def _steps_for_from_phase(session_dir: Path, from_phase: str) -> list[Step]:
    s = str(session_dir)
    steps: list[Step] = []
    # Note: planning + execution are agentic; phases here are deterministic helpers and gates.
    if from_phase == "validate_plan":
        steps.extend(_steps_for_gate(session_dir, "validate_actions"))
    if from_phase in {"validate_plan", "task_contexts"}:
        steps.extend(_steps_for_gate(session_dir, "build_task_contexts"))
    if from_phase in {"validate_plan", "task_contexts", "checkpoint"}:
        steps.extend(_steps_for_gate(session_dir, "checkpoint"))
    if from_phase in {"validate_plan", "task_contexts", "checkpoint", "gates"}:
        steps.extend(
            [
                *_steps_for_gate(session_dir, "validate_task_artifacts"),
                *_steps_for_gate(session_dir, "plan_adherence"),
                *_steps_for_gate(session_dir, "parallel_conformance"),
                *_steps_for_gate(session_dir, "quality"),
                *_steps_for_gate(session_dir, "docs_gate"),
                *_steps_for_gate(session_dir, "changed_files"),
                *_steps_for_gate(session_dir, "compliance"),
            ]
        )
    steps.extend(_steps_for_gate(session_dir, "progress"))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic at phases/gates for a session (rerun/resume helper).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--from-phase", default=None, choices=PHASE_ORDER, help="Run deterministic steps starting at this phase.")
    parser.add_argument("--gate", default=None, help="Run a single deterministic gate (validate_actions|build_task_contexts|checkpoint|validate_task_artifacts|plan_adherence|parallel_conformance|quality|docs_gate|changed_files|compliance|progress)")
    parser.add_argument("--continue-on-fail", action="store_true", help="Run all steps even if one fails.")
    args = parser.parse_args()

    if not args.from_phase and not args.gate:
        raise SystemExit("ERROR: provide --from-phase or --gate")

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    steps: list[Step]
    if args.gate:
        steps = _steps_for_gate(session_dir, args.gate)
    else:
        steps = _steps_for_from_phase(session_dir, args.from_phase)

    results: list[dict[str, Any]] = []
    ok = True
    for step in steps:
        r = _run(step, project_root=project_root)
        results.append(r)
        if r["exit_code"] != 0:
            ok = False
            if not args.continue_on_fail:
                break

    report = {"version": 1, "generated_at": utc_now(), "ok": ok, "session_id": session_dir.name, "steps": results}
    out_dir = session_dir / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "deterministic_run_report.json", report)

    md = ["# Deterministic Run Report (at)", "", f"- generated_at: `{report['generated_at']}`", f"- ok: `{str(ok).lower()}`", ""]
    md.append("## Steps")
    md.append("")
    for r in results:
        md.append(f"- `{r.get('id','')}`: exit=`{r.get('exit_code','')}` — {r.get('label','')}")
    md.append("")
    write_text(out_dir / "deterministic_run_report.md", "\n".join(md))

    print(str(out_dir / "deterministic_run_report.md"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
