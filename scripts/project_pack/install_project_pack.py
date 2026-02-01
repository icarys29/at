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

Version: 0.1.0
Updated: 2026-02-01
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Install minimal at project pack (rules + enforcement runner).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=".session")
    parser.add_argument("--enforcement-mode", choices=["fail", "warn"], default="fail")
    parser.add_argument("--style", choices=["none", "hex"], default="none")
    parser.add_argument("--domain-path", default=None)
    parser.add_argument("--application-path", default=None)
    parser.add_argument("--adapters-path", default=None)
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

    # Enforcement config: safe default is "no checks" until configured.
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
            {
                "id": "architecture.boundaries",
                "type": "python",
                "script": ".claude/at/scripts/check_architecture_boundaries.py",
                "args": ["--config", ".claude/at/architecture_boundaries.json"],
                "timeout_ms": 60000,
            }
        ]

    results.append((_write_json_if_missing(project_root / ".claude" / "at" / "enforcement.json", enforcement_cfg, force=args.force), ".claude/at/enforcement.json"))

    for status, rel in results:
        print(f"{status}\t{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
