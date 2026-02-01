#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Analyze audit logs and produce a stable report (JSON + Markdown)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _iter_jsonl(path: Path, *, max_lines: int = 200_000) -> Iterable[dict[str, Any]]:
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
                    yield obj
    except Exception:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze .claude/audit_logs JSONL and write a stable report.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--out", default=None, help="Output directory (default: .claude/audit_reports)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    audit_dir = (project_root / ".claude" / "audit_logs").resolve()
    out_dir = (Path(args.out).expanduser() if args.out else (project_root / ".claude" / "audit_reports")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tools = audit_dir / "tools.jsonl"
    lifecycle = audit_dir / "lifecycle.jsonl"
    subagents = audit_dir / "subagents.jsonl"

    tool_counter: Counter[str] = Counter()
    event_counter: Counter[str] = Counter()
    sessions: set[str] = set()

    for p in (tools, lifecycle, subagents):
        if not p.exists():
            continue
        for obj in _iter_jsonl(p):
            ev = obj.get("event")
            if isinstance(ev, str) and ev:
                event_counter[ev] += 1
            sid = obj.get("session_id")
            if isinstance(sid, str) and sid.strip():
                sessions.add(sid.strip())
            tn = obj.get("tool_name")
            if isinstance(tn, str) and tn.strip():
                tool_counter[tn.strip()] += 1

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "audit_dir": str(audit_dir).replace("\\", "/"),
        "events": dict(event_counter),
        "top_tools": tool_counter.most_common(20),
        "sessions_observed": len(sessions),
        "notes": [
            "Audit logs are opt-in via /at:setup-audit-hooks.",
            "Traces are off by default (enable with AT_AUDIT_TRACES_ENABLED=1).",
        ],
    }

    write_json(out_dir / "audit_report.json", report)
    md = [
        "# Audit Report (at)",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- sessions_observed: `{report['sessions_observed']}`",
        "",
        "## Events",
        "",
    ]
    for k, v in sorted(event_counter.items()):
        md.append(f"- `{k}`: `{v}`")
    md.append("")
    md.append("## Top tools")
    md.append("")
    for name, cnt in tool_counter.most_common(20):
        md.append(f"- `{name}`: `{cnt}`")
    md.append("")
    write_text(out_dir / "audit_report.md", "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

