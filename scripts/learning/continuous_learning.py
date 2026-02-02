#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Continuous learning extractor (opt-in, controlled)

This script extracts low-sensitivity "learnings" from a session and produces:
- a session-backed preview artifact
- (optional) a persisted learning entry under the configured learning dir

Safety goals:
- opt-in persistence (requires --apply --yes)
- do not ingest repo code or secrets
- keep outputs short and stable

Writes:
- SESSION_DIR/learning/continuous_learning_preview.json
- SESSION_DIR/learning/continuous_learning_preview.md

When --apply --yes:
- <learning.dir>/learnings/<session_id>.json
- <learning.dir>/learnings/<session_id>.md
- <learning.dir>/LEARNINGS.md

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import warnings

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "continuous_learning.py is deprecated and will be removed in v0.5.0. "
    "Agent reasoning task. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import load_json_safe, utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from learning.learning_state import ensure_learning_dirs, learning_root  # noqa: E402


def _load_obj(session_dir: Path, rel: str) -> dict[str, Any] | None:
    p = (session_dir / rel).resolve()
    if not p.exists():
        return None
    data = load_json_safe(p, default=None)
    return data if isinstance(data, dict) else None


def _read_recommendations(*objs: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        recs = obj.get("recommendations")
        if not isinstance(recs, list):
            continue
        for r in recs[:100]:
            if isinstance(r, str) and r.strip():
                out.append(" ".join(r.strip().split()))
    # stable dedup
    uniq: list[str] = []
    seen: set[str] = set()
    for r in out:
        if not r or r in seen:
            continue
        seen.add(r)
        uniq.append(r)
    return uniq[:30]


def _learning_enabled(config: dict[str, Any]) -> bool:
    learning = config.get("learning")
    if not isinstance(learning, dict):
        return True
    enabled = learning.get("enabled")
    return bool(enabled) if isinstance(enabled, bool) else True


def _persist_learning(learn_root: Path, entry: dict[str, Any]) -> tuple[Path, Path]:
    session_id = str(entry.get("session_id") or "unknown").strip() or "unknown"
    learnings_dir = learn_root / "learnings"
    learnings_dir.mkdir(parents=True, exist_ok=True)

    json_path = learnings_dir / f"{session_id}.json"
    md_path = learnings_dir / f"{session_id}.md"
    write_json(json_path, entry)

    md: list[str] = []
    md.append("# Learning Entry (at)")
    md.append("")
    md.append(f"- generated_at: `{entry.get('generated_at','')}`")
    md.append(f"- session_id: `{session_id}`")
    outcome = entry.get("outcome") if isinstance(entry.get("outcome"), dict) else {}
    decision = outcome.get("compliance_decision")
    if isinstance(decision, str) and decision:
        md.append(f"- compliance_decision: `{decision}`")
    md.append("")
    md.append("## Signals")
    md.append("")
    signals = entry.get("signals") if isinstance(entry.get("signals"), dict) else {}
    for k in ("failing_gates", "missing_gates", "quality_failed_command_ids"):
        v = signals.get(k)
        if isinstance(v, list) and v:
            md.append(f"- {k}: " + ", ".join([f"`{str(x)}`" for x in v[:12]]))
    if not any(isinstance(signals.get(k), list) and signals.get(k) for k in ("failing_gates", "missing_gates", "quality_failed_command_ids")):
        md.append("- (none)")
    md.append("")
    md.append("## Recommendations")
    md.append("")
    recs = entry.get("recommendations")
    if isinstance(recs, list) and recs:
        for r in recs[:25]:
            if isinstance(r, str) and r.strip():
                md.append(f"- {r.strip()}")
    else:
        md.append("- (none)")
    md.append("")
    write_text(md_path, "\n".join(md))

    # Update rollup index (stable, small).
    all_entries = sorted(learnings_dir.glob("*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    latest = all_entries[:30]
    roll: list[str] = []
    roll.append("# Learnings (at)")
    roll.append("")
    roll.append(f"- updated_at: `{utc_now()}`")
    roll.append(f"- entries: `{len(all_entries)}`")
    roll.append("")
    roll.append("## Recent")
    roll.append("")
    for p in latest:
        data = load_json_safe(p, default={}) or {}
        sid = str(data.get("session_id") or p.stem).strip()
        oc = data.get("outcome") if isinstance(data.get("outcome"), dict) else {}
        dec = oc.get("compliance_decision")
        rec0 = ""
        recs0 = data.get("recommendations")
        if isinstance(recs0, list) and recs0:
            rec0 = str(recs0[0])[:160]
        bits = [f"`{sid}`"]
        if isinstance(dec, str) and dec:
            bits.append(f"decision=`{dec}`")
        if rec0:
            bits.append(f"- {rec0}")
        roll.append(" ".join(bits))
    roll.append("")
    write_text(learn_root / "LEARNINGS.md", "\n".join(roll))

    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract low-sensitivity learnings from a session (opt-in persistence).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--apply", action="store_true", help="Persist into learning.dir (requires --yes).")
    parser.add_argument("--yes", action="store_true", help="Confirm persistence into learning.dir.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    retrospective = _load_obj(session_dir, "retrospective/RETROSPECTIVE.json")
    session_audit = _load_obj(session_dir, "status/session_audit.json")
    session_diagnostics = _load_obj(session_dir, "status/session_diagnostics.json")
    compliance = _load_obj(session_dir, "compliance/compliance_report.json")

    # Prefer retrospective (if present), but fall back to auditor/diagnostics.
    recs = _read_recommendations(retrospective, session_audit, session_diagnostics)
    if not recs:
        recs = ["No high-signal recommendations found (run /at:retrospective and /at:session-auditor for richer output)."]

    outcome: dict[str, Any] = {}
    if isinstance(retrospective, dict):
        oc = retrospective.get("outcome")
        if isinstance(oc, dict):
            outcome.update({k: oc.get(k) for k in ("compliance_decision", "compliance_ok", "gates_ok", "quality_ok", "docs_ok") if k in oc})
    if not outcome and isinstance(compliance, dict):
        outcome = {"compliance_decision": compliance.get("decision"), "compliance_ok": compliance.get("ok")}

    signals: dict[str, Any] = {}
    if isinstance(retrospective, dict):
        sg = retrospective.get("signals")
        if isinstance(sg, dict):
            for k in ("failing_gates", "missing_gates", "quality_failed_command_ids"):
                if k in sg:
                    signals[k] = sg.get(k)

    entry: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "sources": {
            "retrospective": "retrospective/RETROSPECTIVE.json" if retrospective else None,
            "session_audit": "status/session_audit.json" if session_audit else None,
            "session_diagnostics": "status/session_diagnostics.json" if session_diagnostics else None,
            "compliance": "compliance/compliance_report.json" if compliance else None,
        },
        "outcome": outcome,
        "signals": signals,
        "recommendations": recs,
    }

    out_dir = session_dir / "learning"
    out_dir.mkdir(parents=True, exist_ok=True)
    preview_json = out_dir / "continuous_learning_preview.json"
    preview_md = out_dir / "continuous_learning_preview.md"
    write_json(preview_json, entry)

    md: list[str] = []
    md.append("# Continuous Learning (preview)")
    md.append("")
    md.append(f"- generated_at: `{entry['generated_at']}`")
    md.append(f"- session_id: `{entry['session_id']}`")
    md.append(f"- apply_requested: `{str(bool(args.apply)).lower()}`")
    md.append("")
    md.append("## Recommendations")
    md.append("")
    for r in recs[:25]:
        if isinstance(r, str) and r.strip():
            md.append(f"- {r.strip()}")
    md.append("")
    if args.apply and not args.yes:
        md.append("## Apply (blocked)")
        md.append("")
        md.append("- Refusing to persist learnings without explicit confirmation.")
        md.append("- Re-run with: `--apply --yes`")
        md.append("")
    write_text(preview_md, "\n".join(md))

    if args.apply:
        if not args.yes:
            print(str(preview_md))
            return 2
        if not _learning_enabled(config):
            print("ERROR: learning.enabled=false in .claude/project.yaml; refusing to persist learnings.", file=sys.stderr)
            print(str(preview_md))
            return 2
        ensure_learning_dirs(project_root)
        lr = learning_root(project_root)
        json_path, md_path = _persist_learning(lr, entry)
        print(str(md_path))
        return 0

    print(str(preview_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
