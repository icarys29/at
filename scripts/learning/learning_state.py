#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Learning state helpers (repo-local, low-risk)

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

from pathlib import Path

from lib.project import get_learning_dir, load_project_config


def learning_root(project_root: Path) -> Path:
    cfg = load_project_config(project_root) or {}
    d = get_learning_dir(project_root, cfg)
    return (project_root / d).resolve()


def ensure_learning_dirs(project_root: Path) -> Path:
    root = learning_root(project_root)
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    (root / "adr").mkdir(parents=True, exist_ok=True)
    (root / "learnings").mkdir(parents=True, exist_ok=True)
    return root
