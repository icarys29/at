#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Self-audit (deterministic integrity checks for the plugin)

This is intended to be a deterministic gate that validates:
- referenced scripts exist (hooks/agents/skills)
- version metadata discipline is consistent
- actions contract enums align across schema + validator
- validator fixtures behave as expected

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now_full, write_json, write_text  # noqa: E402
from lib.project import get_plugin_root  # noqa: E402
from validate.actions_validator import ALLOWED_OWNERS, ALLOWED_WORKFLOWS, validate_actions_file  # noqa: E402


@dataclass(frozen=True)
class Issue:
    severity: str  # error|warning
    check_id: str
    message: str
    paths: list[str]


def _iter_files(root: Path, *, patterns: list[str]) -> Iterable[Path]:
    for pat in patterns:
        yield from root.rglob(pat)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _extract_script_refs(text: str) -> list[str]:
    """
    Extract `${CLAUDE_PLUGIN_ROOT}/scripts/...` references from markdown/json-ish text.
    """
    refs: list[str] = []
    for m in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT\}/(?P<rel>scripts/[A-Za-z0-9_./-]+\.py)\b", text):
        refs.append(m.group("rel"))
    return refs


def _has_version_header_python(text: str) -> bool:
    head = "\n".join(text.splitlines()[:80])
    return (
        "at:" in head
        and re.search(r"^Version:\s*\S+", head, flags=re.MULTILINE)
        and re.search(r"^Updated:\s*\S+", head, flags=re.MULTILINE)
    )


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fm = text[4:end]
    out: dict[str, str] = {}
    for line in fm.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v:
            out[k] = v
    return out


def _schema_get(schema: dict[str, Any], path: list[str]) -> Any:
    cur: Any = schema
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _write_reports(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "self_audit_report.json", report)

    md: list[str] = []
    md.append("# Self Audit Report (at)")
    md.append("")
    md.append(f"- generated_at: `{report.get('generated_at','')}`")
    md.append(f"- ok: `{str(report.get('ok', False)).lower()}`")
    md.append("")
    checks = report.get("checks")
    if isinstance(checks, list) and checks:
        md.append("## Checks")
        md.append("")
        for c in checks:
            if not isinstance(c, dict):
                continue
            md.append(f"- `{c.get('id','')}`: `{'ok' if c.get('ok') else 'fail'}` — {c.get('details','')}")
        md.append("")
    issues = report.get("issues")
    if isinstance(issues, list) and issues:
        md.append("## Issues")
        md.append("")
        for it in issues[:200]:
            if not isinstance(it, dict):
                continue
            paths = it.get("paths") if isinstance(it.get("paths"), list) else []
            tail = f" — {', '.join(paths[:6])}{' …' if len(paths) > 6 else ''}" if paths else ""
            md.append(f"- `{it.get('severity','')}` `{it.get('check_id','')}` — {it.get('message','')}{tail}")
        md.append("")
    write_text(out_dir / "self_audit_report.md", "\n".join(md))


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-audit at plugin integrity (deterministic gate).")
    parser.add_argument("--out-dir", default=None, help="Optional output directory for {json,md} report.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()

    plugin_root = get_plugin_root()
    issues: list[Issue] = []
    checks: list[dict[str, Any]] = []

    def check(check_id: str, ok: bool, details: str, *, paths: list[str] | None = None, severity: str = "error") -> None:
        checks.append({"id": check_id, "ok": ok, "details": details})
        if not ok:
            issues.append(Issue(severity=severity, check_id=check_id, message=details, paths=paths or []))

    # 1) Version consistency
    plugin_json = _load_json(plugin_root / "plugin.json") or {}
    version_manifest = plugin_json.get("version") if isinstance(plugin_json.get("version"), str) else None
    version_file = (plugin_root / "VERSION").read_text(encoding="utf-8", errors="ignore").strip() if (plugin_root / "VERSION").exists() else ""
    ok_version = bool(version_manifest) and version_manifest == version_file
    check("plugin.version_consistency", ok_version, f"plugin.json.version={version_manifest!r} VERSION={version_file!r}")

    # 2) Hook script references resolve
    hooks_json = _load_json(plugin_root / "hooks" / "hooks.json")
    missing_hook_scripts: list[str] = []
    if hooks_json and isinstance(hooks_json.get("hooks"), dict):
        for ev, items in (hooks_json.get("hooks") or {}).items():
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                hs = it.get("hooks")
                if not isinstance(hs, list):
                    continue
                for h in hs:
                    if not isinstance(h, dict):
                        continue
                    cmd = h.get("command")
                    if not isinstance(cmd, str):
                        continue
                    for rel in _extract_script_refs(cmd):
                        if not (plugin_root / rel).exists():
                            missing_hook_scripts.append(f"{ev}: {rel}")
    check("hooks.script_refs_exist", len(missing_hook_scripts) == 0, "all hook script references exist", paths=missing_hook_scripts)

    # 3) Agent/skill script references resolve
    md_paths = list(_iter_files(plugin_root / "agents", patterns=["*.md"])) + list(_iter_files(plugin_root / "skills", patterns=["SKILL.md"]))
    missing_md_refs: list[str] = []
    for p in md_paths:
        for rel in _extract_script_refs(_read_text(p)):
            if not (plugin_root / rel).exists():
                missing_md_refs.append(f"{p.relative_to(plugin_root)}: {rel}")
    check("markdown.script_refs_exist", len(missing_md_refs) == 0, "all agents/skills script references exist", paths=missing_md_refs)

    # 4) Version metadata discipline
    py_missing: list[str] = []
    for p in _iter_files(plugin_root / "scripts", patterns=["*.py"]):
        if p.name == "__init__.py":
            continue
        if not _has_version_header_python(_read_text(p)):
            py_missing.append(str(p.relative_to(plugin_root)))
    check("versioning.python_headers", len(py_missing) == 0, "all scripts have at Version/Updated header", paths=py_missing)

    md_missing: list[str] = []
    for p in md_paths:
        fm = _parse_frontmatter(_read_text(p))
        if not fm:
            md_missing.append(str(p.relative_to(plugin_root)))
            continue
        if "version" not in fm or "updated" not in fm:
            md_missing.append(str(p.relative_to(plugin_root)))
    check("versioning.frontmatter", len(md_missing) == 0, "all agents/skills have version+updated frontmatter", paths=md_missing, severity="warning")

    # 5) Contract drift prevention: schema enums align with validator enums.
    schema = _load_json(plugin_root / "schemas" / "actions.schema.json") or {}
    schema_workflows = _schema_get(schema, ["properties", "workflow", "enum"])
    schema_owners = _schema_get(schema, ["$defs", "task", "properties", "owner", "enum"])
    ok_workflows = isinstance(schema_workflows, list) and set(schema_workflows) == set(ALLOWED_WORKFLOWS)
    ok_owners = isinstance(schema_owners, list) and set(schema_owners) == set(ALLOWED_OWNERS)
    check("contracts.schema_workflows", ok_workflows, f"schema workflows match validator: {sorted(list(ALLOWED_WORKFLOWS))}")
    check("contracts.schema_owners", ok_owners, f"schema owners match validator: {sorted(list(ALLOWED_OWNERS))}")

    # 6) Validator fixtures
    fixtures_manifest = _load_json(plugin_root / "scripts" / "validate" / "fixtures" / "actions_fixtures.json") or {}
    fixtures = fixtures_manifest.get("fixtures") if isinstance(fixtures_manifest.get("fixtures"), list) else []
    fixture_issues: list[str] = []
    for it in fixtures:
        if not isinstance(it, dict):
            continue
        rel = it.get("path")
        valid = it.get("valid")
        if not isinstance(rel, str) or not isinstance(valid, bool):
            continue
        p = (plugin_root / rel).resolve()
        if not p.exists():
            fixture_issues.append(f"{rel}: missing fixture file")
            continue
        errors = validate_actions_file(p, project_root=plugin_root)
        got_valid = len(errors) == 0
        if got_valid != valid:
            fixture_issues.append(f"{rel}: expected valid={valid}, got valid={got_valid}")
            continue
        expected_subs = it.get("expect_error_substrings")
        if not valid and isinstance(expected_subs, list) and expected_subs:
            msg_blob = "\n".join([f"{e.path}: {e.message}" for e in errors])
            if not any(isinstance(s, str) and s in msg_blob for s in expected_subs):
                fixture_issues.append(f"{rel}: expected error substrings not found: {expected_subs!r}")
    check("contracts.validator_fixtures", len(fixture_issues) == 0, "validator fixtures behave as expected", paths=fixture_issues)

    ok = not any(i.severity == "error" for i in issues)
    if args.strict:
        ok = ok and not any(i.severity == "warning" for i in issues)

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now_full(),
        "ok": ok,
        "plugin_root": str(plugin_root).replace("\\", "/"),
        "plugin": {"name": plugin_json.get("name"), "version": version_manifest},
        "checks": checks,
        "issues": [i.__dict__ for i in issues],
    }

    if args.out_dir:
        out_dir = Path(args.out_dir).expanduser()
        _write_reports(out_dir, report)

    if not ok:
        # Print a minimal failure summary (machine-correctable).
        print("FAIL: at self-audit found issues.", file=sys.stderr)
        for it in issues[:50]:
            sev = it.severity.upper()
            msg = it.message
            print(f"- {sev}: {it.check_id}: {msg}", file=sys.stderr)
        return 1

    print("OK: at self-audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
