#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Stamp version metadata headers

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_plugin_version() -> str:
    manifest = PLUGIN_ROOT / "plugin.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("version"), str) and data["version"].strip():
                return data["version"].strip()
        except Exception:
            pass
    version_file = PLUGIN_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def _iter_python_files(*, include_templates: bool) -> list[Path]:
    out: list[Path] = []
    for p in (PLUGIN_ROOT / "scripts").rglob("*.py"):
        if p.name == "__init__.py":
            continue
        out.append(p)
    if include_templates:
        templates = PLUGIN_ROOT / "templates"
        if templates.exists():
            for p in templates.rglob("*.py"):
                out.append(p)
    return sorted({p.resolve() for p in out})


def _iter_frontmatter_md_files(*, include_templates: bool) -> list[Path]:
    candidates: list[Path] = []

    # Plugin agents/skills
    for p in (PLUGIN_ROOT / "agents").glob("*.md"):
        if p.is_file():
            candidates.append(p)
    for p in (PLUGIN_ROOT / "skills").rglob("SKILL.md"):
        if p.is_file():
            candidates.append(p)

    # Repo-local project overlay (this repo uses it for the docs keeper system).
    for p in (PLUGIN_ROOT / ".claude" / "agents").glob("*.md"):
        if p.is_file():
            candidates.append(p)
    for p in (PLUGIN_ROOT / ".claude" / "skills").rglob("SKILL.md"):
        if p.is_file():
            candidates.append(p)

    if include_templates:
        # Templates that get installed into projects should stay version-aligned too.
        for p in (PLUGIN_ROOT / "templates" / "claude" / "agents").glob("*.md"):
            if p.is_file():
                candidates.append(p)
        for p in (PLUGIN_ROOT / "templates" / "claude" / "skills").rglob("SKILL.md"):
            if p.is_file():
                candidates.append(p)

    # Keep only files that actually have frontmatter.
    out: list[Path] = []
    for p in candidates:
        try:
            if p.read_text(encoding="utf-8").startswith("---\n"):
                out.append(p)
        except Exception:
            continue
    return sorted({p.resolve() for p in out})


def _find_header_docstring_span(lines: list[str]) -> tuple[int, int] | None:
    """
    Return (start_idx, end_idx) inclusive indices for the first top-of-file docstring block.
    Only considers a docstring that begins within the first ~30 lines.
    """
    start = None
    for i, line in enumerate(lines[:30]):
        if line.strip().startswith('"""'):
            start = i
            break
    if start is None:
        return None
    # Same-line docstring """..."""
    if lines[start].strip().count('"""') >= 2 and lines[start].strip().endswith('"""'):
        return (start, start)
    for j in range(start + 1, min(len(lines), start + 80)):
        if '"""' in lines[j]:
            return (start, j)
    return None


def _get_python_description(path: Path) -> str:
    # Keep it simple for v1: use current `at:` line if present; otherwise infer from filename.
    stem = path.stem.replace("_", " ")
    if path.parts[-2:] == ("lib", path.name):
        return f"Library module ({stem})"
    return f"Script ({stem})"


def _update_python_header(path: Path, *, version: str, updated: str, dry_run: bool) -> bool:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Detect our header docstring (only in the first ~40 lines).
    head = "\n".join(lines[:40])
    if "at:" in head and "Version:" in head and "Updated:" in head:
        new_head = re.sub(r"^Version:\s*.*$", f"Version: {version}", head, flags=re.MULTILINE)
        new_head = re.sub(r"^Updated:\s*.*$", f"Updated: {updated}", new_head, flags=re.MULTILINE)
        if new_head != head:
            new_content = new_head + "\n" + "\n".join(lines[len(head.splitlines()) :])
            if not dry_run:
                path.write_text(new_content + ("\n" if not new_content.endswith("\n") else ""), encoding="utf-8")
            return True
        return False

    # If the file has a top-level docstring but doesn't match our header format, do not rewrite it.
    # (This keeps behavior predictable and avoids clobbering custom metadata.)
    if _find_header_docstring_span(lines) is not None:
        return False

    description = _get_python_description(path)
    header_lines = [
        '"""',
        f"at: {description}",
        "",
        f"Version: {version}",
        f"Updated: {updated}",
        '"""',
        "",
    ]

    # Insert right after the `# /// script` block if present, else after shebang, else at start.
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    # Keep a contiguous `# /// ... # ///` block together.
    if any(l.strip() == "# /// script" for l in lines[:15]):
        end = None
        for i in range(min(len(lines), 60)):
            if lines[i].strip() == "# ///":
                end = i
        if end is not None:
            insert_at = end + 1

    new_lines = lines[:insert_at] + header_lines + lines[insert_at:]
    new_content = "\n".join(new_lines).rstrip() + "\n"
    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True


def _update_md_frontmatter(path: Path, *, version: str, updated: str, dry_run: bool) -> bool:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return False
    end = content.find("\n---\n", 4)
    if end == -1:
        return False

    fm = content[4:end]
    rest = content[end + 5 :]

    def _has(key: str) -> bool:
        return re.search(rf"^{re.escape(key)}:\s*", fm, flags=re.MULTILINE) is not None

    new_fm = fm
    if _has("version"):
        new_fm = re.sub(r"^version:\s*.*$", f'version: "{version}"', new_fm, flags=re.MULTILINE)
    if _has("updated"):
        new_fm = re.sub(r"^updated:\s*.*$", f'updated: "{updated}"', new_fm, flags=re.MULTILINE)

    if not _has("version") or not _has("updated"):
        lines = new_fm.splitlines()
        out_lines: list[str] = []
        injected = False
        for line in lines:
            out_lines.append(line)
            if not injected and line.startswith("name:"):
                if not _has("version"):
                    out_lines.append(f'version: "{version}"')
                if not _has("updated"):
                    out_lines.append(f'updated: "{updated}"')
                injected = True
        if not injected:
            prefix: list[str] = []
            if not _has("version"):
                prefix.append(f'version: "{version}"')
            if not _has("updated"):
                prefix.append(f'updated: "{updated}"')
            out_lines = prefix + out_lines
        new_fm = "\n".join(out_lines)

    new_content = "---\n" + new_fm.strip("\n") + "\n---\n" + rest
    if new_content != content:
        if not dry_run:
            path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Stamp version/updated metadata into plugin files.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    parser.add_argument("--python-only", action="store_true", help="Only process Python files.")
    parser.add_argument("--md-only", action="store_true", help="Only process Markdown frontmatter files.")
    parser.add_argument("--include-templates", action="store_true", help="Also update templates/** (recommended).")
    args = parser.parse_args()

    version = _load_plugin_version()
    updated = _utc_date()

    changed: list[Path] = []
    if not args.md_only:
        for p in _iter_python_files(include_templates=bool(args.include_templates)):
            if _update_python_header(p, version=version, updated=updated, dry_run=args.dry_run):
                changed.append(p)

    if not args.python_only:
        for p in _iter_frontmatter_md_files(include_templates=bool(args.include_templates)):
            if _update_md_frontmatter(p, version=version, updated=updated, dry_run=args.dry_run):
                changed.append(p)

    if args.dry_run:
        print(f"[DRY RUN] Would update {len(changed)} files:")
    else:
        print(f"Updated {len(changed)} files:")
    for p in changed:
        print(f"- {p.relative_to(PLUGIN_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
