#!/usr/bin/env python3
"""
Project enforcement: detect "god classes" (heuristic; default-on)

This is a lightweight, deterministic checker intended to be installed into:
- .claude/at/scripts/check_god_classes.py

It flags Python classes that exceed configurable size thresholds.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IGNORE_DIRS = {
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
    ".session",
}


@dataclass(frozen=True)
class Finding:
    path: str
    class_name: str
    methods: int
    lines: int
    start_line: int
    end_line: int


def _iter_python_files(project_root: Path, *, max_files: int = 50_000) -> list[Path]:
    files: list[Path] = []
    scanned = 0
    for root, dirs, fns in os.walk(project_root, topdown=True):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".git")]
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
    start = getattr(node, "lineno", 0) or 0
    end = getattr(node, "end_lineno", 0) or start
    return (start, end)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect oversized Python classes (god-class heuristic).")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--max-methods", type=int, default=25)
    parser.add_argument("--max-lines", type=int, default=400)
    parser.add_argument("--json", dest="json_out", default=None, help="Write a JSON report to this path (optional)")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    max_methods = int(args.max_methods)
    max_lines = int(args.max_lines)

    findings: list[Finding] = []
    for path in _iter_python_files(project_root):
        rel = str(path.relative_to(project_root)).replace("\\", "/")
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
                findings.append(Finding(path=rel, class_name=node.name, methods=methods, lines=lines, start_line=start, end_line=end))

    ok = len(findings) == 0
    report: dict[str, Any] = {
        "version": 1,
        "ok": ok,
        "thresholds": {"max_methods": max_methods, "max_lines": max_lines},
        "findings_total": len(findings),
        "findings": [f.__dict__ for f in sorted(findings, key=lambda x: (-x.methods, -x.lines, x.path))[:200]],
    }

    if args.json_out:
        outp = Path(args.json_out)
        if not outp.is_absolute():
            outp = (project_root / outp).resolve()
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(__import__("json").dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if ok:
        print("OK: no god classes detected")
        return 0

    print("FAIL: potential god classes detected", file=sys.stderr)
    for f in report["findings"][:20]:
        print(f"- {f.get('path')}:{f.get('start_line')} {f.get('class_name')} methods={f.get('methods')} lines={f.get('lines')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
