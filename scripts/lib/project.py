#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Project detection and configuration utilities

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib.simple_yaml import load_minimal_yaml


def detect_project_dir(explicit: str | None = None) -> Path:
    """
    Detect project directory from explicit path, env, or cwd.

    Resolution order:
    1) Explicit path if provided
    2) CLAUDE_PROJECT_DIR environment variable
    3) Current working directory
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        return Path(env_project).resolve()
    return Path.cwd().resolve()


def load_project_config(project_root: Path) -> dict[str, Any] | None:
    """Load and parse `.claude/project.yaml` (returns None if missing/invalid)."""
    cfg = project_root / ".claude" / "project.yaml"
    if not cfg.exists():
        return None
    try:
        data = load_minimal_yaml(cfg.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_sessions_dir(project_root: Path, config: dict[str, Any] | None = None) -> str:
    """Get `workflow.sessions_dir` from config, default `.session`."""
    if config is None:
        config = load_project_config(project_root)
    if config:
        workflow = config.get("workflow")
        if isinstance(workflow, dict):
            sessions_dir = workflow.get("sessions_dir")
            if isinstance(sessions_dir, str) and sessions_dir.strip():
                return sessions_dir.strip()
    return ".session"


def get_learning_dir(project_root: Path, config: dict[str, Any] | None = None) -> str:
    """Get `learning.dir` from config, default `.claude/agent-team/learning`."""
    if config is None:
        config = load_project_config(project_root)
    if config:
        learning = config.get("learning")
        if isinstance(learning, dict):
            d = learning.get("dir")
            if isinstance(d, str) and d.strip():
                return d.strip()
    return ".claude/agent-team/learning"


def get_plugin_root() -> Path:
    """
    Get the plugin root directory.

    Resolution order:
    1) CLAUDE_PLUGIN_ROOT environment variable
    2) Relative to this file (scripts/lib/project.py -> plugin root)
    """
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def load_plugin_manifest(plugin_root: Path | None = None) -> dict[str, Any] | None:
    """Load plugin `plugin.json` (returns None if missing/invalid)."""
    if plugin_root is None:
        plugin_root = get_plugin_root()
    manifest = plugin_root / "plugin.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def get_plugin_version(plugin_root: Path | None = None) -> str:
    """Get plugin version from `plugin.json` (fallback to `VERSION`)."""
    if plugin_root is None:
        plugin_root = get_plugin_root()
    manifest = load_plugin_manifest(plugin_root)
    if manifest and isinstance(manifest.get("version"), str):
        v = manifest["version"].strip()
        if v:
            return v
    version_file = plugin_root / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"
