#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Run acceptance verifications (deterministic evidence runner)

Runs verification types:
- file
- grep
- command

Does NOT run:
- lsp (reserved for the lsp-verifier subagent, if enabled)

Writes:
- SESSION_DIR/quality/verifications_report.json
- SESSION_DIR/quality/verifications_report.md
- SESSION_DIR/quality/verification_evidence/** (per-verification JSON + logs)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import warnings

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "run_verifications.py is deprecated and will be removed in v0.5.0. "
    "Merged into quality suite. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)
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


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    status: str  # passed|failed|skipped
    details: str
    evidence: dict[str, Any]


def _load_actions(session_dir: Path) -> dict[str, Any]:
    data = load_json_safe(session_dir / "planning" / "actions.json", default={})
    return data if isinstance(data, dict) else {}


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_verification(project_root: Path, v: dict[str, Any]) -> VerificationResult:
    vtype = v.get("type")

    if vtype == "lsp":
        return VerificationResult(ok=True, status="skipped", details="delegated to lsp-verifier (not run by deterministic runner)", evidence={"type": "lsp"})

    if vtype == "file":
        p = v.get("path")
        if not isinstance(p, str) or not p.strip():
            return VerificationResult(ok=False, status="failed", details="missing verification.path", evidence={"type": "file"})
        resolved = resolve_path_under_project_root(project_root, p.strip())
        if resolved is None:
            return VerificationResult(ok=False, status="failed", details=f"invalid repo-relative path: {p!r}", evidence={"type": "file", "path": p})
        exists = resolved.exists()
        return VerificationResult(
            ok=exists,
            status="passed" if exists else "failed",
            details="exists" if exists else "missing",
            evidence={"type": "file", "path": p, "resolved": str(resolved).replace("\\", "/"), "exists": exists},
        )

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
        return VerificationResult(
            ok=found,
            status="passed" if found else "failed",
            details="matched" if found else "no match",
            evidence={"type": "grep", "path": p, "resolved": str(resolved).replace("\\", "/"), "pattern": pat, "matched": found},
        )

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
        out = (proc.stdout or "")
        ok = proc.returncode == 0 if must_succeed else proc.returncode != 0
        output_head = out[:4000]
        return VerificationResult(
            ok=ok,
            status="passed" if ok else "failed",
            details=f"exit={proc.returncode}",
            evidence={
                "type": "command",
                "command": cmd.strip(),
                "exit_code": proc.returncode,
                "must_succeed": must_succeed,
                "output_chars": len(out),
                "output_head": output_head,
                "output_truncated": len(out) > len(output_head),
            },
        )

    return VerificationResult(ok=False, status="failed", details=f"unknown verification type: {vtype!r}", evidence={"type": vtype})


def run_verifications_for_session(*, project_root: Path, session_dir: Path, require_verifications_for_code: bool) -> dict[str, Any]:
    actions = _load_actions(session_dir)
    tasks = actions.get("tasks", []) if isinstance(actions.get("tasks"), list) else []

    evidence_root = session_dir / "quality" / "verification_evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)

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

        acceptance = t.get("acceptance_criteria")
        ac_list = acceptance if isinstance(acceptance, list) else []

        ac_results: list[dict[str, Any]] = []
        any_verifications = False
        for ac in ac_list:
            if not isinstance(ac, dict):
                continue
            ac_id = ac.get("id")
            if not isinstance(ac_id, str) or not ac_id.strip():
                continue
            verifications = ac.get("verifications")
            v_list = verifications if isinstance(verifications, list) else []
            if v_list:
                any_verifications = True

            v_results: list[dict[str, Any]] = []
            ac_ok = True
            for idx, v in enumerate(v_list[:200]):
                if not isinstance(v, dict):
                    ac_ok = False
                    v_results.append({"index": idx, "status": "failed", "details": "invalid verification object"})
                    continue

                r = _run_verification(project_root, v)
                vtype = v.get("type")
                vtype_s = vtype.strip() if isinstance(vtype, str) else "unknown"

                evidence_dir = evidence_root / task_id.strip() / ac_id.strip()
                evidence_dir.mkdir(parents=True, exist_ok=True)

                evidence_rel_json = None
                if vtype_s in {"file", "grep", "command"}:
                    evidence_path = evidence_dir / f"v{idx+1:02d}_{vtype_s}.json"
                    payload = {
                        "version": 1,
                        "generated_at": utc_now(),
                        "task_id": task_id.strip(),
                        "criterion_id": ac_id.strip(),
                        "index": idx,
                        "type": vtype_s,
                        "ok": r.ok,
                        "status": r.status,
                        "details": r.details,
                        "evidence": r.evidence,
                    }
                    write_json(evidence_path, payload)
                    evidence_rel_json = str(evidence_path.relative_to(session_dir)).replace("\\", "/")

                    if vtype_s == "command":
                        log_path = evidence_dir / f"v{idx+1:02d}_command.log"
                        _write_log(
                            log_path,
                            f"$ {r.evidence.get('command','')}\n\n[{r.details} must_succeed={r.evidence.get('must_succeed')}]"
                            "\n\n--- output_head ---\n"
                            f"{r.evidence.get('output_head','')}\n"
                            + ("\n[TRUNCATED]\n" if r.evidence.get("output_truncated") else ""),
                        )
                        payload["evidence"]["log_path"] = str(log_path.relative_to(session_dir)).replace("\\", "/")
                        write_json(evidence_path, payload)

                v_results.append({"index": idx, "type": vtype_s, "status": r.status, "details": r.details, "evidence": r.evidence, "evidence_path": evidence_rel_json})
                if r.status == "failed":
                    ac_ok = False

            if not v_list:
                issues.append(
                    {
                        "task_id": task_id.strip(),
                        "criterion_id": ac_id.strip(),
                        "severity": "error" if require_verifications_for_code else "warning",
                        "message": "acceptance criterion has no verifications",
                    }
                )

            ac_results.append({"id": ac_id.strip(), "ok": ac_ok, "verifications": v_results})
            if v_list and not ac_ok:
                issues.append({"task_id": task_id.strip(), "criterion_id": ac_id.strip(), "severity": "error", "message": "acceptance verifications failed"})

        if require_verifications_for_code and not any_verifications:
            issues.append({"task_id": task_id.strip(), "severity": "error", "message": "workflow.require_verifications_for_code_tasks=true but task has no verifications"})

        task_ok = not any(not ac.get("ok") for ac in ac_results if isinstance(ac, dict) and "ok" in ac)
        task_results.append({"task_id": task_id.strip(), "owner": owner, "ok": task_ok, "acceptance": ac_results})

    ok = not any(i.get("severity") == "error" for i in issues)
    report: dict[str, Any] = {"version": 1, "generated_at": utc_now(), "ok": ok, "issues": issues, "tasks": task_results}
    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "verifications_report.json", report)

    md = ["# Verifications Report (at)", "", f"- generated_at: `{report['generated_at']}`", f"- ok: `{str(ok).lower()}`", ""]
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
    write_text(out_dir / "verifications_report.md", "\n".join(md))

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic acceptance verifications for a session (file/grep/command).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)
    workflow_cfg = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    require_verifications_for_code = bool(workflow_cfg.get("require_verifications_for_code_tasks") is True)

    report = run_verifications_for_session(project_root=project_root, session_dir=session_dir, require_verifications_for_code=require_verifications_for_code)
    print(str((session_dir / "quality" / "verifications_report.md").resolve()))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
