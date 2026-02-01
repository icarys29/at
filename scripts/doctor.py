#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Plugin health check and diagnostics

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.docs_registry import build_doc_id_to_path_map, get_docs_registry_path, get_docs_require_registry, load_docs_registry  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Doctor: validate at overlay preconditions (portable, deterministic).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report to stdout.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    report: dict[str, Any] = {"version": 1, "project_root": str(project_root), "ok": True, "checks": []}

    def check(name: str, ok: bool, details: str) -> None:
        report["checks"].append({"name": name, "ok": ok, "details": details})
        if not ok:
            report["ok"] = False

    cfg_path = project_root / ".claude" / "project.yaml"
    config = load_project_config(project_root)
    if not cfg_path.exists():
        check("config.exists", False, "Missing .claude/project.yaml (run /at:init-project)")
    elif config is None:
        check("config.parse", False, "Failed to parse .claude/project.yaml")
    else:
        check("config.parse", True, "Parsed .claude/project.yaml")

    if config is not None:
        project = config.get("project") if isinstance(config, dict) else None
        if not isinstance(project, dict) or not _is_non_empty_string(project.get("name")):
            check("config.project.name", False, "project.name must be a non-empty string")
        else:
            check("config.project.name", True, f"project.name={project.get('name')!r}")

        workflow = config.get("workflow") if isinstance(config, dict) else None
        if not isinstance(workflow, dict) or not _is_non_empty_string(workflow.get("sessions_dir")):
            check("config.workflow.sessions_dir", False, "workflow.sessions_dir must be a non-empty string")
        else:
            check("config.workflow.sessions_dir", True, f"sessions_dir={workflow.get('sessions_dir')!r}")

        commands = config.get("commands") if isinstance(config, dict) else None
        if not isinstance(commands, dict) or not commands:
            check("config.commands", False, "commands must be a non-empty mapping (at least one language)")
        else:
            check("config.commands", True, f"languages={sorted(list(commands.keys()))[:10]}")

        sessions_dir = get_sessions_dir(project_root, config)
        sessions_root = project_root / sessions_dir
        check("sessions_dir.exists", sessions_root.exists(), f"expected sessions dir at {sessions_root}")

        # Docs registry (optional unless require_registry=true)
        require_registry = get_docs_require_registry(config)
        registry_path = get_docs_registry_path(config)
        registry = load_docs_registry(project_root, registry_path)
        docs_map = build_doc_id_to_path_map(registry)
        if require_registry:
            check("docs.require_registry", True, "docs.require_registry=true")
            check("docs.registry.exists", registry is not None, f"registry_path={registry_path!r}")
            check("docs.registry.docs", docs_map is not None, "registry must contain docs[] with ids and paths")
        else:
            check("docs.require_registry", True, "docs.require_registry=false (onboarding-friendly)")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1

    if not report["ok"]:
        for c in report["checks"]:
            if not c["ok"]:
                print(f"- {c['name']}: {c['details']}", file=sys.stderr)
        return 1

    _ok("config looks usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
