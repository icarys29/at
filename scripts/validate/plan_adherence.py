#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Plan adherence gate (runs declared acceptance verifications)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.path_policy import resolve_path_under_project_root  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    status: str  # passed|failed|skipped
    details: str
    evidence: dict[str, Any]


def _load_actions(session_dir: Path) -> dict[str, Any]:
    data = load_json_safe(session_dir / "planning" / "actions.json", default={})
    return data if isinstance(data, dict) else {}


def _load_task_artifact(session_dir: Path, owner: str, task_id: str) -> dict[str, Any] | None:
    path = (
        session_dir / "implementation" / "tasks" / f"{task_id}.yaml"
        if owner == "implementor"
        else session_dir / "testing" / "tasks" / f"{task_id}.yaml"
    )
    if not path.exists():
        return None
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _run_verification(project_root: Path, v: dict[str, Any]) -> VerificationResult:
    vtype = v.get("type")
    if vtype == "lsp":
        return VerificationResult(ok=True, status="skipped", details="lsp verifications are not implemented in P2", evidence={"type": "lsp"})

    if vtype == "file":
        p = v.get("path")
        if not isinstance(p, str) or not p.strip():
            return VerificationResult(ok=False, status="failed", details="missing verification.path", evidence={"type": "file"})
        resolved = resolve_path_under_project_root(project_root, p.strip())
        if resolved is None:
            return VerificationResult(ok=False, status="failed", details=f"invalid repo-relative path: {p!r}", evidence={"type": "file", "path": p})
        exists = resolved.exists()
        return VerificationResult(ok=exists, status="passed" if exists else "failed", details="exists" if exists else "missing", evidence={"type": "file", "path": p})

    if vtype == "grep":
        p = v.get("path")
        pat = v.get("pattern")
        if not isinstance(p, str) or not p.strip():
            return VerificationResult(ok=False, status="failed", details="missing verification.path", evidence={"type": "grep"})
        if not isinstance(pat, str) or not pat:
            return VerificationResult(ok=False, status="failed", details="missing verification.pattern", evidence={"type": "grep", "path": p})
        resolved = resolve_path_under_project_root(project_root, p.strip())
        if resolved is None or not resolved.exists():
            return VerificationResult(ok=False, status="failed", details=f"missing file: {p!r}", evidence={"type": "grep", "path": p, "pattern": pat})
        try:
            text = resolved.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            return VerificationResult(ok=False, status="failed", details=f"read failed: {exc}", evidence={"type": "grep", "path": p})
        try:
            found = re.search(pat, text, flags=re.MULTILINE) is not None
        except re.error as exc:
            return VerificationResult(ok=False, status="failed", details=f"invalid regex: {exc}", evidence={"type": "grep", "pattern": pat})
        return VerificationResult(ok=found, status="passed" if found else "failed", details="matched" if found else "no match", evidence={"type": "grep", "path": p, "pattern": pat})

    if vtype == "command":
        cmd = v.get("command")
        must = v.get("must_succeed")
        must_succeed = True if must is None else bool(must)
        if not isinstance(cmd, str) or not cmd.strip():
            return VerificationResult(ok=False, status="failed", details="missing verification.command", evidence={"type": "command"})
        proc = subprocess.run(
            cmd.strip(),
            cwd=str(project_root),
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        out = (proc.stdout or "")[:4000]
        ok = proc.returncode == 0 if must_succeed else proc.returncode != 0
        return VerificationResult(
            ok=ok,
            status="passed" if ok else "failed",
            details=f"exit={proc.returncode}",
            evidence={"type": "command", "command": cmd.strip(), "exit_code": proc.returncode, "output_head": out, "must_succeed": must_succeed},
        )

    return VerificationResult(ok=False, status="failed", details=f"unknown verification type: {vtype!r}", evidence={"type": vtype})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plan adherence by running declared acceptance verifications.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    actions = _load_actions(session_dir)
    tasks = actions.get("tasks", []) if isinstance(actions.get("tasks"), list) else []

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    issues: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []

    for t in tasks:
        if not isinstance(t, dict):
            continue
        task_id = t.get("id")
        owner = t.get("owner")
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        if owner not in {"implementor", "tests-builder"}:
            continue

        artifact = _load_task_artifact(session_dir, owner, task_id.strip())
        artifact_status = (artifact.get("status") if isinstance(artifact, dict) else None) if artifact else None
        if artifact is None:
            issues.append({"task_id": task_id, "severity": "error", "message": "missing task artifact"})

        acceptance = t.get("acceptance_criteria")
        ac_list = acceptance if isinstance(acceptance, list) else []

        ac_results: list[dict[str, Any]] = []
        for ac in ac_list:
            if not isinstance(ac, dict):
                continue
            ac_id = ac.get("id")
            if not isinstance(ac_id, str) or not ac_id.strip():
                continue
            verifications = ac.get("verifications")
            v_list = verifications if isinstance(verifications, list) else []
            v_results: list[dict[str, Any]] = []
            ac_ok = True
            for v in v_list:
                if not isinstance(v, dict):
                    ac_ok = False
                    v_results.append({"status": "failed", "details": "invalid verification object"})
                    continue
                r = _run_verification(project_root, v)
                v_results.append({"status": r.status, "details": r.details, "evidence": r.evidence})
                if r.status == "failed":
                    ac_ok = False
            # No verifications: treat as warning, not a hard failure.
            if not v_list:
                issues.append({"task_id": task_id, "criterion_id": ac_id, "severity": "warning", "message": "acceptance criterion has no verifications"})
            ac_results.append({"id": ac_id, "ok": ac_ok, "verifications": v_results})
            if v_list and not ac_ok:
                issues.append({"task_id": task_id, "criterion_id": ac_id, "severity": "error", "message": "acceptance verifications failed"})

        task_ok = True
        if artifact is None:
            task_ok = False
        if isinstance(artifact_status, str) and artifact_status.strip().lower() in {"failed"}:
            task_ok = False
            issues.append({"task_id": task_id, "severity": "error", "message": f"task artifact status={artifact_status!r}"})
        if any(not ac.get("ok") for ac in ac_results if isinstance(ac, dict) and "ok" in ac):
            task_ok = False

        task_results.append({"task_id": task_id, "owner": owner, "ok": task_ok, "artifact_status": artifact_status, "acceptance": ac_results})

    ok = not any(i.get("severity") == "error" for i in issues)
    report: dict[str, Any] = {"version": 1, "generated_at": utc_now(), "ok": ok, "issues": issues, "tasks": task_results}
    write_json(out_dir / "plan_adherence_report.json", report)

    md = ["# Plan Adherence Report (at)", "", f"- generated_at: `{report['generated_at']}`", f"- ok: `{str(ok).lower()}`", ""]
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            sev = it.get("severity", "")
            tid = it.get("task_id", "")
            cid = it.get("criterion_id", "")
            msg = it.get("message", "")
            tag = f"{tid}/{cid}" if cid else tid
            md.append(f"- `{sev}` `{tag}` — {msg}")
        md.append("")
    md.append("## Tasks")
    md.append("")
    for tr in task_results:
        md.append(f"- `{tr.get('task_id','')}` ({tr.get('owner','')}): `{'ok' if tr.get('ok') else 'fail'}`")
    md.append("")
    write_text(out_dir / "plan_adherence_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

