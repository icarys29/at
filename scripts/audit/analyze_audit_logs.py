#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Analyze audit logs and produce a stable report (JSON + Markdown)

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
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


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    p = min(max(p, 0.0), 1.0)
    xs = sorted(values)
    idx = int(round((len(xs) - 1) * p))
    return xs[idx]


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

    # Latency (best-effort from PreToolUse→PostToolUse ts deltas).
    inflight: dict[str, list[dict[str, Any]]] = defaultdict(list)  # session_id -> stack
    durations_ms_by_tool: dict[str, list[float]] = defaultdict(list)
    unmatched_posts = 0

    # Failures (best-effort; depends on what the hook records).
    exit_code_counter: Counter[str] = Counter()  # "tool:exit_code"
    error_counter: Counter[str] = Counter()

    for p in (tools, lifecycle, subagents):
        if not p.exists():
            continue
        for obj in _iter_jsonl(p):
            ev = obj.get("event")
            if isinstance(ev, str) and ev:
                event_counter[ev] += 1
            sid = obj.get("session_id")
            sid_s = sid.strip() if isinstance(sid, str) else ""
            if sid_s:
                sessions.add(sid_s)
            tn = obj.get("tool_name")
            tn_s = tn.strip() if isinstance(tn, str) else ""
            if tn_s:
                tool_counter[tn_s] += 1

            # tools.jsonl-only metrics
            if p != tools:
                continue
            if not (sid_s and tn_s):
                continue
            ts = _parse_ts(obj.get("ts"))
            tool_call_id = obj.get("tool_call_id")
            call_id = tool_call_id.strip() if isinstance(tool_call_id, str) else None

            if ev == "PreToolUse":
                inflight[sid_s].append({"tool_name": tn_s, "ts": ts, "tool_call_id": call_id})
                continue

            if ev == "PostToolUse":
                stack = inflight.get(sid_s) or []
                match_i = None
                # Prefer matching by tool_call_id when present.
                if call_id:
                    for i in range(len(stack) - 1, -1, -1):
                        if stack[i].get("tool_call_id") == call_id:
                            match_i = i
                            break
                # Fallback: match by tool_name (LIFO).
                if match_i is None:
                    for i in range(len(stack) - 1, -1, -1):
                        if stack[i].get("tool_name") == tn_s:
                            match_i = i
                            break

                if match_i is None:
                    unmatched_posts += 1
                else:
                    started = stack.pop(match_i)
                    t0 = started.get("ts")
                    if isinstance(t0, datetime) and isinstance(ts, datetime):
                        dur_ms = (ts - t0).total_seconds() * 1000.0
                        if dur_ms >= 0:
                            xs = durations_ms_by_tool[tn_s]
                            if len(xs) < 5000:
                                xs.append(dur_ms)

                # Failure extraction (best-effort).
                result = obj.get("result")
                if isinstance(result, dict):
                    ec = result.get("exit_code")
                    if isinstance(ec, int) and ec != 0:
                        exit_code_counter[f"{tn_s}:{ec}"] += 1
                    err = result.get("error")
                    if isinstance(err, str) and err.strip():
                        error_counter[err.strip()[:200]] += 1

    latency_summary: list[dict[str, Any]] = []
    for tool, xs in durations_ms_by_tool.items():
        if not xs:
            continue
        latency_summary.append(
            {
                "tool_name": tool,
                "count": len(xs),
                "avg_ms": round(sum(xs) / len(xs), 2),
                "p50_ms": _percentile(xs, 0.50),
                "p95_ms": _percentile(xs, 0.95),
                "max_ms": round(max(xs), 2),
            }
        )
    latency_summary.sort(key=lambda it: (-int(it.get("count", 0)), str(it.get("tool_name", ""))))

    top_exit_codes: list[tuple[str, int]] = exit_code_counter.most_common(20)
    top_errors: list[tuple[str, int]] = error_counter.most_common(20)

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "audit_dir": str(audit_dir).replace("\\", "/"),
        "events": dict(event_counter),
        "top_tools": tool_counter.most_common(20),
        "latency": {
            "paired_samples": sum(int(it.get("count", 0)) for it in latency_summary),
            "unmatched_posts": unmatched_posts,
            "by_tool": latency_summary[:50],
        },
        "top_failures": {
            "exit_codes": [{"key": k, "count": v} for k, v in top_exit_codes],
            "errors": [{"error": k, "count": v} for k, v in top_errors],
        },
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

    md.append("## Latency (best-effort)")
    md.append("")
    md.append(f"- paired_samples: `{report['latency']['paired_samples']}`")
    md.append(f"- unmatched_posts: `{report['latency']['unmatched_posts']}`")
    md.append("")
    for it in latency_summary[:20]:
        md.append(
            f"- `{it.get('tool_name','')}`: n=`{it.get('count','')}` avg_ms=`{it.get('avg_ms','')}` "
            f"p50_ms=`{it.get('p50_ms','')}` p95_ms=`{it.get('p95_ms','')}` max_ms=`{it.get('max_ms','')}`"
        )
    md.append("")

    if top_exit_codes or top_errors:
        md.append("## Top failures (best-effort)")
        md.append("")
        for k, v in top_exit_codes[:12]:
            md.append(f"- `{k}`: `{v}`")
        for k, v in top_errors[:12]:
            md.append(f"- error: {k} ({v})")
        md.append("")

    write_text(out_dir / "audit_report.md", "\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
