#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Build per-task context slices from actions.json

Version: 0.1.0
Updated: 2026-02-01
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

from lib.docs_registry import (  # noqa: E402
    build_doc_id_to_path_map,
    get_docs_registry_path,
    get_docs_require_registry,
    load_docs_registry,
)
from lib.io import safe_read_text, utc_now, write_json, write_text  # noqa: E402
from lib.path_policy import (  # noqa: E402
    forbid_globs_from_project_config,
    is_forbidden_path,
    normalize_repo_relative_posix_path,
    resolve_path_under_project_root,
)
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


CODE_OWNERS = {"implementor", "tests-builder"}
DOCS_KEEPER_TASK_ID = "docs-keeper"


def _normalize_writes(writes: Any) -> list[str]:
    if not isinstance(writes, list):
        return []
    out: list[str] = []
    for w in writes:
        if not isinstance(w, str) or not w.strip():
            continue
        raw = w.strip().replace("\\", "/")
        is_dir = raw.endswith("/")
        norm = normalize_repo_relative_posix_path(raw)
        if not norm:
            continue
        if is_dir and not norm.endswith("/"):
            norm = norm + "/"
        out.append(norm)
    # Preserve order but remove duplicates.
    deduped: list[str] = []
    seen: set[str] = set()
    for w in out:
        if w in seen:
            continue
        seen.add(w)
        deduped.append(w)
    return deduped


def _extract_md_sections(text: str, prefixes: list[str]) -> str:
    if not prefixes:
        return ""
    # Find headings.
    headings: list[tuple[int, int, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\\s+(.*)$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        headings.append((i, level, title))

    if not headings:
        return ""

    selected: list[tuple[int, int, int]] = []
    for idx, level, title in headings:
        if any(title.startswith(p) for p in prefixes if isinstance(p, str) and p.strip()):
            selected.append((idx, level, idx))

    if not selected:
        return ""

    blocks: list[str] = []
    for start_idx, level, _ in selected:
        end_idx = len(lines)
        for j in range(start_idx + 1, len(lines)):
            m = re.match(r"^(#{1,6})\\s+", lines[j])
            if not m:
                continue
            next_level = len(m.group(1))
            if next_level <= level:
                end_idx = j
                break
        block = "\n".join(lines[start_idx:end_idx]).rstrip()
        if block:
            blocks.append(block)
    return "\n\n".join(blocks).rstrip()


def _extract_code_snippets(
    content: str,
    pattern: str,
    *,
    context_lines: int,
    max_matches: int,
    max_total_lines: int = 240,
) -> tuple[str, str | None]:
    """
    Extract up to `max_matches` snippets for regex `pattern` with `context_lines` around each match.
    Returns (snippet_text, error_reason).
    """
    try:
        rx = re.compile(pattern, flags=re.MULTILINE)
    except re.error as exc:
        return ("[INVALID REGEX]\n", f"invalid regex: {exc}")

    lines = content.splitlines()
    if not lines:
        return ("[EMPTY FILE]\n", None)

    ranges: list[tuple[int, int]] = []
    matches = 0
    for m in rx.finditer(content):
        matches += 1
        if matches > max_matches:
            break
        # Compute 0-based line index.
        line_idx = content.count("\n", 0, m.start())
        start = max(0, line_idx - context_lines)
        end = min(len(lines), line_idx + context_lines + 1)
        ranges.append((start, end))

    if not ranges:
        return ("[NO MATCHES]\n", None)

    # Merge overlapping ranges.
    ranges.sort()
    merged: list[tuple[int, int]] = []
    for s, e in ranges:
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))

    out: list[str] = []
    total_lines = 0
    for s, e in merged:
        block = lines[s:e]
        total_lines += len(block)
        if total_lines > max_total_lines:
            out.append("… [TRUNCATED]\n")
            break
        out.append("\n".join(block).rstrip())
        out.append("")  # spacer
    return ("\n".join(out).rstrip() + "\n", None)


def _load_doc_text(
    project_root: Path,
    rel_path: str,
    forbid_globs: list[str],
    *,
    max_chars: int,
) -> tuple[str, bool, str | None]:
    norm = normalize_repo_relative_posix_path(rel_path)
    if not norm:
        return ("[INVALID DOC PATH]\n", False, "invalid path")
    if is_forbidden_path(norm, forbid_globs):
        return ("[OMITTED: forbidden by policies.forbid_secrets_globs]\n", False, "forbidden")
    resolved = resolve_path_under_project_root(project_root, norm)
    if not resolved or not resolved.exists():
        return ("[MISSING DOC FILE]\n", False, "missing")
    text, truncated = safe_read_text(resolved, max_chars=max_chars)
    return (text, truncated, None)


def _load_rule_text(
    project_root: Path,
    rel_path: str,
    forbid_globs: list[str],
    *,
    max_chars: int,
) -> tuple[str, bool, str | None]:
    """
    Like _load_doc_text but for `.claude/rules/**`.
    """
    norm = normalize_repo_relative_posix_path(rel_path)
    if not norm:
        return ("[INVALID RULE PATH]\n", False, "invalid path")
    if is_forbidden_path(norm, forbid_globs):
        return ("[OMITTED: forbidden by policies.forbid_secrets_globs]\n", False, "forbidden")
    resolved = resolve_path_under_project_root(project_root, norm)
    if not resolved or not resolved.exists():
        return ("[MISSING RULE FILE]\n", False, "missing")
    text, truncated = safe_read_text(resolved, max_chars=max_chars)
    return (text, truncated, None)


def _render_task_context(
    *,
    project_root: Path,
    session_dir: Path,
    config_text: str | None,
    task: dict[str, Any],
    docs_map: dict[str, str] | None,
    forbid_globs: list[str],
    max_doc_chars: int,
    max_code_chars: int,
) -> str:
    tid = str(task.get("id", "")).strip()
    owner = str(task.get("owner", "")).strip()
    summary = str(task.get("summary", "")).strip()
    description = task.get("description") if isinstance(task.get("description"), str) else ""
    file_scope = task.get("file_scope") if isinstance(task.get("file_scope"), dict) else {}

    lines: list[str] = []
    lines.append(f"# Task Context: {tid}")
    lines.append("")
    lines.append("## Task")
    lines.append("")
    lines.append(f"- id: `{tid}`")
    lines.append(f"- owner: `{owner}`")
    lines.append(f"- summary: {summary}")
    lines.append("")

    if description:
        lines.append("## Description")
        lines.append("")
        lines.append(description.rstrip())
        lines.append("")

    lines.append("## File Scope")
    lines.append("")
    allow = file_scope.get("allow", [])
    deny = file_scope.get("deny", [])
    writes = _normalize_writes(file_scope.get("writes", []))
    if isinstance(allow, list) and allow:
        lines.append("- allow:")
        for a in allow[:100]:
            if isinstance(a, str) and a.strip():
                lines.append(f"  - `{a.strip()}`")
    if isinstance(deny, list) and deny:
        lines.append("- deny:")
        for d in deny[:100]:
            if isinstance(d, str) and d.strip():
                lines.append(f"  - `{d.strip()}`")
    if isinstance(writes, list) and writes:
        lines.append("- writes (STRICT, no globs):")
        for w in writes[:200]:
            if isinstance(w, str) and w.strip():
                lines.append(f"  - `{w.strip()}`")
    lines.append("")

    lines.append("## Acceptance Criteria")
    lines.append("")
    acs = task.get("acceptance_criteria", [])
    if isinstance(acs, list) and acs:
        for ac in acs[:200]:
            if not isinstance(ac, dict):
                continue
            ac_id = ac.get("id", "")
            statement = ac.get("statement", "")
            lines.append(f"- `{ac_id}`: {statement}")
            verifs = ac.get("verifications")
            if isinstance(verifs, list) and verifs:
                for v in verifs[:20]:
                    if isinstance(v, dict) and isinstance(v.get("type"), str):
                        lines.append(f"  - verify `{v.get('type')}`")
    else:
        lines.append("- (missing acceptance_criteria in plan)")
    lines.append("")

    if config_text:
        lines.append("## Project Config (excerpt)")
        lines.append("")
        lines.append("```yaml")
        lines.append(config_text.rstrip())
        lines.append("```")
        lines.append("")

    # Always-on rules: keep small, but make them visible to implementors/tests.
    # Include global + project architecture + language rules for configured primary languages.
    cfg = load_project_config(project_root) or {}
    primary_langs: list[str] = []
    proj = cfg.get("project") if isinstance(cfg.get("project"), dict) else {}
    langs = proj.get("primary_languages") if isinstance(proj.get("primary_languages"), list) else []
    for it in langs[:6]:
        if isinstance(it, str) and it.strip():
            primary_langs.append(it.strip())

    rule_paths: list[tuple[str, str]] = [
        (".claude/rules/at/global.md", "Global rules (always-on)"),
        (".claude/rules/project/architecture.md", "Project architecture rules (repo-specific)"),
        *[(f".claude/rules/at/lang/{lang}.md", f"Language rules ({lang})") for lang in primary_langs[:2]],
    ]
    embedded_any = False
    for rp, label in rule_paths:
        content, truncated, err = _load_rule_text(project_root, rp, forbid_globs, max_chars=8_000)
        if err == "missing":
            continue
        if not embedded_any:
            lines.append("## Rules (always-on, embedded)")
            lines.append("")
            embedded_any = True
        lines.append(f"### `{rp}`")
        lines.append("")
        lines.append(f"- Hint: {label}")
        notes: list[str] = []
        if err and err != "missing":
            notes.append(err)
        if truncated:
            notes.append("truncated")
        if notes:
            lines.append(f"- Note: {', '.join(notes)}")
            lines.append("")
        lines.append("```md")
        lines.append(content.rstrip())
        lines.append("```")
        lines.append("")

    # Embedded code pointers (paths + grep patterns)
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    code_pointers = ctx.get("code_pointers") if isinstance(ctx.get("code_pointers"), list) else []
    if code_pointers:
        lines.append("## Code Pointers (embedded)")
        lines.append("")

    for cp in code_pointers[:50]:
        if not isinstance(cp, dict):
            continue
        p = cp.get("path")
        pat = cp.get("pattern")
        if not isinstance(p, str) or not p.strip() or not isinstance(pat, str) or not pat.strip():
            continue
        context_lines = int(cp.get("context_lines")) if isinstance(cp.get("context_lines"), int) else 3
        max_matches = int(cp.get("max_matches")) if isinstance(cp.get("max_matches"), int) else 5

        content, truncated, err = _load_doc_text(project_root, p.strip(), forbid_globs, max_chars=max_code_chars)
        snippet = content
        snippet_err = None
        if not err:
            snippet, snippet_err = _extract_code_snippets(
                content,
                pat.strip(),
                context_lines=max(0, context_lines),
                max_matches=max(1, max_matches),
            )

        lines.append(f"### `{p.strip()}` — /{pat.strip()}/")
        lines.append("")
        notes: list[str] = []
        if err:
            notes.append(err)
        if snippet_err:
            notes.append(snippet_err)
        if truncated:
            notes.append("truncated")
        if notes:
            lines.append(f"- Note: {', '.join(notes)}")
            lines.append("")
        lines.append("```text")
        lines.append(snippet.rstrip())
        lines.append("```")
        lines.append("")

    # Embedded docs
    doc_ids = ctx.get("doc_ids") if isinstance(ctx.get("doc_ids"), list) else []
    doc_sections = ctx.get("doc_sections") if isinstance(ctx.get("doc_sections"), dict) else {}
    include_full_doc = bool(ctx.get("include_full_doc")) if isinstance(ctx.get("include_full_doc"), bool) else False

    if doc_ids:
        lines.append("## Docs (embedded)")
        lines.append("")

    for doc_id in [d for d in doc_ids if isinstance(d, str) and d.strip()]:
        rel_path = docs_map.get(doc_id.strip()) if docs_map else None
        if not rel_path:
            lines.append(f"### {doc_id.strip()}")
            lines.append("")
            lines.append("[UNKNOWN DOC ID]\n")
            continue

        content, truncated, err = _load_doc_text(project_root, rel_path, forbid_globs, max_chars=max_doc_chars)
        excerpt = content
        if not include_full_doc:
            prefixes = doc_sections.get(doc_id.strip())
            if isinstance(prefixes, list):
                extracted = _extract_md_sections(content, [str(p) for p in prefixes if isinstance(p, str)])
                if extracted:
                    excerpt = extracted
                else:
                    excerpt = content[: min(len(content), max_doc_chars)]

        lines.append(f"### {doc_id.strip()} — `{rel_path}`")
        lines.append("")
        if err:
            lines.append(f"- Note: {err}")
            lines.append("")
        if truncated:
            lines.append("- Note: truncated")
            lines.append("")
        lines.append("```md")
        lines.append(excerpt.rstrip())
        lines.append("```")
        lines.append("")

    # Pin the session artifacts expected for this task (for tool-time enforcement + Stop hooks).
    if owner == "implementor":
        lines.append("## Required Output Artifact")
        lines.append("")
        lines.append(f"- Create: `{(session_dir / 'implementation' / 'tasks' / (tid + '.yaml')).relative_to(session_dir)}`")
        lines.append("")
    elif owner == "tests-builder":
        lines.append("## Required Output Artifact")
        lines.append("")
        lines.append(f"- Create: `{(session_dir / 'testing' / 'tasks' / (tid + '.yaml')).relative_to(session_dir)}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_docs_keeper_context(*, session_dir: Path, config_text: str | None) -> str:
    lines: list[str] = []
    lines.append(f"# Task Context: {DOCS_KEEPER_TASK_ID}")
    lines.append("")
    lines.append("## Task")
    lines.append("")
    lines.append(f"- id: `{DOCS_KEEPER_TASK_ID}`")
    lines.append("- owner: `docs-keeper`")
    lines.append("- summary: Keep documentation registry and docs aligned after delivered work.")
    lines.append("")
    lines.append("## File Scope")
    lines.append("")
    lines.append("- writes (STRICT, no globs):")
    lines.append("  - `docs/`")
    lines.append("")
    if config_text:
        lines.append("## Project Config (excerpt)")
        lines.append("")
        lines.append("```yaml")
        lines.append(config_text.rstrip())
        lines.append("```")
        lines.append("")
    lines.append("## Session Inputs")
    lines.append("")
    lines.append(f"- Session root: `{session_dir}`")
    lines.append(f"- Planning: `{(session_dir / 'planning' / 'actions.json').relative_to(session_dir)}`")
    lines.append(f"- Implementation tasks: `{(session_dir / 'implementation' / 'tasks').relative_to(session_dir)}`")
    lines.append(f"- Testing tasks: `{(session_dir / 'testing' / 'tasks').relative_to(session_dir)}`")
    lines.append(f"- Docs plan output: `{(session_dir / 'documentation').relative_to(session_dir)}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build per-task context slices for implementor/tests-builder tasks (and a docs-keeper context for scope enforcement)."
    )
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--max-doc-chars", type=int, default=40_000)
    parser.add_argument("--max-code-chars", type=int, default=12_000)
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    actions_path = session_dir / "planning" / "actions.json"
    try:
        actions = json.loads(actions_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing planning/actions.json: {actions_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in planning/actions.json: {exc}") from exc

    if not isinstance(actions, dict):
        raise RuntimeError("planning/actions.json root must be an object")
    tasks = actions.get("tasks")
    if not isinstance(tasks, list):
        raise RuntimeError("planning/actions.json.tasks must be an array")

    config = load_project_config(project_root) or {}
    forbid = forbid_globs_from_project_config(config)

    config_path = project_root / ".claude" / "project.yaml"
    config_text = None
    if config_path.exists() and not is_forbidden_path(".claude/project.yaml", forbid):
        config_text, _ = safe_read_text(config_path, max_chars=20_000)

    require_registry = get_docs_require_registry(config)
    registry_path = get_docs_registry_path(config)
    registry = load_docs_registry(project_root, registry_path)
    docs_map = build_doc_id_to_path_map(registry)

    if require_registry and not docs_map:
        raise RuntimeError(f"docs.require_registry=true but registry is missing/invalid: {registry_path!r}")

    out_dir = session_dir / "inputs" / "task_context"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_tasks: dict[str, Any] = {}
    generated = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        owner = t.get("owner")
        if owner not in CODE_OWNERS:
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.strip():
            continue

        tid = tid.strip()
        ctx_path = out_dir / f"{tid}.md"
        ctx_text = _render_task_context(
            project_root=project_root,
            session_dir=session_dir,
            config_text=config_text,
            task=t,
            docs_map=docs_map,
            forbid_globs=forbid,
            max_doc_chars=args.max_doc_chars,
            max_code_chars=args.max_code_chars,
        )
        write_text(ctx_path, ctx_text)
        generated += 1

        file_scope = t.get("file_scope") if isinstance(t.get("file_scope"), dict) else {}
        manifest_tasks[tid] = {
            "owner": owner,
            "summary": t.get("summary", ""),
            "file_scope": {
                "allow": file_scope.get("allow", []),
                "deny": file_scope.get("deny", []),
                "writes": _normalize_writes(file_scope.get("writes", [])),
            },
            "context": t.get("context", {}),
        }

    # Always include docs-keeper context in the manifest so file-scope enforcement can authorize docs edits
    # deterministically during the always-on deliver docs sync step.
    dk_path = out_dir / f"{DOCS_KEEPER_TASK_ID}.md"
    write_text(dk_path, _render_docs_keeper_context(session_dir=session_dir, config_text=config_text))
    manifest_tasks[DOCS_KEEPER_TASK_ID] = {
        "owner": "docs-keeper",
        "summary": "Keep documentation registry and docs aligned after delivered work.",
        "file_scope": {"allow": [], "deny": [], "writes": ["docs/"]},
        "context": {},
    }
    generated += 1

    manifest: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "tasks": manifest_tasks,
    }
    write_json(session_dir / "inputs" / "task_context_manifest.json", manifest)

    print(f"Generated {generated} task contexts.")
    print(str(session_dir / "inputs" / "task_context_manifest.json"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
