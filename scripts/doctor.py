#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Plugin health check and diagnostics

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.docs_registry import build_doc_id_to_path_map, get_docs_registry_path, get_docs_require_registry, load_docs_registry  # noqa: E402
from lib.project import detect_project_dir, get_plugin_root, get_sessions_dir, load_project_config  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())





def _first_token(cmd: str) -> str | None:
    parts = cmd.strip().split()
    return parts[0] if parts else None


def _tool_exists(token: str) -> bool:
    if not token:
        return False
    if token.startswith("./") or token.startswith("../") or token.startswith("/"):
        return Path(token).expanduser().exists()
    return shutil.which(token) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Doctor: validate at overlay preconditions (portable, deterministic).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report to stdout.")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    report: dict[str, Any] = {"version": 2, "project_root": str(project_root), "ok": True, "warnings": 0, "checks": []}

    def check(name: str, ok: bool, details: str, *, severity: str = "error") -> None:
        if severity not in {"error", "warning"}:
            severity = "error"
        report["checks"].append({"name": name, "ok": ok, "severity": severity, "details": details})
        if not ok and severity == "error":
            report["ok"] = False
        if not ok and severity == "warning":
            report["warnings"] = int(report.get("warnings") or 0) + 1

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

        # Tooling preflight
        check("tool.uv", shutil.which("uv") is not None, "uv must be installed and on PATH (https://astral.sh/uv/)")

        # Quality commands: best-effort check that first tokens exist on PATH.
        cmds = config.get("commands") if isinstance(config.get("commands"), dict) else {}
        if isinstance(cmds, dict):
            missing: list[str] = []
            for lang, spec in cmds.items():
                if not isinstance(spec, dict):
                    continue
                for key in ("format", "lint", "typecheck", "test", "build", "e2e"):
                    raw = spec.get(key)
                    if not isinstance(raw, str) or not raw.strip():
                        continue
                    tok = _first_token(raw)
                    if not tok or not _tool_exists(tok):
                        missing.append(f"{lang}.{key}:{tok or '<empty>'}")
            if missing:
                check("commands.tools", False, "Missing command tools (first token): " + ", ".join(missing[:20]), severity="warning")
            else:
                check("commands.tools", True, "Configured command first tokens appear available", severity="warning")

        # LSP: best-effort check that server commands exist when enabled.
        lsp_cfg = config.get("lsp") if isinstance(config.get("lsp"), dict) else {}
        lsp_enabled = bool(lsp_cfg.get("enabled") is True)
        if lsp_enabled:
            plugin_root = get_plugin_root()
            lsp_path = plugin_root / ".lsp.json"
            if not lsp_path.exists():
                check("lsp.config", False, f"lsp.enabled=true but missing {lsp_path}", severity="warning")
            else:
                try:
                    lsp_data = json.loads(lsp_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    check("lsp.config", False, f"Invalid .lsp.json ({exc})", severity="warning")
                    lsp_data = {}
                if isinstance(lsp_data, dict):
                    proj = config.get("project") if isinstance(config.get("project"), dict) else {}
                    primary: list[str] = []
                    if isinstance(proj, dict) and isinstance(proj.get("primary_languages"), list):
                        primary = [x for x in proj.get("primary_languages") if isinstance(x, str)]
                    langs = primary or list(lsp_data.keys())
                    missing_servers: list[str] = []
                    for lang in langs[:20]:
                        entry = lsp_data.get(lang)
                        if not isinstance(entry, dict):
                            continue
                        cmd = entry.get("command")
                        if isinstance(cmd, str) and cmd.strip() and shutil.which(cmd.strip()) is None:
                            missing_servers.append(f"{lang}:{cmd.strip()}")
                    if missing_servers:
                        check("lsp.servers", False, "Missing LSP server commands: " + ", ".join(missing_servers[:20]), severity="warning")
                    else:
                        check("lsp.servers", True, "LSP server commands appear available", severity="warning")

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
            if not c.get("ok") and c.get("severity") != "warning":
                print(f"- {c['name']}: {c['details']}", file=sys.stderr)
        return 1

    warnings = [c for c in report["checks"] if isinstance(c, dict) and c.get("severity") == "warning" and not c.get("ok")]
    if warnings:
        print("WARN:")
        for c in warnings[:50]:
            print(f"- {c.get('name')}: {c.get('details')}")

    _ok("config looks usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
