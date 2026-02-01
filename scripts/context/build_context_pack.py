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


def _truncate(s: str, n: int) -> str:
    s = s.strip().replace("\n", " ")
    if len(s) <= n:
        return s
    if n <= 1:
        return "…"
    return s[: max(0, n - 1)].rstrip() + "…"


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
        when = item.get("when")
        tags = item.get("tags")
        doc_type = item.get("type")
        owners = item.get("owners")
        status = item.get("status")
        if not isinstance(doc_id, str) or not doc_id.strip():
            continue
        if not isinstance(path, str) or not path.strip():
            continue
        tail = f" — {title}" if isinstance(title, str) and title.strip() else ""
        tier_s = f" (tier {tier})" if isinstance(tier, int) else ""
        type_s = f" [{doc_type.strip()}]" if isinstance(doc_type, str) and doc_type.strip() else ""
        status_s = f" | status: {status.strip()}" if isinstance(status, str) and status.strip() else ""
        owners_s = ""
        if isinstance(owners, list):
            owners_list = [str(o).strip() for o in owners[:8] if isinstance(o, str) and str(o).strip()]
            if owners_list:
                owners_s = " | owners: " + ", ".join(owners_list)
        when_s = ""
        if isinstance(when, str) and when.strip():
            when_s = f" | when: {_truncate(when, 140)}"
        tags_s = ""
        if isinstance(tags, list):
            tags_list = [str(t).strip() for t in tags[:12] if isinstance(t, str) and str(t).strip()]
            if tags_list:
                tags_s = " | tags: " + ", ".join(tags_list)
        out.append(f"- `{doc_id.strip()}`{tier_s}{type_s}: `{path.strip()}`{tail}{status_s}{owners_s}{when_s}{tags_s}")
    if len(docs) > limit:
        out.append(f"- … ({len(docs) - limit} more)")
    return out or ["- (no valid docs entries)"]


def _format_docs_coverage_rules_summary(registry: dict[str, Any] | None, *, limit: int = 80) -> list[str]:
    if not registry:
        return ["- (missing registry)"]
    rules = registry.get("coverage_rules")
    if not isinstance(rules, list) or not rules:
        return ["- (no coverage_rules[])"]

    out: list[str] = []
    for it in rules[:limit]:
        if not isinstance(it, dict):
            continue
        rid = it.get("id")
        desc = it.get("description")
        when = it.get("when")
        match = it.get("match") if isinstance(it.get("match"), dict) else {}
        actions = it.get("actions") if isinstance(it.get("actions"), dict) else {}
        match_any = it.get("match_any") if isinstance(it.get("match_any"), list) else []
        requires = it.get("requires") if isinstance(it.get("requires"), list) else []

        if not isinstance(rid, str) or not rid.strip():
            continue
        rid_s = rid.strip()
        desc_s = when.strip() if isinstance(when, str) and when.strip() else (desc.strip() if isinstance(desc, str) and desc.strip() else "")
        out.append(f"- `{rid_s}`: {desc_s}" if desc_s else f"- `{rid_s}`")

        # Legacy rule shape summary
        if match:
            for key in ("paths_any", "created_paths_any", "modified_paths_any", "deleted_paths_any"):
                globs = match.get(key)
                if isinstance(globs, list):
                    gs = [str(g).strip() for g in globs[:20] if isinstance(g, str) and str(g).strip()]
                    if gs:
                        out.append(f"  - match `{key}`: " + ", ".join([f"`{g}`" for g in gs]))

            req_docs = actions.get("require_doc_ids")
            if isinstance(req_docs, list):
                ds = [str(d).strip() for d in req_docs[:20] if isinstance(d, str) and str(d).strip()]
                if ds:
                    out.append("  - require doc ids: " + ", ".join([f"`{d}`" for d in ds]))

            req_types = actions.get("require_create_types")
            if isinstance(req_types, list):
                ts = [str(t).strip() for t in req_types[:20] if isinstance(t, str) and str(t).strip()]
                if ts:
                    out.append("  - require create types: " + ", ".join([f"`{t}`" for t in ts]))

            note = actions.get("note")
            if isinstance(note, str) and note.strip():
                out.append("  - note: " + _truncate(note, 180))

        # Advanced rule shape summary
        if match_any:
            out.append("  - match_any:")
            for g in match_any[:3]:
                if not isinstance(g, dict):
                    continue
                parts: list[str] = []
                for key in ("paths_any", "changed_paths_any", "created_paths_any", "modified_paths_any", "deleted_paths_any", "keywords_any", "keywords_all"):
                    vv = g.get(key)
                    if isinstance(vv, list):
                        vs = [str(x).strip() for x in vv[:8] if isinstance(x, str) and str(x).strip()]
                        if vs:
                            parts.append(f"{key}=" + ",".join(vs))
                if g.get("always") is True:
                    parts.append("always=true")
                if parts:
                    out.append("    - " + " | ".join([_truncate(p, 120) for p in parts]))

        if requires:
            ids: list[str] = []
            types: list[str] = []
            for r in requires[:30]:
                if not isinstance(r, dict):
                    continue
                did = r.get("id")
                if isinstance(did, str) and did.strip():
                    ids.append(did.strip())
                typ = r.get("type")
                if isinstance(typ, str) and typ.strip():
                    types.append(typ.strip())
            if ids:
                out.append("  - requires ids: " + ", ".join([f"`{d}`" for d in ids[:12]]))
            if types:
                out.append("  - requires types: " + ", ".join([f"`{t}`" for t in types[:12]]))

    if len(rules) > limit:
        out.append(f"- … ({len(rules) - limit} more)")
    return out or ["- (no valid coverage rules entries)"]


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

    lines.append("## Docs Coverage Rules (summary)")
    lines.append("")
    lines.append("These rules are deterministic triggers for when docs must be reviewed/created.")
    lines.append("The action planner should use these rules + each doc’s `when` to select `context.doc_ids[]` per code task.")
    lines.append("")
    lines.extend(_format_docs_coverage_rules_summary(registry))
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
