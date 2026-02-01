#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs registry helpers

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def get_docs_registry_path(config: dict[str, Any] | None) -> str:
    docs_cfg = config.get("docs") if isinstance(config, dict) else None
    if isinstance(docs_cfg, dict) and isinstance(docs_cfg.get("registry_path"), str) and docs_cfg.get("registry_path"):
        return str(docs_cfg["registry_path"]).strip()
    return "docs/DOCUMENTATION_REGISTRY.json"


def get_docs_require_registry(config: dict[str, Any] | None) -> bool:
    docs_cfg = config.get("docs") if isinstance(config, dict) else None
    if isinstance(docs_cfg, dict) and isinstance(docs_cfg.get("require_registry"), bool):
        return bool(docs_cfg.get("require_registry"))
    return False


def load_docs_registry(project_root: Path, registry_path: str) -> dict[str, Any] | None:
    reg = (project_root / registry_path).resolve()
    if not reg.exists():
        return None
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def build_doc_id_to_path_map(registry: dict[str, Any] | None) -> dict[str, str] | None:
    if not registry or not isinstance(registry, dict):
        return None
    docs = registry.get("docs")
    gen = registry.get("generated_artifacts")
    if not isinstance(docs, list) and not isinstance(gen, list):
        return None
    out: dict[str, str] = {}
    for item in (docs or []):
        if not isinstance(item, dict):
            continue
        doc_id = item.get("id")
        path = item.get("path")
        if isinstance(doc_id, str) and doc_id.strip() and isinstance(path, str) and path.strip():
            out[doc_id.strip()] = path.strip()
    for item in (gen or []):
        if not isinstance(item, dict):
            continue
        doc_id = item.get("id")
        path = item.get("path")
        if isinstance(doc_id, str) and doc_id.strip() and isinstance(path, str) and path.strip():
            out[doc_id.strip()] = path.strip()
    return out or None
