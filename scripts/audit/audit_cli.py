#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Audit CLI (interactive inspection of .claude/audit_logs)

This is intentionally low-sensitivity by default:
- It summarizes counts, timings, and failures.
- It only shows raw tool inputs/outputs when trace capture is enabled and the
  user explicitly requests trace detail.

Version: 0.4.0
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


def _audit_dir(project_root: Path) -> Path:
    return (project_root / ".claude" / "audit_logs").resolve()


def cmd_list(project_root: Path) -> int:
    audit_dir = _audit_dir(project_root)
    if not audit_dir.exists():
        print(f"FAIL: audit logs not found at {audit_dir}", file=sys.stderr)
        print("Hint: install audit hooks with /at:setup-audit-hooks", file=sys.stderr)
        return 2

    files = [
        audit_dir / "tools.jsonl",
        audit_dir / "lifecycle.jsonl",
        audit_dir / "subagents.jsonl",
    ]

    print(f"audit_dir: {audit_dir}")
    for p in files:
        if not p.exists():
            print(f"- {p.name}: MISSING")
            continue
        try:
            size = p.stat().st_size
        except Exception:
            size = -1
        try:
            lines = sum(1 for _ in open(p, "rb"))
        except Exception:
            lines = -1
        size_s = "?" if size < 0 else (f"{size/1024:.1f}KB" if size < 1024 * 1024 else f"{size/1024/1024:.2f}MB")
        lines_s = "?" if lines < 0 else str(lines)
        print(f"- {p.name}: lines={lines_s} size={size_s}")
    return 0


def _load_tools(project_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    audit_dir = _audit_dir(project_root)
    tools = audit_dir / "tools.jsonl"
    return tools, list(_iter_jsonl(tools))


def _load_lifecycle(project_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    audit_dir = _audit_dir(project_root)
    lifecycle = audit_dir / "lifecycle.jsonl"
    return lifecycle, list(_iter_jsonl(lifecycle))


def cmd_sessions(project_root: Path) -> int:
    lifecycle_path, rows = _load_lifecycle(project_root)
    if not lifecycle_path.exists():
        print(f"FAIL: {lifecycle_path} not found (install audit hooks with /at:setup-audit-hooks)", file=sys.stderr)
        return 2

    starts: dict[str, datetime] = {}
    ends: dict[str, datetime] = {}
    for r in rows:
        sid = r.get("session_id")
        if not isinstance(sid, str) or not sid.strip():
            continue
        ev = r.get("event")
        ts = _parse_ts(r.get("ts"))
        if not isinstance(ev, str) or ts is None:
            continue
        if ev == "SessionStart":
            prev = starts.get(sid)
            if prev is None or ts < prev:
                starts[sid] = ts
        elif ev == "SessionEnd":
            prev = ends.get(sid)
            if prev is None or ts > prev:
                ends[sid] = ts

    if not starts and not ends:
        print("No session lifecycle events found.")
        return 0

    # Print newest-first.
    sessions = sorted(set(starts) | set(ends), key=lambda s: (starts.get(s) or ends.get(s) or datetime.min), reverse=True)
    for sid in sessions[:60]:
        st = starts.get(sid)
        en = ends.get(sid)
        dur_s = None
        if st and en:
            dur_s = (en - st).total_seconds()
        dur_txt = "-" if dur_s is None else (f"{dur_s:.1f}s" if dur_s < 60 else f"{dur_s/60:.1f}m")
        print(f"- {sid} start={st.isoformat(timespec='seconds') if st else '-'} end={en.isoformat(timespec='seconds') if en else '-'} dur={dur_txt}")
    if len(sessions) > 60:
        print(f"... ({len(sessions) - 60} more)")
    return 0


def cmd_tools(project_root: Path, *, session_id: str | None) -> int:
    tools_path, rows = _load_tools(project_root)
    if not tools_path.exists():
        print(f"FAIL: {tools_path} not found (install audit hooks with /at:setup-audit-hooks)", file=sys.stderr)
        return 2

    c: Counter[str] = Counter()
    events: Counter[str] = Counter()
    for r in rows:
        sid = r.get("session_id")
        if session_id and (not isinstance(sid, str) or sid.strip() != session_id):
            continue
        tn = r.get("tool_name")
        if isinstance(tn, str) and tn.strip():
            c[tn.strip()] += 1
        ev = r.get("event")
        if isinstance(ev, str) and ev.strip():
            events[ev.strip()] += 1

    if not c and not events:
        print("No tool events found.")
        return 0

    if session_id:
        print(f"session_id: {session_id}")
    print("events:")
    for k, v in sorted(events.items()):
        print(f"- {k}: {v}")
    print("")
    print("top_tools:")
    for name, cnt in c.most_common(30):
        print(f"- {name}: {cnt}")
    return 0


def cmd_timing(project_root: Path, *, session_id: str | None) -> int:
    tools_path, rows = _load_tools(project_root)
    if not tools_path.exists():
        print(f"FAIL: {tools_path} not found (install audit hooks with /at:setup-audit-hooks)", file=sys.stderr)
        return 2

    inflight: dict[str, list[dict[str, Any]]] = defaultdict(list)  # session_id -> stack
    durations_ms_by_tool: dict[str, list[float]] = defaultdict(list)
    unmatched_posts = 0

    for r in rows:
        sid = r.get("session_id")
        sid_s = sid.strip() if isinstance(sid, str) else ""
        if session_id and sid_s != session_id:
            continue
        ev = r.get("event")
        tn = r.get("tool_name")
        if not (isinstance(ev, str) and isinstance(tn, str) and sid_s and tn.strip()):
            continue
        ev = ev.strip()
        tn = tn.strip()
        ts = _parse_ts(r.get("ts"))
        if ts is None:
            continue
        call_id = r.get("tool_call_id")
        call_id_s = call_id.strip() if isinstance(call_id, str) and call_id.strip() else None

        if ev == "PreToolUse":
            inflight[sid_s].append({"tool_name": tn, "ts": ts, "tool_call_id": call_id_s})
            continue

        if ev != "PostToolUse":
            continue

        stack = inflight.get(sid_s) or []
        match_i = None
        if call_id_s:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i].get("tool_call_id") == call_id_s:
                    match_i = i
                    break
        if match_i is None:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i].get("tool_name") == tn:
                    match_i = i
                    break
        if match_i is None:
            unmatched_posts += 1
            continue
        started = stack.pop(match_i)
        t0 = started.get("ts")
        if isinstance(t0, datetime):
            dur_ms = (ts - t0).total_seconds() * 1000.0
            if dur_ms >= 0:
                xs = durations_ms_by_tool[tn]
                if len(xs) < 5000:
                    xs.append(dur_ms)

    if not durations_ms_by_tool:
        print("No paired PreToolUse/PostToolUse samples found.")
        if unmatched_posts:
            print(f"unmatched_posts: {unmatched_posts}")
        return 0

    summary: list[dict[str, Any]] = []
    for tool, xs in durations_ms_by_tool.items():
        summary.append(
            {
                "tool_name": tool,
                "count": len(xs),
                "avg_ms": round(sum(xs) / len(xs), 2),
                "p50_ms": _percentile(xs, 0.50),
                "p95_ms": _percentile(xs, 0.95),
                "max_ms": round(max(xs), 2),
            }
        )
    summary.sort(key=lambda it: (-int(it.get("count", 0)), str(it.get("tool_name", ""))))

    if session_id:
        print(f"session_id: {session_id}")
    print(f"paired_samples: {sum(int(it.get('count', 0)) for it in summary)}")
    print(f"unmatched_posts: {unmatched_posts}")
    print("")
    for it in summary[:40]:
        print(
            f"- {it.get('tool_name','')}: n={it.get('count','')} avg_ms={it.get('avg_ms','')} "
            f"p50_ms={it.get('p50_ms','')} p95_ms={it.get('p95_ms','')} max_ms={it.get('max_ms','')}"
        )
    return 0


def cmd_traces(project_root: Path, *, session_id: str | None) -> int:
    tools_path, rows = _load_tools(project_root)
    if not tools_path.exists():
        print(f"FAIL: {tools_path} not found (install audit hooks with /at:setup-audit-hooks)", file=sys.stderr)
        return 2

    traces: list[dict[str, Any]] = []
    for r in rows:
        sid = r.get("session_id")
        sid_s = sid.strip() if isinstance(sid, str) else ""
        if session_id and sid_s != session_id:
            continue
        if "tool_input" not in r and "tool_output" not in r:
            continue
        call_id = r.get("tool_call_id")
        call_id_s = call_id.strip() if isinstance(call_id, str) else ""
        traces.append(
            {
                "ts": r.get("ts"),
                "event": r.get("event"),
                "tool_name": r.get("tool_name"),
                "tool_call_id": call_id_s,
                "has_input": "tool_input" in r,
                "has_output": "tool_output" in r,
            }
        )

    if not traces:
        print("No trace payloads found in tools.jsonl.")
        print("Hint: enable trace capture by setting AT_AUDIT_TRACES_ENABLED=1 before installing audit hooks.")
        return 0

    if session_id:
        print(f"session_id: {session_id}")
    print(f"trace_records: {len(traces)}")
    for t in traces[:60]:
        print(
            f"- ts={t.get('ts','')} event={t.get('event','')} tool={t.get('tool_name','')} "
            f"tool_call_id={t.get('tool_call_id','') or '-'} input={t.get('has_input')} output={t.get('has_output')}"
        )
    if len(traces) > 60:
        print(f"... ({len(traces) - 60} more)")
    return 0


def _truncate_json(value: Any, *, max_chars: int) -> str:
    try:
        s = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        s = repr(value)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def cmd_trace_detail(project_root: Path, *, tool_call_id: str, session_id: str | None, max_chars: int) -> int:
    tools_path, rows = _load_tools(project_root)
    if not tools_path.exists():
        print(f"FAIL: {tools_path} not found (install audit hooks with /at:setup-audit-hooks)", file=sys.stderr)
        return 2

    matches: list[dict[str, Any]] = []
    want = tool_call_id.strip()
    for r in rows:
        sid = r.get("session_id")
        sid_s = sid.strip() if isinstance(sid, str) else ""
        if session_id and sid_s != session_id:
            continue
        cid = r.get("tool_call_id")
        cid_s = cid.strip() if isinstance(cid, str) else ""
        if not cid_s or cid_s != want:
            continue
        matches.append(r)

    if not matches:
        print("No matching tool_call_id found.")
        return 0

    # Print a small, stable view first.
    for r in matches[:8]:
        print(f"ts: {r.get('ts','')}")
        print(f"event: {r.get('event','')}")
        print(f"tool_name: {r.get('tool_name','')}")
        if "result" in r:
            print("result:")
            print(_truncate_json(r.get("result"), max_chars=max_chars))
        if "tool_input" in r:
            print("tool_input:")
            print(_truncate_json(r.get("tool_input"), max_chars=max_chars))
        if "tool_output" in r:
            print("tool_output:")
            print(_truncate_json(r.get("tool_output"), max_chars=max_chars))
        print("")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive audit inspection for .claude/audit_logs (requires audit hooks).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--session-id", default=None, help="Filter by a specific session_id (optional).")
    parser.add_argument("--max-chars", default=12000, type=int, help="Max chars when printing trace payloads.")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List audit log files and sizes.")
    sub.add_parser("sessions", help="Summarize SessionStart/SessionEnd events.")

    p_tools = sub.add_parser("tools", help="Show top tool usage counts.")
    p_tools.add_argument("--session-id", dest="session_id_override", default=None)

    p_timing = sub.add_parser("timing", help="Show best-effort tool latency by pairing PreToolUse/PostToolUse.")
    p_timing.add_argument("--session-id", dest="session_id_override", default=None)

    p_traces = sub.add_parser("traces", help="List trace payload records (requires AT_AUDIT_TRACES_ENABLED=1 at capture).")
    p_traces.add_argument("--session-id", dest="session_id_override", default=None)

    p_detail = sub.add_parser("trace-detail", help="Show trace payload(s) for one tool_call_id.")
    p_detail.add_argument("tool_call_id")
    p_detail.add_argument("--session-id", dest="session_id_override", default=None)

    args = parser.parse_args()
    project_root = detect_project_dir(args.project_dir)

    sid = args.session_id
    if hasattr(args, "session_id_override") and getattr(args, "session_id_override"):
        sid = getattr(args, "session_id_override")

    if args.cmd == "list":
        return cmd_list(project_root)
    if args.cmd == "sessions":
        return cmd_sessions(project_root)
    if args.cmd == "tools":
        return cmd_tools(project_root, session_id=sid)
    if args.cmd == "timing":
        return cmd_timing(project_root, session_id=sid)
    if args.cmd == "traces":
        return cmd_traces(project_root, session_id=sid)
    if args.cmd == "trace-detail":
        return cmd_trace_detail(project_root, tool_call_id=str(args.tool_call_id), session_id=sid, max_chars=int(args.max_chars))

    print(f"Unknown command: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0)
