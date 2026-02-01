#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Architecture boundary checker (portable, deterministic)

Checks dependency direction by scanning imports for supported languages:
- Python
- Go
- TypeScript

Configuration is JSON (repo-local) and specifies:
- ignore_file_globs
- boundaries[] with path_globs and forbid_import_regex per language
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Violation:
    boundary: str
    file: str
    line: int
    language: str
    imported: str
    pattern: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def _matches_any(path_posix: str, globs: list[str]) -> bool:
    p = path_posix.replace("\\", "/")
    for g in globs:
        if not isinstance(g, str) or not g.strip():
            continue
        if fnmatch.fnmatch(p, g.strip()):
            return True
    return False


def _iter_files(project_root: Path, include_globs: list[str], ignore_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    root = project_root.resolve()
    # Use rglob for simplicity; filter via globs deterministically.
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.resolve().relative_to(root).as_posix()
        except Exception:
            continue
        if _matches_any(rel, ignore_globs):
            continue
        if not _matches_any(rel, include_globs):
            continue
        files.append(p)
    return files


_PY_IMPORT = re.compile(r"^\s*import\s+([a-zA-Z0-9_\.]+)\s*$")
_PY_FROM = re.compile(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+")


def _python_imports(path: Path) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _PY_IMPORT.match(line) or _PY_FROM.match(line)
        if m:
            imports.append((m.group(1), idx))
    return imports


_GO_IMPORT_SINGLE = re.compile(r'^\s*import\s+"([^"]+)"\s*$')
_GO_IMPORT_START = re.compile(r"^\s*import\s*\(\s*$")
_GO_IMPORT_LINE = re.compile(r'^\s*"([^"]+)"\s*$')


def _go_imports(path: Path) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    in_block = False
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if not in_block:
            if _GO_IMPORT_START.match(line):
                in_block = True
                continue
            m = _GO_IMPORT_SINGLE.match(line)
            if m:
                imports.append((m.group(1), idx))
            continue
        else:
            if line.startswith(")"):
                in_block = False
                continue
            m = _GO_IMPORT_LINE.match(line)
            if m:
                imports.append((m.group(1), idx))
    return imports


_TS_IMPORT_FROM = re.compile(r'^\s*import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]\s*;?\s*$')
_TS_IMPORT_BARE = re.compile(r'^\s*import\s+[\'"]([^\'"]+)[\'"]\s*;?\s*$')
_TS_DYNAMIC_IMPORT = re.compile(r'import\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
_TS_REQUIRE = re.compile(r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)')


def _ts_imports(path: Path) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = _TS_IMPORT_FROM.match(line) or _TS_IMPORT_BARE.match(line)
        if m:
            imports.append((m.group(1), idx))
            continue
        for rx in (_TS_DYNAMIC_IMPORT, _TS_REQUIRE):
            m2 = rx.search(line)
            if m2:
                imports.append((m2.group(1), idx))
    return imports


def _language_for_path(path: Path) -> str | None:
    s = path.name.lower()
    if s.endswith(".py"):
        return "python"
    if s.endswith(".go"):
        return "go"
    if s.endswith(".ts") or s.endswith(".tsx"):
        return "typescript"
    return None


def _iter_imports(path: Path, language: str) -> list[tuple[str, int]]:
    if language == "python":
        return _python_imports(path)
    if language == "go":
        return _go_imports(path)
    if language == "typescript":
        return _ts_imports(path)
    return []


def _compile_regexes(items: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for s in items[:200]:
        if not isinstance(s, str) or not s.strip():
            continue
        out.append(re.compile(s))
    return out


def _relpath(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _check_boundary(
    *,
    project_root: Path,
    boundary_name: str,
    files: list[Path],
    forbid_by_lang: dict[str, list[re.Pattern[str]]],
) -> list[Violation]:
    violations: list[Violation] = []
    for path in files:
        lang = _language_for_path(path)
        if not lang:
            continue
        forbid = forbid_by_lang.get(lang, [])
        if not forbid:
            continue
        for imported, line in _iter_imports(path, lang):
            for rx in forbid:
                if rx.search(imported):
                    violations.append(
                        Violation(
                            boundary=boundary_name,
                            file=_relpath(project_root, path),
                            line=line,
                            language=lang,
                            imported=imported,
                            pattern=rx.pattern,
                        )
                    )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", required=True)
    parser.add_argument("--json", dest="json_out", default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (project_root / config_path).resolve()

    cfg = _load_json(config_path)
    boundaries = cfg.get("boundaries", [])
    if not isinstance(boundaries, list) or not boundaries:
        raise RuntimeError("Config must contain non-empty boundaries[]")

    ignore_globs = cfg.get("ignore_file_globs", [])
    if not isinstance(ignore_globs, list):
        raise RuntimeError("ignore_file_globs must be a list")

    all_violations: list[Violation] = []
    scanned_files = 0

    for boundary in boundaries:
        if not isinstance(boundary, dict):
            continue
        name = boundary.get("name")
        path_globs = boundary.get("path_globs")
        forbid_rx = boundary.get("forbid_import_regex", {})
        if not isinstance(name, str) or not name:
            raise RuntimeError("Each boundary must have a non-empty name")
        if not isinstance(path_globs, list) or not path_globs:
            raise RuntimeError(f"Boundary {name} must have non-empty path_globs")
        if not isinstance(forbid_rx, dict):
            raise RuntimeError(f"Boundary {name} forbid_import_regex must be an object")

        files = _iter_files(project_root, [str(g) for g in path_globs], [str(g) for g in ignore_globs])
        scanned_files += len(files)

        forbid_by_lang: dict[str, list[re.Pattern[str]]] = {}
        for lang, patterns in forbid_rx.items():
            if not isinstance(patterns, list):
                continue
            forbid_by_lang[str(lang)] = _compile_regexes([str(p) for p in patterns])

        all_violations.extend(_check_boundary(project_root=project_root, boundary_name=name, files=files, forbid_by_lang=forbid_by_lang))

    report = {"version": 1, "scanned_files": scanned_files, "violations": [v.__dict__ for v in all_violations]}
    if args.json_out:
        out_path = Path(args.json_out)
        if not out_path.is_absolute():
            out_path = project_root / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if all_violations:
        print(f"FAIL: {len(all_violations)} architecture boundary violations found", file=sys.stderr)
        for v in all_violations[:50]:
            print(f"- {v.file}:{v.line} ({v.language}) imported {v.imported!r} (matched {v.pattern!r})", file=sys.stderr)
        return 1

    print(f"OK: architecture boundaries satisfied (scanned_files={scanned_files})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

