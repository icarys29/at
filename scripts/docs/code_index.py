#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Code index for docs generation (session-backed, deterministic)

This script analyzes code to produce a lightweight "code index" artifact used by
docs-keeper to generate/update documentation with better grounding.

Writes (by default):
- SESSION_DIR/documentation/code_index.json
- SESSION_DIR/documentation/code_index.md

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "code_index.py is deprecated and will be removed in v0.5.0. "
    "Use LSP tool directly for code analysis. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.path_policy import forbid_globs_from_project_config, is_forbidden_path, normalize_repo_relative_posix_path, resolve_path_under_project_root  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402
from lib.simple_yaml import load_minimal_yaml  # noqa: E402





_SUPPORTED_EXTS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

_DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".session",
    ".claude",
    "docs",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

_MAX_FILE_BYTES_DEFAULT = 400_000
_MAX_FILES_CHANGED_DEFAULT = 250
_MAX_FILES_FULL_DEFAULT = 2000
_MAX_SYMBOLS_PER_FILE = 200


@dataclass(frozen=True)
class Symbol:
    kind: str
    name: str
    line: int | None
    signature: str | None
    doc_head: str | None
    members: list[str] | None = None


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        data = load_minimal_yaml(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _collect_changed_files(session_dir: Path) -> list[str]:
    paths: list[str] = []
    task_paths = sorted((session_dir / "implementation" / "tasks").glob("*.yaml")) + sorted(
        (session_dir / "testing" / "tasks").glob("*.yaml")
    )
    for p in task_paths:
        data = _load_yaml(p)
        if not data:
            continue
        changed = data.get("changed_files")
        if not isinstance(changed, list):
            continue
        for it in changed[:2000]:
            if not isinstance(it, dict):
                continue
            fp = it.get("path")
            act = it.get("action")
            if not (isinstance(fp, str) and fp.strip()):
                continue
            if act not in {"created", "modified"}:
                continue
            norm = normalize_repo_relative_posix_path(fp.strip().replace("\\", "/"))
            if norm:
                paths.append(norm)
    # Dedup stable.
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return sorted(out)


def _iter_code_files_full(project_root: Path, *, forbid: list[str], max_files: int) -> list[str]:
    files: list[str] = []
    root = project_root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        # Prune excluded dirs early.
        pruned: list[str] = []
        for d in dirnames:
            if d in _DEFAULT_EXCLUDE_DIRS:
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)
        # Also prune if any parent is excluded.
        if any(p in _DEFAULT_EXCLUDE_DIRS for p in parts):
            dirnames[:] = []
            continue

        for fn in filenames:
            if max_files > 0 and len(files) >= max_files:
                return sorted(files)
            ext = Path(fn).suffix.lower()
            if ext not in _SUPPORTED_EXTS:
                continue
            rel = (Path(rel_dir) / fn) if rel_dir != "." else Path(fn)
            rel_posix = str(rel).replace("\\", "/")
            norm = normalize_repo_relative_posix_path(rel_posix)
            if not norm:
                continue
            if is_forbidden_path(norm, forbid):
                continue
            files.append(norm)
    return sorted(files)


def _safe_read_bytes(path: Path, *, max_bytes: int) -> tuple[bytes, str | None]:
    try:
        data = path.read_bytes()
    except Exception as exc:
        return b"", f"read_error: {exc}"
    if max_bytes > 0 and len(data) > max_bytes:
        return b"", f"too_large: {len(data)} bytes > {max_bytes}"
    return data, None


def _doc_head(text: str | None, *, max_len: int = 140) -> str | None:
    if not isinstance(text, str):
        return None
    head = text.strip().splitlines()[0].strip() if text.strip() else ""
    if not head:
        return None
    head = re.sub(r"\\s+", " ", head)
    return head[:max_len]


def _format_py_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    a = fn.args
    parts: list[str] = []
    for arg in getattr(a, "posonlyargs", []) or []:
        if isinstance(arg, ast.arg) and arg.arg:
            parts.append(arg.arg)
    if getattr(a, "posonlyargs", None):
        parts.append("/")
    for arg in a.args or []:
        if isinstance(arg, ast.arg) and arg.arg:
            parts.append(arg.arg)
    if a.vararg and isinstance(a.vararg, ast.arg) and a.vararg.arg:
        parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        parts.append("*")
    for arg in a.kwonlyargs or []:
        if isinstance(arg, ast.arg) and arg.arg:
            parts.append(arg.arg)
    if a.kwarg and isinstance(a.kwarg, ast.arg) and a.kwarg.arg:
        parts.append("**" + a.kwarg.arg)
    return f"{fn.name}(" + ", ".join([p for p in parts if p]) + ")"


def _extract_python_symbols(text: str) -> tuple[list[Symbol], list[str]]:
    try:
        tree = ast.parse(text)
    except Exception:
        return ([], [])

    symbols: list[Symbol] = []
    imports: set[str] = set()

    for node in tree.body[:10_000]:
        if isinstance(node, ast.Import):
            for alias in node.names[:100]:
                if isinstance(alias, ast.alias) and alias.name:
                    imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

        if isinstance(node, ast.ClassDef):
            doc = _doc_head(ast.get_docstring(node))
            members: list[str] = []
            for item in node.body[:5000]:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name:
                    members.append(item.name)
            members = sorted(set(members))[:80]
            symbols.append(
                Symbol(
                    kind="class",
                    name=node.name,
                    line=int(getattr(node, "lineno", 0)) or None,
                    signature=None,
                    doc_head=doc,
                    members=members if members else None,
                )
            )
        elif isinstance(node, ast.FunctionDef):
            doc = _doc_head(ast.get_docstring(node))
            symbols.append(
                Symbol(
                    kind="function",
                    name=node.name,
                    line=int(getattr(node, "lineno", 0)) or None,
                    signature=_format_py_signature(node),
                    doc_head=doc,
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            doc = _doc_head(ast.get_docstring(node))
            symbols.append(
                Symbol(
                    kind="async_function",
                    name=node.name,
                    line=int(getattr(node, "lineno", 0)) or None,
                    signature=_format_py_signature(node),
                    doc_head=doc,
                )
            )

        if len(symbols) >= _MAX_SYMBOLS_PER_FILE:
            break

    # Stable order: by line then kind/name.
    symbols.sort(key=lambda s: (s.line or 0, s.kind, s.name))
    return (symbols, sorted(imports))


def _extract_regex_symbols(text: str, language: str) -> list[Symbol]:
    """
    Best-effort extraction for non-Python languages.
    Keep it conservative to avoid noisy or misleading output.
    """
    out: list[Symbol] = []
    lines = text.splitlines()

    if language in {"javascript", "typescript"}:
        patterns: list[tuple[str, str]] = [
            (r"^\\s*export\\s+function\\s+(?P<name>[A-Za-z_$][\\w$]*)\\s*\\(", "function"),
            (r"^\\s*function\\s+(?P<name>[A-Za-z_$][\\w$]*)\\s*\\(", "function"),
            (r"^\\s*export\\s+class\\s+(?P<name>[A-Za-z_$][\\w$]*)\\b", "class"),
            (r"^\\s*class\\s+(?P<name>[A-Za-z_$][\\w$]*)\\b", "class"),
        ]
    elif language == "go":
        patterns = [
            (r"^\\s*type\\s+(?P<name>[A-Za-z_][\\w]*)\\s+struct\\b", "struct"),
            (r"^\\s*type\\s+(?P<name>[A-Za-z_][\\w]*)\\s+interface\\b", "interface"),
            (r"^\\s*func\\s+(?P<name>[A-Za-z_][\\w]*)\\s*\\(", "function"),
        ]
    elif language == "rust":
        patterns = [
            (r"^\\s*pub\\s+fn\\s+(?P<name>[A-Za-z_][\\w]*)\\s*\\(", "function"),
            (r"^\\s*fn\\s+(?P<name>[A-Za-z_][\\w]*)\\s*\\(", "function"),
            (r"^\\s*pub\\s+struct\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "struct"),
            (r"^\\s*struct\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "struct"),
            (r"^\\s*pub\\s+enum\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "enum"),
            (r"^\\s*enum\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "enum"),
            (r"^\\s*pub\\s+trait\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "trait"),
            (r"^\\s*trait\\s+(?P<name>[A-Za-z_][\\w]*)\\b", "trait"),
        ]
    else:
        return []

    for i, line in enumerate(lines[:40_000], start=1):
        # Ignore common single-line comments to reduce false positives.
        stripped = line.lstrip()
        if stripped.startswith(("//", "#")):
            continue
        for pat, kind in patterns:
            m = re.match(pat, line)
            if not m:
                continue
            name = m.groupdict().get("name")
            if not name:
                continue
            out.append(Symbol(kind=kind, name=name, line=i, signature=None, doc_head=None))
            break
        if len(out) >= _MAX_SYMBOLS_PER_FILE:
            break
    out.sort(key=lambda s: (s.line or 0, s.kind, s.name))
    return out


def _analyze_file(project_root: Path, rel_posix: str, *, forbid: list[str], max_file_bytes: int) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    norm = normalize_repo_relative_posix_path(rel_posix)
    if not norm:
        return None, {"path": rel_posix, "reason": "invalid_path"}
    if is_forbidden_path(norm, forbid):
        return None, {"path": norm, "reason": "forbidden_path"}

    ext = Path(norm).suffix.lower()
    language = _SUPPORTED_EXTS.get(ext)
    if not language:
        return None, {"path": norm, "reason": "unsupported_extension"}

    abs_path = resolve_path_under_project_root(project_root, norm)
    if abs_path is None:
        return None, {"path": norm, "reason": "outside_project_root"}
    if not abs_path.exists():
        return None, {"path": norm, "reason": "missing"}
    if not abs_path.is_file():
        return None, {"path": norm, "reason": "not_a_file"}

    data, err = _safe_read_bytes(abs_path, max_bytes=max_file_bytes)
    if err:
        return None, {"path": norm, "reason": err}
    text = data.decode("utf-8", errors="ignore")

    symbols: list[Symbol] = []
    imports: list[str] = []
    if language == "python":
        symbols, imports = _extract_python_symbols(text)
    else:
        symbols = _extract_regex_symbols(text, language)

    payload: dict[str, Any] = {
        "path": norm,
        "language": language,
        "symbols": [
            {
                "kind": s.kind,
                "name": s.name,
                "line": s.line,
                "signature": s.signature,
                "doc_head": s.doc_head,
                "members": s.members,
            }
            for s in symbols[:_MAX_SYMBOLS_PER_FILE]
        ],
    }
    if imports and language == "python":
        payload["imports"] = imports[:80]
    return payload, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic code index for docs generation (session-backed).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--mode", default="changed", choices=["changed", "full"], help="Analyze changed files (default) or full repo.")
    parser.add_argument("--max-files", type=int, default=0, help="Hard limit on files analyzed (0 uses mode default).")
    parser.add_argument("--max-file-bytes", type=int, default=_MAX_FILE_BYTES_DEFAULT, help="Skip files larger than this many bytes.")
    parser.add_argument("--out-json", default=None, help="Override output JSON path (default: SESSION_DIR/documentation/code_index.json)")
    parser.add_argument("--out-md", default=None, help="Override output Markdown path (default: SESSION_DIR/documentation/code_index.md)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    forbid = forbid_globs_from_project_config(config)

    max_files = int(args.max_files) if int(args.max_files) > 0 else (_MAX_FILES_FULL_DEFAULT if args.mode == "full" else _MAX_FILES_CHANGED_DEFAULT)
    max_file_bytes = int(args.max_file_bytes) if int(args.max_file_bytes) > 0 else _MAX_FILE_BYTES_DEFAULT

    if args.mode == "full":
        targets = _iter_code_files_full(project_root, forbid=forbid, max_files=max_files)
        source = "filesystem_scan"
    else:
        targets = _collect_changed_files(session_dir)[:max_files]
        source = "session_tasks.changed_files"

    analyzed: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for rel in targets:
        item, skip = _analyze_file(project_root, rel, forbid=forbid, max_file_bytes=max_file_bytes)
        if skip:
            skipped.append(skip)
            continue
        if item:
            analyzed.append(item)

    out_dir = session_dir / "documentation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = Path(args.out_json).expanduser() if args.out_json else (out_dir / "code_index.json")
    out_md = Path(args.out_md).expanduser() if args.out_md else (out_dir / "code_index.md")

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "session_id": session_dir.name,
        "mode": args.mode,
        "source": source,
        "limits": {"max_files": max_files, "max_file_bytes": max_file_bytes},
        "summary": {
            "targets_total": len(targets),
            "files_analyzed": len(analyzed),
            "files_skipped": len(skipped),
            "symbols_total": sum(len(it.get("symbols") or []) for it in analyzed if isinstance(it, dict)),
        },
        "files": analyzed,
        "skipped": skipped,
    }
    write_json(out_json, report)

    md: list[str] = []
    md.append("# Code Index (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- session_id: `{report['session_id']}`")
    md.append(f"- mode: `{report['mode']}`")
    md.append(f"- source: `{report['source']}`")
    md.append(f"- targets_total: `{report['summary']['targets_total']}`")
    md.append(f"- files_analyzed: `{report['summary']['files_analyzed']}`")
    md.append(f"- files_skipped: `{report['summary']['files_skipped']}`")
    md.append(f"- symbols_total: `{report['summary']['symbols_total']}`")
    md.append("")

    md.append("## Files (sample)")
    md.append("")
    for f in analyzed[:80]:
        if not isinstance(f, dict):
            continue
        path = f.get("path", "")
        lang = f.get("language", "")
        md.append(f"- `{path}` ({lang})")
        syms = f.get("symbols")
        if isinstance(syms, list) and syms:
            for s in syms[:25]:
                if not isinstance(s, dict):
                    continue
                kind = s.get("kind", "")
                name = s.get("name", "")
                line = s.get("line")
                sig = s.get("signature")
                doc = s.get("doc_head")
                base = f"  - `{kind}` `{name}`"
                if isinstance(sig, str) and sig.strip():
                    base += f" — `{sig.strip()}`"
                if isinstance(line, int) and line > 0:
                    base += f" (L{line})"
                if isinstance(doc, str) and doc.strip():
                    base += f" — {doc.strip()}"
                md.append(base)
            if len(syms) > 25:
                md.append(f"  - … ({len(syms) - 25} more symbols)")
        md.append("")
        if len(md) > 2400:
            md.append("- … (truncated)")
            md.append("")
            break

    if skipped:
        md.append("## Skipped (sample)")
        md.append("")
        for s in skipped[:80]:
            if not isinstance(s, dict):
                continue
            md.append(f"- `{s.get('path','')}` — {s.get('reason','')}")
        if len(skipped) > 80:
            md.append(f"- … ({len(skipped) - 80} more)")
        md.append("")

    write_text(out_md, "\n".join(md))
    print(str(out_md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
