#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Path policy utilities

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.simple_yaml import load_minimal_yaml

DEFAULT_FORBID_SECRETS_GLOBS = [
    ".env",
    ".env.*",
    "secrets/**",
]

# Allowlist for common non-secret templates (even if forbid globs include ".env.*").
ALLOW_SECRET_TEMPLATES = {
    ".env.sample",
    ".env.example",
    ".env.template",
}



def normalize_repo_relative_posix_path(value: str) -> str | None:
    """
    Return a normalized repo-relative POSIX path (no leading './').
    Reject absolute paths, home paths, and path traversal.
    """
    v = value.strip().replace("\\", "/")
    if not v:
        return None
    if v.startswith(("/", "~")):
        return None
    while v.startswith("./"):
        v = v[2:]
    parts = [p for p in v.split("/") if p not in {"", "."}]
    if any(p == ".." for p in parts):
        return None
    return "/".join(parts) if parts else None


def resolve_path_under_project_root(project_root: Path, rel_path: str) -> Path | None:
    """
    Resolve a repo-relative path and ensure it stays under the project root
    after resolving symlinks.
    """
    norm = normalize_repo_relative_posix_path(rel_path)
    if not norm:
        return None
    root = project_root.resolve()
    try:
        resolved = (root / norm).resolve()
    except Exception:
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def matches_any_glob(rel_path: str, patterns: list[str]) -> bool:
    p = Path(rel_path)
    return any(p.match(pat) for pat in patterns if isinstance(pat, str) and pat)


def is_allowed_secret_template(rel_path: str) -> bool:
    name = Path(rel_path).name
    if name in ALLOW_SECRET_TEMPLATES:
        return True
    # Allow nested templates too (e.g. app/server/.env.sample)
    if rel_path.endswith("/.env.sample") or rel_path.endswith("/.env.example") or rel_path.endswith("/.env.template"):
        return True
    return False


def is_forbidden_path(rel_path: str, forbid_globs: list[str]) -> bool:
    if is_allowed_secret_template(rel_path):
        return False
    return matches_any_glob(rel_path, forbid_globs)


def forbid_secrets_globs_from_project_yaml(project_root: Path) -> list[str]:
    cfg = project_root / ".claude" / "project.yaml"
    if not cfg.exists():
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    try:
        data = load_minimal_yaml(cfg.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    policies = data.get("policies") if isinstance(data, dict) else None
    if not isinstance(policies, dict):
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    globs = policies.get("forbid_secrets_globs")
    if not isinstance(globs, list):
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    out = [str(x) for x in globs if isinstance(x, str) and x.strip()]
    return out or DEFAULT_FORBID_SECRETS_GLOBS[:]


def forbid_globs_from_project_config(config: dict[str, Any] | None) -> list[str]:
    """Return `policies.forbid_secrets_globs` from config, with defaults."""
    if not config or not isinstance(config, dict):
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    policies = config.get("policies")
    if not isinstance(policies, dict):
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    globs = policies.get("forbid_secrets_globs")
    if not isinstance(globs, list):
        return DEFAULT_FORBID_SECRETS_GLOBS[:]
    out = [str(x) for x in globs if isinstance(x, str) and x.strip()]
    return out or DEFAULT_FORBID_SECRETS_GLOBS[:]
