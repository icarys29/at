#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Analyze a repo and propose onboarding changes (overlay + docs only)

Writes:
- .claude/at/onboarding_report.json
- .claude/at/onboarding_report.md

No production code is modified.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_plugin_root  # noqa: E402
from onboarding.onboarding_utils import detect_languages, render_project_yaml, suggest_commands  # noqa: E402


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / "templates" / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze repo and write an onboarding proposal (no code edits).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--out-dir", default=None, help="Default: <project>/.claude/at")
    # Accept common flags so skills can forward $ARGUMENTS safely.
    parser.add_argument("--apply", action="store_true", help="No-op for analyzer (proposal only).")
    parser.add_argument("--force", action="store_true", help="No-op for analyzer (proposal only).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    plugin_root = get_plugin_root()

    languages = detect_languages(project_root) or ["python"]
    commands_by_lang = suggest_commands(project_root, languages)

    template_project_yaml = _read_template(plugin_root, "project.yaml")
    proposed_project_yaml = render_project_yaml(
        template_text=template_project_yaml,
        project_name=project_root.name,
        languages=languages,
        commands_by_lang=commands_by_lang,
    )

    supported_packs = {"python", "go", "typescript", "rust"}
    recommended_packs = [l for l in languages if l in supported_packs]

    planned_creates: list[str] = []
    for p in (
        ".claude/project.yaml",
        ".claude/rules/at/global.md",
        "docs/DOCUMENTATION_REGISTRY.json",
        "docs/DOCUMENTATION_REGISTRY.md",
        "docs/PROJECT_CONTEXT.md",
        "docs/ARCHITECTURE.md",
        "docs/adr/README.md",
        "docs/architecture/README.md",
        "docs/patterns/README.md",
        "docs/patterns/PAT_PUBLIC_API.md",
        "docs/runbooks/README.md",
    ):
        if not (project_root / p).exists():
            planned_creates.append(p)

    for lang in recommended_packs:
        if not (project_root / ".claude" / "rules" / "at" / "lang" / f"{lang}.md").exists():
            planned_creates.append(f".claude/rules/at/lang/{lang}.md")
        if not (project_root / ".claude" / "at" / "languages" / f"{lang}.json").exists():
            planned_creates.append(f".claude/at/languages/{lang}.json")

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "project_root": str(project_root).replace("\\", "/"),
        "detected_languages": languages,
        "recommended_language_packs": recommended_packs,
        "proposed": {
            "project_yaml_path": ".claude/project.yaml",
            "project_yaml_preview_head": proposed_project_yaml.splitlines()[:120],
        },
        "planned_creates": sorted(set(planned_creates)),
        "notes": [
            "This is a proposal only. Use /at:onboard --apply to write overlay + docs with backups.",
            "No production code files are modified by onboarding.",
        ],
    }

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (project_root / ".claude" / "at").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "onboarding_report.json", report)

    md: list[str] = []
    md.append("# Onboarding Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- project_root: `{report['project_root']}`")
    md.append("")
    md.append("## Detected languages")
    md.append("")
    if languages:
        for l in languages:
            md.append(f"- `{l}`")
    else:
        md.append("- (none detected)")
    md.append("")
    md.append("## Recommended language packs")
    md.append("")
    if recommended_packs:
        for l in recommended_packs:
            md.append(f"- `{l}`")
    else:
        md.append("- (none)")
    md.append("")
    md.append("## Planned creates (overlay + docs)")
    md.append("")
    for p in report["planned_creates"][:300]:
        md.append(f"- `{p}`")
    if len(report["planned_creates"]) > 300:
        md.append(f"- … ({len(report['planned_creates']) - 300} more)")
    md.append("")
    md.append("## Proposed .claude/project.yaml (preview)")
    md.append("")
    md.append("```yaml")
    md.extend(report["proposed"]["project_yaml_preview_head"])
    md.append("```")
    md.append("")
    write_text(out_dir / "onboarding_report.md", "\n".join(md))

    print(str(out_dir / "onboarding_report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
