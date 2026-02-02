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

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_plugin_root, load_project_config  # noqa: E402
from onboarding.onboarding_utils import detect_languages, render_project_yaml, suggest_commands  # noqa: E402


def _read_template(plugin_root: Path, rel: str) -> str:
    p = (plugin_root / "templates" / rel).resolve()
    if not p.exists():
        raise RuntimeError(f"Missing template: {p}")
    return p.read_text(encoding="utf-8")






def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _has_managed_hook(settings: dict[str, Any], *, managed_by: str) -> bool:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for items in hooks.values():
        if not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            hs = entry.get("hooks")
            if not isinstance(hs, list):
                continue
            for h in hs:
                if not isinstance(h, dict):
                    continue
                meta = h.get("metadata")
                if isinstance(meta, dict) and meta.get("managed_by") == managed_by:
                    return True
    return False


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
    existing_cfg = load_project_config(project_root)

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

    overlay_exists = bool((project_root / ".claude" / "project.yaml").exists())
    docs_registry_exists = bool((project_root / "docs" / "DOCUMENTATION_REGISTRY.json").exists())
    settings_local = _load_json(project_root / ".claude" / "settings.local.json")
    settings_team = _load_json(project_root / ".claude" / "settings.json")
    hooks_status = {
        "policy_hooks": _has_managed_hook(settings_local, managed_by="at-policy-hooks") or _has_managed_hook(settings_team, managed_by="at-policy-hooks"),
        "audit_hooks": _has_managed_hook(settings_local, managed_by="at-audit-hooks") or _has_managed_hook(settings_team, managed_by="at-audit-hooks"),
        "docs_keeper_hooks": _has_managed_hook(settings_local, managed_by="docs-keeper-hooks") or _has_managed_hook(
            settings_team, managed_by="docs-keeper-hooks"
        ),
        "learning_hooks": _has_managed_hook(settings_local, managed_by="at-learning-hooks") or _has_managed_hook(settings_team, managed_by="at-learning-hooks"),
        "ux_nudges_hooks": _has_managed_hook(settings_local, managed_by="at-ux-nudges-hooks") or _has_managed_hook(
            settings_team, managed_by="at-ux-nudges-hooks"
        ),
    }

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
        "existing": {
            "overlay_present": overlay_exists,
            "docs_registry_present": docs_registry_exists,
            "project_yaml_parse_ok": bool(existing_cfg is not None),
            "hooks": hooks_status,
        },
        "proposed": {
            "project_yaml_path": ".claude/project.yaml",
            "project_yaml_preview_head": proposed_project_yaml.splitlines()[:120],
        },
        "planned_creates": sorted(set(planned_creates)),
        "notes": [
            "This is a proposal only. Use /at:onboard --apply to write overlay + docs with backups.",
            "If this repo already has an at overlay, prefer /at:upgrade-project unless you explicitly want to overwrite onboarding files (--force).",
            "Hooks are optional and should be installed deliberately (policy/audit/docs-keeper/learning/UX nudges).",
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
    md.append("## Existing state")
    md.append("")
    md.append(f"- overlay_present: `{str(report['existing']['overlay_present']).lower()}`")
    md.append(f"- docs_registry_present: `{str(report['existing']['docs_registry_present']).lower()}`")
    md.append(f"- project_yaml_parse_ok: `{str(report['existing']['project_yaml_parse_ok']).lower()}`")
    md.append("")
    md.append("### Hooks (project)")
    md.append("")
    hooks = report["existing"]["hooks"]
    md.append(f"- policy_hooks: `{str(bool(hooks.get('policy_hooks'))).lower()}`")
    md.append(f"- audit_hooks: `{str(bool(hooks.get('audit_hooks'))).lower()}`")
    md.append(f"- docs_keeper_hooks: `{str(bool(hooks.get('docs_keeper_hooks'))).lower()}`")
    md.append(f"- learning_hooks: `{str(bool(hooks.get('learning_hooks'))).lower()}`")
    md.append(f"- ux_nudges_hooks: `{str(bool(hooks.get('ux_nudges_hooks'))).lower()}`")
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
    md.append("## Suggested next steps")
    md.append("")
    if report["existing"]["overlay_present"]:
        md.append("- If you already use at in this repo: run `/at:upgrade-project` (safe dry-run default).")
    else:
        md.append("- Apply the overlay: `/at:onboard --apply` (creates backups).")
    if not hooks.get("policy_hooks"):
        md.append("- Optional (recommended): install policy hooks: `/at:setup-policy-hooks --scope project`")
    if not hooks.get("audit_hooks"):
        md.append("- Optional: install audit hooks: `/at:setup-audit-hooks --scope project`")
    if not hooks.get("docs_keeper_hooks"):
        md.append("- Optional (teams): install docs-keeper hooks: `/at:setup-docs-keeper-hooks --scope project`")
    md.append("")
    write_text(out_dir / "onboarding_report.md", "\n".join(md))

    print(str(out_dir / "onboarding_report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
