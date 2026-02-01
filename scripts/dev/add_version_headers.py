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


def _iter_python_files() -> list[Path]:
    out: list[Path] = []
    for p in (PLUGIN_ROOT / "scripts").rglob("*.py"):
        if p.name == "__init__.py":
            continue
        out.append(p)
    return sorted(out)


def _iter_agent_md_files() -> list[Path]:
    agents_dir = PLUGIN_ROOT / "agents"
    if not agents_dir.exists():
        return []
    return sorted([p for p in agents_dir.glob("*.md") if p.is_file()])


def _iter_skill_md_files() -> list[Path]:
    skills_dir = PLUGIN_ROOT / "skills"
    if not skills_dir.exists():
        return []
    return sorted([p for p in skills_dir.rglob("SKILL.md") if p.is_file()])


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

    description = _get_python_description(path)
    new_header = f'''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
\"\"\"
at: {description}

Version: {version}
Updated: {updated}
\"\"\"'''

    # Remove existing shebang if present.
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]

    # Remove top-of-file docstring only if it looks like an auto header.
    if lines and lines[0].strip().startswith('"""'):
        joined = "\n".join(lines[:40])
        if "Version:" in joined and "Updated:" in joined:
            # Find end of docstring.
            end_idx = None
            for i, line in enumerate(lines):
                if i == 0:
                    if line.strip().endswith('"""') and line.count('"""') >= 2:
                        end_idx = i
                        break
                    continue
                if '"""' in line:
                    end_idx = i
                    break
            if end_idx is not None:
                lines = lines[end_idx + 1 :]

    # Skip leading empty lines.
    while lines and not lines[0].strip():
        lines = lines[1:]

    new_content = new_header + "\n" + "\n".join(lines)
    if not new_content.endswith("\n"):
        new_content += "\n"

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
    args = parser.parse_args()

    version = _load_plugin_version()
    updated = _utc_date()

    changed: list[Path] = []
    for p in _iter_python_files():
        if _update_python_header(p, version=version, updated=updated, dry_run=args.dry_run):
            changed.append(p)

    for p in _iter_agent_md_files():
        if _update_md_frontmatter(p, version=version, updated=updated, dry_run=args.dry_run):
            changed.append(p)

    for p in _iter_skill_md_files():
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
