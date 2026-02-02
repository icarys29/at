#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: God-class audit (SRP heuristic; Python-only for now)

This is a user-invocable scanner that flags oversized Python classes using a
simple, deterministic heuristic (method count and line span).

Writes:
- If --session is provided: SESSION_DIR/quality/god_class_audit.{json,md}
- Else: .claude/at/reports/god_class_audit.{json,md}

Exit codes:
- 0 when ok=true (no findings)
- 1 when ok=false (findings present)
- 2 for configuration/runtime errors

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
import warnings
from dataclasses import asdict, dataclass

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "god_class_audit.py is deprecated and will be removed in v0.5.0. "
    "Niche feature, moved to optional pack. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402



_DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    ".claude",
}


@dataclass(frozen=True)
class Finding:
    path: str
    class_name: str
    methods: int
    lines: int
    start_line: int
    end_line: int


def _iter_python_files(project_root: Path, *, ignore_dirs: set[str], max_files: int = 50_000) -> list[Path]:
    files: list[Path] = []
    scanned = 0
    for root, dirs, fns in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for fn in fns:
            scanned += 1
            if max_files > 0 and scanned > max_files:
                break
            if fn.endswith(".py"):
                files.append(Path(root) / fn)
        if max_files > 0 and scanned > max_files:
            break
    return files


def _count_methods(node: ast.ClassDef) -> int:
    return sum(1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _class_span(node: ast.ClassDef) -> tuple[int, int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", 0) or start)
    return (start, end)


def _collect_findings(project_root: Path, *, sessions_dir: str, max_methods: int, max_lines: int) -> list[Finding]:
    ignore = set(_DEFAULT_IGNORE_DIRS)
    sd = (sessions_dir or ".session").strip().strip("/").strip("\\")
    if sd:
        ignore.add(sd)

    findings: list[Finding] = []
    for path in _iter_python_files(project_root, ignore_dirs=ignore):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(text)
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = _count_methods(node)
            start, end = _class_span(node)
            lines = max(0, (end - start + 1)) if start and end else 0
            if methods >= max_methods or lines >= max_lines:
                rel = str(path.relative_to(project_root)).replace("\\", "/")
                findings.append(
                    Finding(
                        path=rel,
                        class_name=node.name,
                        methods=methods,
                        lines=lines,
                        start_line=start,
                        end_line=end,
                    )
                )
    findings.sort(key=lambda f: (-f.methods, -f.lines, f.path, f.class_name))
    return findings


def _default_out_dir(project_root: Path) -> Path:
    return (project_root / ".claude" / "at" / "reports").resolve()


def _render_md(report: dict[str, Any]) -> str:
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    max_methods = (report.get("thresholds") or {}).get("max_methods") if isinstance(report.get("thresholds"), dict) else None
    max_lines = (report.get("thresholds") or {}).get("max_lines") if isinstance(report.get("thresholds"), dict) else None

    md: list[str] = []
    md.append("# God-class Audit (at)")
    md.append("")
    md.append(f"- generated_at: `{report.get('generated_at','')}`")
    md.append(f"- ok: `{str(bool(report.get('ok'))).lower()}`")
    md.append(f"- findings_total: `{report.get('findings_total', 0)}`")
    if isinstance(max_methods, int) and isinstance(max_lines, int):
        md.append(f"- thresholds: methods>={max_methods}, lines>={max_lines}")
    md.append("")

    if not findings:
        md.append("## Findings")
        md.append("")
        md.append("- (none)")
        md.append("")
        return "\n".join(md)

    md.append("## Findings (top)")
    md.append("")
    for it in findings[:30]:
        if not isinstance(it, dict):
            continue
        md.append(
            f"- `{it.get('path','')}`:{it.get('start_line','')} `{it.get('class_name','')}` methods=`{it.get('methods','')}` lines=`{it.get('lines','')}`"
        )
    if len(findings) > 30:
        md.append(f"- ... ({len(findings) - 30} more)")
    md.append("")
    md.append("## Suggested next steps")
    md.append("")
    md.append("- Split responsibilities: extract collaborators (e.g., persistence, IO, HTTP) into separate classes/modules.")
    md.append("- Reduce method count: move cohesive groups of methods into focused services.")
    md.append("- Reduce file/class size: break large switch/dispatch logic into strategy objects.")
    md.append("- Add tests around extracted boundaries before refactoring if behavior is risky.")
    md.append("")
    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for oversized Python classes (god-class heuristic).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory; when set, writes under SESSION_DIR/quality/")
    parser.add_argument("--max-methods", type=int, default=25)
    parser.add_argument("--max-lines", type=int, default=400)
    parser.add_argument("--out-dir", default=None, help="Override output directory (when --session is not provided).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)

    if args.session:
        session_dir = resolve_session_dir(project_root, sessions_dir, str(args.session))
        out_dir = (session_dir / "quality").resolve()
    else:
        out_dir = (Path(args.out_dir).expanduser().resolve() if isinstance(args.out_dir, str) and args.out_dir.strip() else _default_out_dir(project_root))

    out_dir.mkdir(parents=True, exist_ok=True)

    findings = _collect_findings(project_root, sessions_dir=sessions_dir, max_methods=int(args.max_methods), max_lines=int(args.max_lines))
    ok = len(findings) == 0

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "thresholds": {"max_methods": int(args.max_methods), "max_lines": int(args.max_lines)},
        "findings_total": len(findings),
        "findings": [asdict(f) for f in findings[:200]],
    }
    write_json(out_dir / "god_class_audit.json", report)
    write_text(out_dir / "god_class_audit.md", _render_md(report))

    print(str(out_dir / "god_class_audit.md"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
