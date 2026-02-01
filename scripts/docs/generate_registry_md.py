#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Generate docs/DOCUMENTATION_REGISTRY.md from docs/DOCUMENTATION_REGISTRY.json

Deterministic, repo-local, and safe to run in CI.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import write_text  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir, load_project_config  # noqa: E402
from lib.docs_registry import get_docs_registry_path  # noqa: E402


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _render(registry: dict[str, Any], *, registry_path: str) -> str:
    version = registry.get("version")
    if version != 2:
        raise RuntimeError(f"Expected registry.version=2 (got {version!r})")

    docs = registry.get("docs") if isinstance(registry.get("docs"), list) else []
    generated = registry.get("generated_artifacts") if isinstance(registry.get("generated_artifacts"), list) else []

    # Sort by tier (asc), then id.
    def _key_doc(it: dict[str, Any]) -> tuple[int, str]:
        tier = it.get("tier")
        t = int(tier) if isinstance(tier, int) else 999
        did = it.get("id") if isinstance(it.get("id"), str) else ""
        return (t, did)

    items: list[dict[str, Any]] = [it for it in docs if isinstance(it, dict)]
    items.sort(key=_key_doc)

    lines: list[str] = []
    lines.append("# Documentation Registry (at)")
    lines.append("")
    lines.append("AUTO-GENERATED. DO NOT EDIT.")
    lines.append(f"Source of truth: `{registry_path}`")
    lines.append("")
    lines.append("This file is generated from the JSON registry and is intended for fast human scanning.")
    lines.append("")
    lines.append("## Index")
    lines.append("")
    lines.append("| Tier | Type | ID | Status | Owners | Title | Path | When | Tags |")
    lines.append("|---:|---|---|---|---|---|---|---|---|")
    for it in items[:4000]:
        doc_id = it.get("id") if isinstance(it.get("id"), str) else ""
        doc_type = it.get("type") if isinstance(it.get("type"), str) else ""
        title = it.get("title") if isinstance(it.get("title"), str) else ""
        path = it.get("path") if isinstance(it.get("path"), str) else ""
        when = it.get("when") if isinstance(it.get("when"), str) else ""
        tags = it.get("tags") if isinstance(it.get("tags"), list) else []
        owners = it.get("owners") if isinstance(it.get("owners"), list) else []
        status = it.get("status") if isinstance(it.get("status"), str) else ""
        tier = it.get("tier") if isinstance(it.get("tier"), int) else ""
        norm = normalize_repo_relative_posix_path(path) if isinstance(path, str) and path else None
        path_s = norm or path
        if not doc_id or not path_s:
            continue
        when_s = (when.strip().replace("\n", " "))[:180]
        tags_s = ", ".join([str(t).strip() for t in tags[:12] if isinstance(t, str) and str(t).strip()])
        owners_s = ", ".join([str(o).strip() for o in owners[:8] if isinstance(o, str) and str(o).strip()])
        lines.append(f"| {tier} | {doc_type} | `{doc_id}` | {status} | {owners_s} | {title} | `{path_s}` | {when_s} | {tags_s} |")

    if generated:
        lines.append("")
        lines.append("## Generated Artifacts")
        lines.append("")
        lines.append("| ID | Path | Source | Generator | Mode |")
        lines.append("|---|---|---|---|---|")
        for it in generated[:200]:
            if not isinstance(it, dict):
                continue
            gid = it.get("id") if isinstance(it.get("id"), str) else ""
            gpath = it.get("path") if isinstance(it.get("path"), str) else ""
            src = it.get("source") if isinstance(it.get("source"), str) else ""
            generator = it.get("generator") if isinstance(it.get("generator"), str) else ""
            mode = it.get("mode") if isinstance(it.get("mode"), str) else ""
            if not gid or not gpath:
                continue
            gpath_norm = normalize_repo_relative_posix_path(gpath) or gpath
            src_norm = normalize_repo_relative_posix_path(src) or src
            lines.append(f"| `{gid}` | `{gpath_norm}` | `{src_norm}` | {generator} | {mode} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Tiers: 1=core contract, 2=architecture/conventions, 3=how-to, 4=reference/appendix.")
    lines.append("- Keep docs concise and keep this registry accurate; gates may fail on drift.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/DOCUMENTATION_REGISTRY.md from the JSON registry.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--registry-path", default=None, help="Override docs registry JSON path (else from config).")
    parser.add_argument("--out", default="docs/DOCUMENTATION_REGISTRY.md")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if output differs (do not write).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    cfg = load_project_config(project_root) or {}
    registry_path = args.registry_path or get_docs_registry_path(cfg)
    reg_file = (project_root / registry_path).resolve()
    if not reg_file.exists():
        print(f"ERROR: missing registry JSON: {registry_path}", file=sys.stderr)
        return 2

    registry = _load_json(reg_file)
    if registry is None:
        print(f"ERROR: invalid registry JSON: {registry_path}", file=sys.stderr)
        return 2

    try:
        rendered = _render(registry, registry_path=registry_path).rstrip() + "\n"
    except Exception as exc:
        print(f"ERROR: failed to render registry markdown: {exc}", file=sys.stderr)
        return 2
    out_path = (project_root / args.out).resolve()

    current = ""
    if out_path.exists():
        current = out_path.read_text(encoding="utf-8", errors="ignore")

    if args.check:
        if current != rendered:
            print(f"DRIFT: {args.out} is not in sync with {registry_path}", file=sys.stderr)
            return 1
        print("OK: registry markdown is in sync.")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text(out_path, rendered)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
