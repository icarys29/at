#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Install a minimal "project pack" (rules + enforcement runner) into the repo overlay.

Installs:
- .claude/rules/project/README.md (if missing; already created by init-project)
- .claude/at/enforcement.json
- .claude/at/scripts/run_enforcements.py
Optionally (style=hex):
- .claude/rules/project/architecture.md
- .claude/at/architecture_boundaries.json
- .claude/at/scripts/check_architecture_boundaries.py

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now  # noqa: E402
from lib.project import detect_project_dir  # noqa: E402


def _write_if_missing(path: Path, content: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def _write_json_if_missing(path: Path, data: dict[str, Any], *, force: bool) -> str:
    if path.exists() and not force:
        return "SKIP"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return "OVERWRITE" if path.exists() and force else "CREATE"


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_template(rel_path: str) -> str:
    path = (_plugin_root() / "templates" / rel_path).resolve()
    if not path.exists():
        raise RuntimeError(f"Missing template: {path}")
    return path.read_text(encoding="utf-8")


def _render_architecture_rules_hex(domain_path: str, application_path: str, adapters_path: str) -> str:
    return (
        "# Architecture Rules (project)\n\n"
        "Style: hexagonal (ports/adapters)\n\n"
        "## Boundaries\n\n"
        f"- Domain: `{domain_path}`\n"
        f"- Application: `{application_path}`\n"
        f"- Adapters/Infra: `{adapters_path}`\n\n"
        "## Dependency Rules (enforced)\n\n"
        "- Domain MUST NOT import from Application or Adapters.\n"
        "- Application MUST NOT import from Adapters.\n"
        "- Adapters MAY import from Domain and Application.\n"
        "\n"
    )


def _basename(path: str) -> str:
    s = path.rstrip("/").rstrip("\\")
    if not s:
        return s
    return s.split("/")[-1].split("\\")[-1]


def _regex_for_python_module_segment(seg: str) -> str:
    # Match "seg" as an import segment (not a substring of another segment).
    esc = re.escape(seg)
    return rf"(^|\\.){esc}(\\.|$)"


def _regex_for_path_segment(seg: str) -> str:
    esc = re.escape(seg)
    return rf"(^|/){esc}(/|$)"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_entry(*, check_id: str, script: str, args: list[str], timeout_ms: int = 60000) -> dict[str, Any]:
    return {"id": check_id, "type": "python", "script": script, "args": args, "timeout_ms": int(timeout_ms)}


def _merge_check(checks: list[dict[str, Any]], desired: dict[str, Any], *, force: bool) -> list[dict[str, Any]]:
    check_id = desired.get("id")
    if not isinstance(check_id, str) or not check_id.strip():
        return checks
    out: list[dict[str, Any]] = []
    replaced = False
    for c in checks:
        if not isinstance(c, dict) or c.get("id") != check_id:
            out.append(c if isinstance(c, dict) else {})
            continue
        if force:
            out.append(desired)
        else:
            out.append(c)
        replaced = True
    if not replaced:
        out.append(desired)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Install minimal at project pack (rules + enforcement runner).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=".session")
    parser.add_argument("--enforcement-mode", choices=["fail", "warn"], default="warn")
    parser.add_argument("--style", choices=["none", "hex"], default="none")
    parser.add_argument("--domain-path", default=None)
    parser.add_argument("--application-path", default=None)
    parser.add_argument("--adapters-path", default=None)
    god_class_group = parser.add_mutually_exclusive_group()
    god_class_group.add_argument("--include-god-class-check", dest="include_god_class_check", action="store_true", help="Install python.god_class enforcement (SRP heuristic).")
    god_class_group.add_argument("--no-god-class-check", dest="include_god_class_check", action="store_false", help="Do not install python.god_class enforcement.")
    parser.set_defaults(include_god_class_check=True)
    parser.add_argument("--god-class-max-methods", type=int, default=25)
    parser.add_argument("--god-class-max-lines", type=int, default=400)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)

    results: list[tuple[str, str]] = []
    # Always install the enforcement runner.
    results.append(
        (
            _write_if_missing(
                project_root / ".claude" / "at" / "scripts" / "run_enforcements.py",
                _read_template("project_pack/enforcement/run_enforcements.py"),
                force=args.force,
            ),
            ".claude/at/scripts/run_enforcements.py",
        )
    )

    # Ensure executable bit best-effort.
    try:
        (project_root / ".claude" / "at" / "scripts" / "run_enforcements.py").chmod(0o755)
    except Exception:
        pass

    # Enforcement config: safe default is warn-mode with low-sensitivity checks.
    enforcement_cfg: dict[str, Any] = {"version": 1, "generated_at": utc_now(), "mode": args.enforcement_mode, "checks": []}

    # Optional: install hexagonal architecture boundary enforcement.
    if args.style == "hex":
        if not args.domain_path or not args.application_path or not args.adapters_path:
            raise RuntimeError("--domain-path, --application-path, and --adapters-path are required for --style hex")

        # Install boundary checker script.
        results.append(
            (
                _write_if_missing(
                    project_root / ".claude" / "at" / "scripts" / "check_architecture_boundaries.py",
                    _read_template("project_pack/enforcement/check_architecture_boundaries.py"),
                    force=args.force,
                ),
                ".claude/at/scripts/check_architecture_boundaries.py",
            )
        )

        try:
            (project_root / ".claude" / "at" / "scripts" / "check_architecture_boundaries.py").chmod(0o755)
        except Exception:
            pass

        rules_dir = project_root / ".claude" / "rules" / "project"
        results.append(
            (
                _write_if_missing(
                    rules_dir / "architecture.md",
                    _render_architecture_rules_hex(args.domain_path, args.application_path, args.adapters_path),
                    force=args.force,
                ),
                ".claude/rules/project/architecture.md",
            )
        )

        domain_seg = _basename(args.domain_path)
        app_seg = _basename(args.application_path)
        adapters_seg = _basename(args.adapters_path)

        sessions_glob = f"{args.sessions_dir.rstrip('/')}/**" if args.sessions_dir else ".session/**"

        boundaries_cfg = {
            "version": 1,
            "style": "hexagonal",
            "ignore_file_globs": [
                ".claude/**",
                sessions_glob,
                "node_modules/**",
                "vendor/**",
                "dist/**",
                "build/**",
                ".venv/**",
                "**/*_test.go",
                "**/*_test.py",
                "**/test_*.py",
                "**/tests/**",
                "**/__tests__/**",
                "**/*.spec.ts",
                "**/*.spec.tsx",
                "**/*.test.ts",
                "**/*.test.tsx",
            ],
            "boundaries": [
                {
                    "name": "domain",
                    "path_globs": [f"{args.domain_path.rstrip('/')}/**"],
                    "forbid_import_regex": {
                        "python": [
                            _regex_for_python_module_segment(app_seg),
                            _regex_for_python_module_segment(adapters_seg),
                        ],
                        "go": [_regex_for_path_segment(app_seg), _regex_for_path_segment(adapters_seg)],
                        "typescript": [_regex_for_path_segment(app_seg), _regex_for_path_segment(adapters_seg)],
                    },
                },
                {
                    "name": "application",
                    "path_globs": [f"{args.application_path.rstrip('/')}/**"],
                    "forbid_import_regex": {
                        "python": [_regex_for_python_module_segment(adapters_seg)],
                        "go": [_regex_for_path_segment(adapters_seg)],
                        "typescript": [_regex_for_path_segment(adapters_seg)],
                    },
                },
            ],
        }

        results.append(
            (
                _write_json_if_missing(project_root / ".claude" / "at" / "architecture_boundaries.json", boundaries_cfg, force=args.force),
                ".claude/at/architecture_boundaries.json",
            )
        )

        enforcement_cfg["checks"] = [
            _check_entry(
                check_id="architecture.boundaries",
                script=".claude/at/scripts/check_architecture_boundaries.py",
                args=["--config", ".claude/at/architecture_boundaries.json"],
                timeout_ms=60000,
            )
        ]

    # Optional: install python god-class checker.
    if args.include_god_class_check:
        results.append(
            (
                _write_if_missing(
                    project_root / ".claude" / "at" / "scripts" / "check_god_classes.py",
                    _read_template("project_pack/enforcement/check_god_classes.py"),
                    force=args.force,
                ),
                ".claude/at/scripts/check_god_classes.py",
            )
        )
        try:
            (project_root / ".claude" / "at" / "scripts" / "check_god_classes.py").chmod(0o755)
        except Exception:
            pass
        enforcement_cfg["checks"].append(
            _check_entry(
                check_id="python.god_class",
                script=".claude/at/scripts/check_god_classes.py",
                args=["--project-root", ".", "--max-methods", str(int(args.god_class_max_methods)), "--max-lines", str(int(args.god_class_max_lines))],
                timeout_ms=60000,
            )
        )

    # enforcement.json: by default we create it once and then leave it alone.
    # If the user explicitly enables checks (style!=none or include god-class), we merge in the required checks
    # without forcing an overwrite (unless --force).
    enforcement_path = project_root / ".claude" / "at" / "enforcement.json"
    desired_checks = enforcement_cfg.get("checks") if isinstance(enforcement_cfg.get("checks"), list) else []
    wants_checks = bool(desired_checks)
    if enforcement_path.exists() and not args.force and wants_checks:
        existing = _load_json(enforcement_path)
        merged: dict[str, Any] = existing if isinstance(existing, dict) else {}
        merged.setdefault("version", 1)
        merged["generated_at"] = utc_now()
        # Preserve existing mode when present.
        mode = merged.get("mode")
        if mode not in {"fail", "warn"}:
            merged["mode"] = args.enforcement_mode
        checks = merged.get("checks")
        if not isinstance(checks, list):
            checks = []
        checks_out: list[dict[str, Any]] = [c for c in checks if isinstance(c, dict)]
        for desired in desired_checks:
            if isinstance(desired, dict):
                checks_out = _merge_check(checks_out, desired, force=False)
        merged["checks"] = checks_out
        _write_json(enforcement_path, merged)
        results.append(("MERGE", ".claude/at/enforcement.json"))
    elif enforcement_path.exists() and not args.force and not wants_checks:
        results.append(("SKIP", ".claude/at/enforcement.json"))
    else:
        # If file is missing, create it. If --force, overwrite.
        results.append((_write_json_if_missing(enforcement_path, enforcement_cfg, force=True), ".claude/at/enforcement.json"))

    for status, rel in results:
        print(f"{status}\t{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
