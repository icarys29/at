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
from lib.simple_yaml import load_minimal_yaml  # noqa: E402
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


def _extract_frontmatter_block(text: str) -> str | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    return "\n".join(lines[1:end]) + "\n"


def _count_indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _escape_yaml_double_quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _collapse_block_scalars(frontmatter: str) -> str:
    """
    Convert YAML block scalars (>, |) into quoted scalar strings so they can be
    parsed by lib.simple_yaml.load_minimal_yaml (which intentionally supports a
    smaller YAML subset).
    """
    lines = frontmatter.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.lstrip(" ")
        indent = _count_indent(raw)
        # Preserve comments/blank lines for stable error reporting.
        if not stripped or stripped.startswith("#"):
            out.append(raw)
            i += 1
            continue
        if ":" not in stripped:
            out.append(raw)
            i += 1
            continue
        key, rest = stripped.split(":", 1)
        key = key.strip()
        rest = rest.lstrip(" ")
        if key and rest and rest[0] in {"|", ">"}:
            style = rest[0]
            j = i + 1
            block_lines: list[str] = []
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    block_lines.append("")
                    j += 1
                    continue
                nxt_indent = _count_indent(nxt)
                if nxt_indent <= indent:
                    break
                block_lines.append(nxt)
                j += 1
            content_indent = None
            for bl in block_lines:
                if not isinstance(bl, str) or not bl.strip():
                    continue
                content_indent = _count_indent(bl) if content_indent is None else min(content_indent, _count_indent(bl))
            norm: list[str] = []
            for bl in block_lines:
                if not bl:
                    norm.append("")
                    continue
                if content_indent is None:
                    norm.append(bl.lstrip(" "))
                else:
                    norm.append(bl[content_indent:] if len(bl) >= content_indent else bl.lstrip(" "))
            if style == "|":
                value = "\n".join(norm).strip()
            else:
                value = " ".join([x.strip() for x in norm if x.strip()]).strip()
            out.append(" " * indent + f'{key}: "{_escape_yaml_double_quoted(value)}"')
            i = j
            continue

        out.append(raw)
        i += 1
    return "\n".join(out) + "\n"


def _parse_frontmatter_yaml(text: str) -> tuple[dict[str, Any] | None, str | None]:
    fm = _extract_frontmatter_block(text)
    if fm is None:
        return None, "missing frontmatter"
    try:
        return load_minimal_yaml(_collapse_block_scalars(fm)), None
    except Exception as exc:
        return None, str(exc)


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

    # 1) Version consistency (VERSION + root plugin.json + canonical .claude-plugin/plugin.json)
    root_manifest = _load_json(plugin_root / "plugin.json") or {}
    canonical_manifest = _load_json(plugin_root / ".claude-plugin" / "plugin.json") or {}
    version_root = root_manifest.get("version") if isinstance(root_manifest.get("version"), str) else None
    version_canonical = canonical_manifest.get("version") if isinstance(canonical_manifest.get("version"), str) else None
    version_file = (plugin_root / "VERSION").read_text(encoding="utf-8", errors="ignore").strip() if (plugin_root / "VERSION").exists() else ""
    ok_version = bool(version_root) and bool(version_canonical) and version_root == version_file == version_canonical
    check(
        "plugin.version_consistency",
        ok_version,
        f"root.plugin.json.version={version_root!r} canonical..claude-plugin/plugin.json.version={version_canonical!r} VERSION={version_file!r}",
    )

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
    frontmatter_invalid: list[str] = []
    for p in md_paths:
        fm, err = _parse_frontmatter_yaml(_read_text(p))
        if err:
            frontmatter_invalid.append(f"{p.relative_to(plugin_root)}: {err}")
            continue
        if not isinstance(fm, dict):
            frontmatter_invalid.append(f"{p.relative_to(plugin_root)}: invalid YAML (non-mapping)")
            continue
        if "version" not in fm or "updated" not in fm:
            md_missing.append(str(p.relative_to(plugin_root)))
    check("frontmatter.yaml_valid", len(frontmatter_invalid) == 0, "all skills/agents frontmatter parses as YAML", paths=frontmatter_invalid)
    check("versioning.frontmatter", len(md_missing) == 0, "all agents/skills have version+updated frontmatter", paths=md_missing, severity="warning")

    # 5) Contract drift prevention: schema enums align with validator enums.
    schema = _load_json(plugin_root / "schemas" / "actions.schema.json") or {}
    schema_workflows = _schema_get(schema, ["properties", "workflow", "enum"])
    schema_owners = _schema_get(schema, ["$defs", "task", "properties", "owner", "enum"])
    ok_workflows = isinstance(schema_workflows, list) and set(schema_workflows) == set(ALLOWED_WORKFLOWS)
    ok_owners = isinstance(schema_owners, list) and set(schema_owners) == set(ALLOWED_OWNERS)
    check("contracts.schema_workflows", ok_workflows, f"schema workflows match validator: {sorted(list(ALLOWED_WORKFLOWS))}")
    check("contracts.schema_owners", ok_owners, f"schema owners match validator: {sorted(list(ALLOWED_OWNERS))}")

    # 5.5) Contract completeness: every allowed owner has a corresponding agent definition.
    missing_owner_agents: list[str] = []
    for owner in sorted(ALLOWED_OWNERS):
        p = plugin_root / "agents" / f"{owner}.md"
        if not p.exists():
            missing_owner_agents.append(f"agents/{owner}.md")
    check("contracts.owner_agents_exist", len(missing_owner_agents) == 0, "all schema owners have agent definitions", paths=missing_owner_agents)

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
        "plugin": {"name": root_manifest.get("name"), "version": version_root},
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
