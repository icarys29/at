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
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from validate.run_verifications import run_verifications_for_session  # noqa: E402


def _load_lsp_results(session_dir: Path) -> tuple[dict[tuple[str, str, int], dict[str, Any]], str | None]:
    """
    Load lsp-verifier output (if present).

    Expected shape:
      {
        "version": 1,
        "results": [
          {"task_id": "...", "criterion_id": "...", "index": 0, "status": "passed|failed|skipped", "details": "..."}
        ]
      }
    """
    path = session_dir / "quality" / "lsp_verifications.json"
    if not path.exists():
        return {}, "missing lsp_verifications.json"
    data = load_json_safe(path, default=None)
    if not isinstance(data, dict):
        return {}, "invalid lsp_verifications.json (not an object)"
    raw = data.get("results")
    if not isinstance(raw, list):
        return {}, "invalid lsp_verifications.json (missing results[])"

    out: dict[tuple[str, str, int], dict[str, Any]] = {}
    for it in raw[:5000]:
        if not isinstance(it, dict):
            continue
        tid = it.get("task_id")
        cid = it.get("criterion_id")
        idx = it.get("index")
        if not isinstance(tid, str) or not tid.strip():
            continue
        if not isinstance(cid, str) or not cid.strip():
            continue
        if not isinstance(idx, int) or idx < 0:
            continue
        out[(tid.strip(), cid.strip(), idx)] = it
    return out, None


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
    workflow_cfg = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    require_verifications_for_code = bool(workflow_cfg.get("require_verifications_for_code_tasks") is True)

    lsp_cfg = config.get("lsp") if isinstance(config.get("lsp"), dict) else {}
    lsp_enabled = bool(lsp_cfg.get("enabled") is True)
    lsp_mode = lsp_cfg.get("mode") if isinstance(lsp_cfg.get("mode"), str) else "skip"
    if lsp_mode not in {"fail", "warn", "skip"}:
        lsp_mode = "skip"

    base = run_verifications_for_session(project_root=project_root, session_dir=session_dir, require_verifications_for_code=require_verifications_for_code)

    issues = base.get("issues") if isinstance(base.get("issues"), list) else []
    tasks = base.get("tasks") if isinstance(base.get("tasks"), list) else []

    lsp_results_map: dict[tuple[str, str, int], dict[str, Any]]
    lsp_err: str | None
    lsp_results_map, lsp_err = _load_lsp_results(session_dir)

    # Apply LSP policy to any lsp verifications present in the report.
    seen_lsp = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        task_id = t.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        acceptance = t.get("acceptance")
        if not isinstance(acceptance, list):
            continue
        for ac in acceptance:
            if not isinstance(ac, dict):
                continue
            ac_id = ac.get("id")
            if not isinstance(ac_id, str) or not ac_id.strip():
                continue
            verifs = ac.get("verifications")
            if not isinstance(verifs, list):
                continue
            for v in verifs:
                if not isinstance(v, dict):
                    continue
                if v.get("type") != "lsp":
                    continue
                idx = v.get("index")
                if not isinstance(idx, int) or idx < 0:
                    continue
                seen_lsp += 1

                if not lsp_enabled:
                    v["status"] = "failed"
                    v["details"] = "lsp.enabled=false (remove lsp verifications or enable LSP)"
                    v["evidence"] = {"type": "lsp", "enabled": False}
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "error",
                            "message": "lsp verification present but lsp.enabled=false",
                        }
                    )
                    continue

                if lsp_mode == "skip":
                    v["status"] = "skipped"
                    v["details"] = "lsp.mode=skip (LSP checks are not required)"
                    v["evidence"] = {"type": "lsp", "enabled": True, "mode": "skip"}
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "warning",
                            "message": "lsp verification skipped (mode=skip)",
                        }
                    )
                    continue

                if lsp_err:
                    v["status"] = "failed" if lsp_mode == "fail" else "warn"
                    v["details"] = f"{lsp_err} (run lsp-verifier)"
                    v["evidence"] = {"type": "lsp", "enabled": True, "mode": lsp_mode}
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "error" if lsp_mode == "fail" else "warning",
                            "message": f"lsp verification blocked: {lsp_err}",
                        }
                    )
                    continue

                key = (task_id.strip(), ac_id.strip(), idx)
                r = lsp_results_map.get(key)
                if not isinstance(r, dict):
                    v["status"] = "failed" if lsp_mode == "fail" else "warn"
                    v["details"] = "missing lsp-verifier result for this verification"
                    v["evidence"] = {"type": "lsp", "enabled": True, "mode": lsp_mode, "key": {"task_id": key[0], "criterion_id": key[1], "index": key[2]}}
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "error" if lsp_mode == "fail" else "warning",
                            "message": "missing lsp-verifier result for this verification",
                        }
                    )
                    continue

                st = r.get("status")
                details = r.get("details")
                if not isinstance(st, str):
                    st = "failed"
                if not isinstance(details, str):
                    details = ""
                st = st.strip().lower()
                if st not in {"passed", "failed", "skipped"}:
                    st = "failed"

                if st == "failed" and lsp_mode == "warn":
                    v["status"] = "warn"
                    v["details"] = details or "lsp failed (mode=warn)"
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "warning",
                            "message": "lsp verification failed (mode=warn)",
                        }
                    )
                elif st == "skipped" and lsp_mode in {"fail", "warn"}:
                    v["status"] = "warn"
                    v["details"] = details or "lsp skipped (mode requires evidence)"
                    issues.append(
                        {
                            "task_id": task_id.strip(),
                            "criterion_id": ac_id.strip(),
                            "severity": "warning" if lsp_mode == "warn" else "error",
                            "message": "lsp verification skipped (mode requires evidence)",
                        }
                    )
                else:
                    v["status"] = st
                    v["details"] = details or ("lsp passed" if st == "passed" else "lsp failed")

    # Recompute acceptance/task ok after LSP policy adjustments.
    for t in tasks:
        if not isinstance(t, dict):
            continue
        acceptance = t.get("acceptance")
        if not isinstance(acceptance, list):
            continue
        task_ok = True
        for ac in acceptance:
            if not isinstance(ac, dict):
                continue
            verifs = ac.get("verifications")
            if not isinstance(verifs, list):
                continue
            ac_ok = True
            for v in verifs:
                if isinstance(v, dict) and v.get("status") == "failed":
                    ac_ok = False
            ac["ok"] = ac_ok
            if not ac_ok:
                task_ok = False
        t["ok"] = task_ok

    ok = not any(i.get("severity") == "error" for i in issues if isinstance(i, dict))
    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "issues": issues,
        "tasks": tasks,
        "lsp": {"enabled": lsp_enabled, "mode": lsp_mode, "lsp_verifications_expected": seen_lsp},
    }

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "plan_adherence_report.json", report)

    md = ["# Plan Adherence Report (at)", "", f"- generated_at: `{report['generated_at']}`", f"- ok: `{str(ok).lower()}`", ""]
    if report.get("lsp_verifications_expected"):
        md.append("## LSP")
        md.append("")
        md.append(f"- enabled: `{str(lsp_enabled).lower()}`")
        md.append(f"- mode: `{lsp_mode}`")
        md.append("")
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            if not isinstance(it, dict):
                continue
            sev = it.get("severity", "")
            tid = it.get("task_id", "")
            cid = it.get("criterion_id", "")
            msg = it.get("message", "")
            tag = f"{tid}/{cid}" if cid else tid
            md.append(f"- `{sev}` `{tag}` — {msg}")
        md.append("")
    md.append("## Tasks")
    md.append("")
    for tr in tasks:
        if not isinstance(tr, dict):
            continue
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
