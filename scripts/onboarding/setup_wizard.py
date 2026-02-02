#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Setup wizard - auto-detect tooling and generate project.yaml

Version: 0.5.0
Updated: 2026-02-02

This script implements the detection logic for /at:setup skill.
It probes the project for languages, package managers, and tooling,
then returns a JSON proposal for the skill to present to the user.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir  # noqa: E402
from onboarding.onboarding_utils import detect_languages, detect_package_manager  # noqa: E402


def detect_project_type(project_root: Path) -> dict[str, Any]:
    """Detect the primary project type from marker files."""
    result: dict[str, Any] = {"type": None, "markers": []}

    # Check for marker files
    markers = [
        ("package.json", "node"),
        ("pyproject.toml", "python"),
        ("setup.py", "python"),
        ("go.mod", "go"),
        ("Cargo.toml", "rust"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ]

    for filename, proj_type in markers:
        if (project_root / filename).exists():
            result["markers"].append(filename)
            if result["type"] is None:
                result["type"] = proj_type

    return result


def detect_python_tooling(project_root: Path) -> dict[str, Any]:
    """Detect Python tooling configuration."""
    tooling: dict[str, Any] = {}

    # Linter: ruff
    if (project_root / "ruff.toml").exists() or (project_root / ".ruff.toml").exists():
        tooling["lint"] = {"detected": True, "tool": "ruff", "command": "ruff check ."}
    elif (project_root / "pyproject.toml").exists():
        content = (project_root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if "[tool.ruff]" in content:
            tooling["lint"] = {"detected": True, "tool": "ruff", "command": "ruff check ."}

    # Formatter: ruff format
    if tooling.get("lint", {}).get("tool") == "ruff":
        tooling["format"] = {"detected": True, "tool": "ruff", "command": "ruff format ."}

    # Type checker: mypy
    if (project_root / "mypy.ini").exists():
        tooling["typecheck"] = {"detected": True, "tool": "mypy", "command": "mypy ."}
    elif (project_root / "pyproject.toml").exists():
        content = (project_root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if "[tool.mypy]" in content:
            tooling["typecheck"] = {"detected": True, "tool": "mypy", "command": "mypy ."}

    # Test runner: pytest
    if (project_root / "pytest.ini").exists() or (project_root / "conftest.py").exists():
        tooling["test"] = {"detected": True, "tool": "pytest", "command": "pytest -q"}
    elif (project_root / "pyproject.toml").exists():
        content = (project_root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if "[tool.pytest" in content:
            tooling["test"] = {"detected": True, "tool": "pytest", "command": "pytest -q"}

    return tooling


def detect_node_tooling(project_root: Path) -> dict[str, Any]:
    """Detect Node/TypeScript tooling configuration."""
    tooling: dict[str, Any] = {}

    # Linter: eslint
    eslint_configs = [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs"]
    for cfg in eslint_configs:
        if (project_root / cfg).exists():
            tooling["lint"] = {"detected": True, "tool": "eslint", "command": "eslint ."}
            break

    # Formatter: prettier
    prettier_configs = [".prettierrc", ".prettierrc.js", ".prettierrc.json", "prettier.config.js"]
    for cfg in prettier_configs:
        if (project_root / cfg).exists():
            tooling["format"] = {"detected": True, "tool": "prettier", "command": "prettier --check ."}
            break

    # Type checker: TypeScript
    if (project_root / "tsconfig.json").exists():
        tooling["typecheck"] = {"detected": True, "tool": "tsc", "command": "tsc --noEmit"}

    # Test runner: check package.json scripts
    if (project_root / "package.json").exists():
        try:
            pkg = json.loads((project_root / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "test" in scripts:
                tooling["test"] = {"detected": True, "tool": "npm", "command": "npm test"}
        except Exception:
            pass

    return tooling


def detect_go_tooling(project_root: Path) -> dict[str, Any]:
    """Detect Go tooling configuration."""
    tooling: dict[str, Any] = {}

    # Linter: golangci-lint
    if (project_root / ".golangci.yml").exists() or (project_root / ".golangci.yaml").exists():
        tooling["lint"] = {"detected": True, "tool": "golangci-lint", "command": "golangci-lint run"}

    # Formatter: gofmt (always available)
    tooling["format"] = {"detected": True, "tool": "go fmt", "command": "go fmt ./..."}

    # Test runner: go test
    tooling["test"] = {"detected": True, "tool": "go test", "command": "go test ./..."}

    return tooling


def detect_rust_tooling(project_root: Path) -> dict[str, Any]:
    """Detect Rust tooling configuration."""
    tooling: dict[str, Any] = {}

    # Linter: clippy
    tooling["lint"] = {"detected": True, "tool": "clippy", "command": "cargo clippy"}

    # Formatter: rustfmt
    tooling["format"] = {"detected": True, "tool": "rustfmt", "command": "cargo fmt --check"}

    # Test runner: cargo test
    tooling["test"] = {"detected": True, "tool": "cargo test", "command": "cargo test"}

    return tooling


def generate_proposal(project_root: Path) -> dict[str, Any]:
    """Generate a configuration proposal for the project."""
    project_type = detect_project_type(project_root)
    languages = detect_languages(project_root)
    package_manager = detect_package_manager(project_root)

    # Detect tooling based on project type
    tooling: dict[str, Any] = {}
    if project_type["type"] == "python":
        tooling = detect_python_tooling(project_root)
    elif project_type["type"] == "node":
        tooling = detect_node_tooling(project_root)
    elif project_type["type"] == "go":
        tooling = detect_go_tooling(project_root)
    elif project_type["type"] == "rust":
        tooling = detect_rust_tooling(project_root)

    # Determine command prefix based on package manager
    prefix = ""
    if project_type["type"] == "python":
        if package_manager == "uv":
            prefix = "uv run "
        elif package_manager == "poetry":
            prefix = "poetry run "

    # Build proposed commands
    commands: dict[str, str] = {}
    for cmd_type in ["lint", "format", "typecheck", "test"]:
        if cmd_type in tooling and tooling[cmd_type].get("detected"):
            base_cmd = tooling[cmd_type]["command"]
            commands[cmd_type] = f"{prefix}{base_cmd}" if prefix else base_cmd

    return {
        "version": 1,
        "project_type": project_type["type"],
        "markers": project_type["markers"],
        "languages": languages,
        "package_manager": package_manager,
        "tooling": tooling,
        "proposed_commands": commands,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup wizard - detect project configuration")
    parser.add_argument("--project-dir", default=None, help="Project directory")
    parser.add_argument("--format", choices=["json", "human"], default="json", help="Output format")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    proposal = generate_proposal(project_root)

    if args.format == "json":
        print(json.dumps(proposal, indent=2))
    else:
        # Human-readable output
        print(f"Project type: {proposal['project_type'] or 'unknown'}")
        print(f"Package manager: {proposal['package_manager'] or 'not detected'}")
        print()
        print("Tooling detected:")
        for cmd_type, cmd in proposal["proposed_commands"].items():
            print(f"  ✓ {cmd_type}: {cmd}")
        for cmd_type in ["lint", "format", "typecheck", "test", "build"]:
            if cmd_type not in proposal["proposed_commands"]:
                print(f"  ✗ {cmd_type}: not detected")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
