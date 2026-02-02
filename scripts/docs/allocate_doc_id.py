#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Deterministic documentation ID allocator (registry-driven)

Allocates the next available numeric ID for a given registry doc type prefix, e.g.:
- ADR-0001
- ARD-0001
- PAT-0001
- RB-0001

This script is intentionally deterministic and project/language agnostic:
- reads docs/DOCUMENTATION_REGISTRY.json (v2) to find doc_types prefix + dir
- scans registry docs[] and the managed doc dir for existing numeric IDs

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path, resolve_path_under_project_root  # noqa: E402
from lib.project import detect_project_dir, load_project_config  # noqa: E402


def _get_doc_type(registry: dict[str, Any], doc_type: str) -> dict[str, Any] | None:
    dts = registry.get("doc_types")
    if not isinstance(dts, list):
        return None
    for it in dts[:200]:
        if not isinstance(it, dict):
            continue
        t = it.get("type")
        if isinstance(t, str) and t.strip() == doc_type:
            return it
    return None


def _collect_existing_numbers(
    project_root: Path,
    *,
    registry: dict[str, Any],
    doc_type: str,
    prefix: str,
    managed_dir: str,
) -> tuple[set[int], int]:
    """
    Returns (numbers, width_guess).
    width_guess is inferred from existing IDs, defaulting to 4.
    """
    numbers: set[int] = set()
    widths: list[int] = []

    rx = re.compile(rf"^{re.escape(prefix)}(?P<num>\d+)$")

    docs = registry.get("docs")
    if isinstance(docs, list):
        for it in docs[:5000]:
            if not isinstance(it, dict):
                continue
            if it.get("type") != doc_type:
                continue
            did = it.get("id")
            if not isinstance(did, str) or not did.strip():
                continue
            m = rx.match(did.strip())
            if not m:
                continue
            raw = m.group("num")
            try:
                numbers.add(int(raw))
                widths.append(len(raw))
            except Exception:
                continue

    dir_norm = normalize_repo_relative_posix_path(managed_dir)
    if dir_norm:
        root = resolve_path_under_project_root(project_root, dir_norm)
        if root and root.exists() and root.is_dir():
            for p in root.rglob("*.md"):
                stem = p.stem
                m = rx.match(stem)
                if not m:
                    continue
                raw = m.group("num")
                try:
                    numbers.add(int(raw))
                    widths.append(len(raw))
                except Exception:
                    continue

    width_guess = max(widths) if widths else 4
    width_guess = max(2, min(width_guess, 8))
    return (numbers, width_guess)


def main() -> int:
    parser = argparse.ArgumentParser(description="Allocate the next available numeric docs id for a given registry doc type.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--registry-path", default=None)
    parser.add_argument("--type", required=True, choices=["context", "architecture", "adr", "ard", "pattern", "runbook"])
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    cfg = load_project_config(project_root) or {}
    registry_path = args.registry_path or get_docs_registry_path(cfg)
    registry = load_docs_registry(project_root, registry_path)
    if not isinstance(registry, dict):
        print(json.dumps({"ok": False, "error": f"missing or invalid registry: {registry_path}"}))
        return 2

    if registry.get("version") != 2:
        print(json.dumps({"ok": False, "error": f"unsupported registry.version: {registry.get('version')!r}"}))
        return 2

    dt = _get_doc_type(registry, args.type)
    if not isinstance(dt, dict):
        print(json.dumps({"ok": False, "error": f"doc type not found in registry.doc_types: {args.type!r}"}))
        return 2

    prefix = dt.get("prefix")
    managed_dir = dt.get("dir")
    if not isinstance(prefix, str) or not prefix.strip():
        print(json.dumps({"ok": False, "error": f"invalid prefix for doc type {args.type!r}"}))
        return 2
    if not isinstance(managed_dir, str) or not managed_dir.strip():
        print(json.dumps({"ok": False, "error": f"invalid dir for doc type {args.type!r}"}))
        return 2

    prefix = prefix.strip()
    managed_dir = managed_dir.strip()

    numbers, width = _collect_existing_numbers(
        project_root,
        registry=registry,
        doc_type=args.type,
        prefix=prefix,
        managed_dir=managed_dir,
    )
    next_num = (max(numbers) + 1) if numbers else 1

    new_id = f"{prefix}{next_num:0{width}d}"
    suggested_path = f"{managed_dir.rstrip('/')}/{new_id}.md"

    print(
        json.dumps(
            {
                "ok": True,
                "registry_path": registry_path,
                "type": args.type,
                "id": new_id,
                "path": suggested_path,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
