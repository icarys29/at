#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Audit log helpers (JSONL, best-effort, fail-open)

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditPaths:
    dir: Path
    tools_jsonl: Path
    lifecycle_jsonl: Path
    subagents_jsonl: Path


def get_audit_dir(project_root: Path) -> Path:
    return (project_root / ".claude" / "audit_logs").resolve()


def ensure_audit_paths(project_root: Path) -> AuditPaths:
    d = get_audit_dir(project_root)
    d.mkdir(parents=True, exist_ok=True)
    return AuditPaths(
        dir=d,
        tools_jsonl=d / "tools.jsonl",
        lifecycle_jsonl=d / "lifecycle.jsonl",
        subagents_jsonl=d / "subagents.jsonl",
    )


def _json_default(o: Any) -> str:
    try:
        return str(o)
    except Exception:
        return "<unserializable>"


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    """
    Best-effort append one JSON line. Never raises.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False, default=_json_default)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        return


def traces_enabled() -> bool:
    v = os.environ.get("AT_AUDIT_TRACES_ENABLED", "").strip().lower()
    return v in {"1", "true", "yes", "on"}
