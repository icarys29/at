#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Roll up KPIs across sessions (best-effort)

Writes:
- <sessions_dir>/telemetry_rollup.{json,md}

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate telemetry/session_kpis.json across sessions.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--limit", type=int, default=200, help="Max sessions to scan (newest first).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    root = (project_root / sessions_dir).resolve()
    if not root.exists():
        print("No sessions dir.", file=sys.stderr)
        return 1

    session_dirs = [p for p in sorted(root.iterdir(), reverse=True) if p.is_dir() and (p / "session.json").exists()]
    session_dirs = session_dirs[: max(0, args.limit)]

    overall = Counter()
    gate_counts = Counter()
    scanned = 0
    for sd in session_dirs:
        kpi_path = sd / "telemetry" / "session_kpis.json"
        if not kpi_path.exists():
            continue
        data = load_json_safe(kpi_path, default=None)
        if not isinstance(data, dict):
            continue
        scanned += 1
        st = data.get("overall_status")
        if isinstance(st, str) and st:
            overall[st] += 1
        gates = data.get("gates")
        if isinstance(gates, dict):
            for k, v in gates.items():
                if v is True:
                    gate_counts[f"{k}:true"] += 1
                elif v is False:
                    gate_counts[f"{k}:false"] += 1

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "sessions_scanned": scanned,
        "overall_status_counts": dict(overall),
        "gate_counts": dict(gate_counts),
    }

    out_json = root / "telemetry_rollup.json"
    out_md = root / "telemetry_rollup.md"
    write_json(out_json, report)

    md = ["# Telemetry Rollup (at)", "", f"- generated_at: `{report['generated_at']}`", f"- sessions_scanned: `{scanned}`", "", "## Overall", ""]
    for k, v in sorted(overall.items()):
        md.append(f"- `{k}`: `{v}`")
    md.append("")
    md.append("## Gates")
    md.append("")
    for k, v in sorted(gate_counts.items()):
        md.append(f"- `{k}`: `{v}`")
    md.append("")
    write_text(out_md, "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
