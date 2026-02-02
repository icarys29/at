#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: E2E gate (enforce end-to-end verification policy)

Reads:
- `.claude/project.yaml` (workflow.e2e_mode)
- `.claude/at/e2e.json` (enabled + id)
- `SESSION_DIR/quality/quality_report.json` (command results)

Writes:
- `SESSION_DIR/quality/e2e_gate_report.{json,md}`

Policy:
- workflow.e2e_mode=off: always ok.
- workflow.e2e_mode=optional: ok if E2E passed or skipped (warn if missing).
- workflow.e2e_mode=required: fail if E2E is missing, skipped, or failed.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "e2e_gate.py is deprecated and will be removed in v0.5.0. "
    "E2E checking will be merged into quality suite. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402





def _load_e2e_cfg(project_root: Path) -> dict[str, Any] | None:
    p = (project_root / ".claude" / "at" / "e2e.json").resolve()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("version") == 1 else None


def _mode(config: dict[str, Any]) -> str:
    wf = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    m = wf.get("e2e_mode")
    if isinstance(m, str) and m.strip().lower() in {"off", "optional", "required"}:
        return m.strip().lower()
    return "optional"


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce E2E gate policy for a session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    out_dir = session_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    mode = _mode(config)
    e2e_cfg = _load_e2e_cfg(project_root) or {}
    enabled = e2e_cfg.get("enabled") is True
    e2e_id = e2e_cfg.get("id") if isinstance(e2e_cfg.get("id"), str) and e2e_cfg.get("id").strip() else "e2e"

    issues: list[dict[str, Any]] = []
    status = "skipped"
    ok = True

    if mode == "off":
        status = "skipped"
        ok = True
    else:
        if not enabled:
            status = "missing"
            if mode == "required":
                ok = False
                issues.append({"severity": "error", "message": "E2E is required but .claude/at/e2e.json is missing or enabled=false"})
            else:
                ok = True
                issues.append({"severity": "warning", "message": "E2E not enabled (optional). Configure via /at:setup-e2e and set .claude/at/e2e.json enabled=true"})
        else:
            report = load_json_safe(out_dir / "quality_report.json", default={})
            report = report if isinstance(report, dict) else {}
            results = report.get("results") if isinstance(report.get("results"), list) else []
            found = None
            for r in results:
                if isinstance(r, dict) and r.get("id") == e2e_id:
                    found = r
                    break
            if found is None:
                status = "missing"
                ok = mode != "required"
                issues.append({"severity": "error" if mode == "required" else "warning", "message": f"E2E result not found in quality_report.json (expected id={e2e_id!r})"})
            else:
                st = found.get("status")
                status = str(st) if isinstance(st, str) and st else "unknown"
                if status == "passed":
                    ok = True
                elif status == "skipped":
                    ok = mode != "required"
                    issues.append({"severity": "error" if mode == "required" else "warning", "message": f"E2E skipped: {found.get('reason','')}"})
                else:
                    ok = False
                    issues.append({"severity": "error", "message": f"E2E failed (see quality log): {found.get('log_path','')}"})

    payload = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "mode": mode,
        "e2e_enabled": bool(enabled),
        "e2e_id": e2e_id,
        "status": status,
        "issues": issues,
    }
    write_json(out_dir / "e2e_gate_report.json", payload)

    md: list[str] = []
    md.append("# E2E Gate Report (at)")
    md.append("")
    md.append(f"- generated_at: `{payload['generated_at']}`")
    md.append(f"- ok: `{str(ok).lower()}`")
    md.append(f"- mode: `{mode}`")
    md.append(f"- status: `{status}`")
    md.append("")
    if issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:50]:
            md.append(f"- `{it.get('severity','')}` — {it.get('message','')}")
        md.append("")
    write_text(out_dir / "e2e_gate_report.md", "\n".join(md))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
