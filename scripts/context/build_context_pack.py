#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Build context pack for agent workflows

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

from lib.docs_registry import get_docs_registry_path, load_docs_registry  # noqa: E402
from lib.io import safe_read_text, utc_now, write_text  # noqa: E402
from lib.path_policy import forbid_globs_from_project_config, is_forbidden_path, normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


def _format_docs_registry_summary(registry: dict[str, Any] | None, *, limit: int = 200) -> list[str]:
    if not registry:
        return ["- (missing)"]
    docs = registry.get("docs")
    if not isinstance(docs, list) or not docs:
        return ["- (no docs[])"]
    out: list[str] = []
    for item in docs[:limit]:
        if not isinstance(item, dict):
            continue
        doc_id = item.get("id")
        path = item.get("path")
        title = item.get("title")
        tier = item.get("tier")
        if not isinstance(doc_id, str) or not doc_id.strip():
            continue
        if not isinstance(path, str) or not path.strip():
            continue
        tail = f" — {title}" if isinstance(title, str) and title.strip() else ""
        tier_s = f" (tier {tier})" if isinstance(tier, int) else ""
        out.append(f"- `{doc_id.strip()}`{tier_s}: `{path.strip()}`{tail}")
    if len(docs) > limit:
        out.append(f"- … ({len(docs) - limit} more)")
    return out or ["- (no valid docs entries)"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the at context pack for the current session.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--max-chars", type=int, default=40_000)
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    config = load_project_config(project_root) or {}
    forbid = forbid_globs_from_project_config(config)

    lines: list[str] = []
    lines.append("# Context Pack (at)")
    lines.append("")
    lines.append(f"- Generated: {utc_now()}")
    lines.append(f"- Project root: `{project_root}`")
    lines.append(f"- Session dir: `{session_dir}`")
    lines.append("")

    request_path = session_dir / "inputs" / "request.md"
    if request_path.exists():
        content, truncated = safe_read_text(request_path, max_chars=min(args.max_chars, 20_000))
        lines.append("## Request")
        lines.append("")
        lines.append(f"- Source: `{request_path.relative_to(session_dir)}`")
        if truncated:
            lines.append("- Note: truncated")
        lines.append("")
        lines.append("```md")
        lines.append(content.rstrip())
        lines.append("```")
        lines.append("")

    # Project config
    cfg_rel = ".claude/project.yaml"
    cfg_norm = normalize_repo_relative_posix_path(cfg_rel) or cfg_rel
    cfg_path = project_root / cfg_norm
    if cfg_path.exists() and not is_forbidden_path(cfg_norm, forbid):
        content, truncated = safe_read_text(cfg_path, max_chars=min(args.max_chars, 40_000))
        lines.append("## Project Config")
        lines.append("")
        lines.append(f"- Source: `{cfg_norm}`")
        if truncated:
            lines.append("- Note: truncated")
        lines.append("")
        lines.append("```yaml")
        lines.append(content.rstrip())
        lines.append("```")
        lines.append("")

    # Project CLAUDE.md (if present)
    claude_rel = "CLAUDE.md"
    claude_norm = normalize_repo_relative_posix_path(claude_rel) or claude_rel
    claude_path = project_root / claude_norm
    if claude_path.exists() and not is_forbidden_path(claude_norm, forbid):
        content, truncated = safe_read_text(claude_path, max_chars=min(args.max_chars, 60_000))
        lines.append("## Project Instructions (CLAUDE.md)")
        lines.append("")
        lines.append(f"- Source: `{claude_norm}`")
        if truncated:
            lines.append("- Note: truncated")
        lines.append("")
        lines.append("```md")
        lines.append(content.rstrip())
        lines.append("```")
        lines.append("")

    # Docs registry summary
    registry_path = get_docs_registry_path(config)
    registry = load_docs_registry(project_root, registry_path)
    lines.append("## Docs Registry (summary)")
    lines.append("")
    lines.append(f"- Registry path: `{registry_path}`")
    lines.extend(_format_docs_registry_summary(registry))
    lines.append("")

    out = "\n".join(lines).rstrip() + "\n"
    write_text(session_dir / "inputs" / "context_pack.md", out)

    print(str(session_dir / "inputs" / "context_pack.md"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
