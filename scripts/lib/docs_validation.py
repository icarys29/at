#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Docs registry validation utilities (v2)

Designed to be shared by docs gate, docs lint, and hooks.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from lib.path_policy import normalize_repo_relative_posix_path, resolve_path_under_project_root


def validate_registry_v2(
    project_root: Path,
    *,
    registry_path: str,
    registry: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "registry_path": registry_path,
        "docs_total": 0,
        "docs_missing_files": 0,
        "docs_missing_when": 0,
        "docs_missing_required_fields": 0,
        "tiers": {},
        "types": {},
    }
    type_map: dict[str, dict[str, Any]] = {}

    if registry is None:
        issues.append({"severity": "error", "message": "docs registry missing or invalid JSON"})
        return (issues, summary, type_map)

    if registry.get("version") != 2:
        issues.append({"severity": "error", "message": f"registry.version must be 2 (got {registry.get('version')!r})"})
        return (issues, summary, type_map)

    rid = registry.get("registry_id")
    if not isinstance(rid, str) or not rid.strip():
        issues.append({"severity": "error", "message": "registry.registry_id must be a non-empty string"})

    gen = registry.get("generated_artifacts")
    if not isinstance(gen, list) or not gen:
        issues.append({"severity": "error", "message": "registry.generated_artifacts must be a non-empty array"})
    else:
        for it in gen[:200]:
            if not isinstance(it, dict):
                continue
            gid = it.get("id")
            gpath = it.get("path")
            src = it.get("source")
            generator = it.get("generator")
            mode = it.get("mode")
            if not isinstance(gid, str) or not gid.strip():
                issues.append({"severity": "error", "message": "generated_artifacts entry missing id"})
            if not isinstance(gpath, str) or not gpath.strip():
                issues.append({"severity": "error", "message": f"generated_artifacts[{gid!r}].path must be a non-empty string"})
            if not isinstance(src, str) or not src.strip():
                issues.append({"severity": "error", "message": f"generated_artifacts[{gid!r}].source must be a non-empty string"})
            if not isinstance(generator, str) or not generator.strip():
                issues.append({"severity": "error", "message": f"generated_artifacts[{gid!r}].generator must be a non-empty string"})
            if mode not in {"overwrite"}:
                issues.append({"severity": "error", "message": f"generated_artifacts[{gid!r}].mode must be 'overwrite'"})

    doc_types = registry.get("doc_types")
    if not isinstance(doc_types, list) or not doc_types:
        issues.append({"severity": "error", "message": "registry.doc_types must be a non-empty array"})
    else:
        for it in doc_types[:200]:
            if not isinstance(it, dict):
                continue
            t = it.get("type")
            prefix = it.get("prefix")
            dir_ = it.get("dir")
            template = it.get("template")
            if not isinstance(t, str) or not t.strip():
                issues.append({"severity": "error", "message": "doc_types entry missing type"})
                continue
            if t.strip() in type_map:
                issues.append({"severity": "error", "message": f"duplicate doc type: {t.strip()!r}"})
                continue
            if not isinstance(prefix, str) or not prefix.strip():
                issues.append({"severity": "error", "message": f"doc_types[{t.strip()}].prefix must be a non-empty string"})
                continue
            if not isinstance(dir_, str) or not dir_.strip():
                issues.append({"severity": "error", "message": f"doc_types[{t.strip()}].dir must be a non-empty string"})
                continue
            if not isinstance(template, str) or not template.strip():
                issues.append({"severity": "error", "message": f"doc_types[{t.strip()}].template must be a non-empty string"})
                continue
            tpl_norm = normalize_repo_relative_posix_path(template.strip())
            if not tpl_norm:
                issues.append({"severity": "error", "message": f"invalid template path for doc type {t.strip()!r}: {template!r}"})
                continue
            tpl_path = resolve_path_under_project_root(project_root, tpl_norm)
            if tpl_path is None or not tpl_path.exists():
                issues.append({"severity": "error", "message": f"missing template file for doc type {t.strip()!r}: {tpl_norm}"})
                continue
            type_map[t.strip()] = it

    docs = registry.get("docs")
    if not isinstance(docs, list) or not docs:
        issues.append({"severity": "error", "message": "registry.docs must be a non-empty array"})
        return (issues, summary, type_map)

    seen_ids: set[str] = set()
    tiers: dict[str, int] = {}
    types: dict[str, int] = {}
    missing_files = 0
    missing_when = 0
    missing_required_fields = 0
    for item in docs[:2000]:
        if not isinstance(item, dict):
            continue

        doc_id = item.get("id")
        doc_type = item.get("type")
        path = item.get("path")
        tier = item.get("tier")
        when = item.get("when")
        title = item.get("title")
        tags = item.get("tags")
        owners = item.get("owners")
        status = item.get("status")

        if not isinstance(doc_id, str) or not doc_id.strip():
            issues.append({"severity": "error", "message": "doc entry missing id"})
            continue
        did = doc_id.strip()
        if did in seen_ids:
            issues.append({"severity": "error", "message": f"duplicate doc id: {did!r}"})
        seen_ids.add(did)

        required_ok = True
        if not isinstance(doc_type, str) or not doc_type.strip():
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required type"})
            required_ok = False
        if not isinstance(title, str) or not title.strip():
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required title"})
            required_ok = False
        if not isinstance(tier, int):
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required tier (integer)"})
            required_ok = False
        if not isinstance(tags, list):
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required tags[]"})
            required_ok = False
        if not isinstance(owners, list):
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required owners[]"})
            required_ok = False
        if status not in {"active", "draft", "deprecated"}:
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry status must be one of: active|draft|deprecated"})
            required_ok = False
        if not required_ok:
            missing_required_fields += 1

        if not isinstance(path, str) or not path.strip():
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing path"})
            continue
        norm = normalize_repo_relative_posix_path(path.strip())
        if not norm:
            issues.append({"severity": "error", "doc_id": did, "message": f"invalid doc path: {path!r}"})
            continue

        if isinstance(doc_type, str) and doc_type.strip():
            t = doc_type.strip()
            types[t] = types.get(t, 0) + 1
            dt = type_map.get(t)
            if dt is None:
                issues.append({"severity": "error", "doc_id": did, "message": f"unknown doc type: {t!r}"})
            else:
                prefix = dt.get("prefix")
                if isinstance(prefix, str) and prefix.strip() and not did.startswith(prefix.strip()):
                    issues.append({"severity": "error", "doc_id": did, "message": f"doc id must start with prefix {prefix.strip()!r} for type {t!r}"})
                dir_ = dt.get("dir")
                if isinstance(dir_, str) and dir_.strip():
                    dir_norm = normalize_repo_relative_posix_path(dir_.strip())
                    if dir_norm and not norm.startswith(dir_norm.rstrip("/") + "/") and norm != dir_norm:
                        issues.append({"severity": "error", "doc_id": did, "message": f"doc path must be under {dir_norm!r} for type {t!r}"})

        resolved = resolve_path_under_project_root(project_root, norm)
        if resolved is None or not resolved.exists():
            missing_files += 1
            issues.append({"severity": "error", "doc_id": did, "path": norm, "message": "doc file missing"})

        if isinstance(tier, int):
            tiers[str(tier)] = tiers.get(str(tier), 0) + 1

        if not isinstance(when, str) or not when.strip():
            missing_when += 1
            issues.append({"severity": "error", "doc_id": did, "message": "doc entry missing required 'when' (used for planner context selection)"})

    summary["docs_total"] = len(seen_ids)
    summary["docs_missing_files"] = missing_files
    summary["docs_missing_when"] = missing_when
    summary["docs_missing_required_fields"] = missing_required_fields
    summary["tiers"] = tiers
    summary["types"] = types
    return (issues, summary, type_map)


def run_registry_md_check(project_root: Path, *, registry_path: str) -> dict[str, Any]:
    """
    Deterministic check: docs/DOCUMENTATION_REGISTRY.md must be in sync with the JSON registry.
    """
    script = (project_root / "scripts" / "docs" / "generate_registry_md.py").resolve()
    plugin_root = Path((__import__("os").environ.get("CLAUDE_PLUGIN_ROOT") or "")).expanduser()
    if plugin_root and plugin_root.is_dir():
        cand = (plugin_root / "scripts" / "docs" / "generate_registry_md.py").resolve()
        if cand.exists():
            script = cand

    if not script.exists():
        return {"status": "skipped", "reason": "missing scripts/docs/generate_registry_md.py"}

    proc = subprocess.run(
        [sys.executable, str(script), "--project-dir", str(project_root), "--registry-path", registry_path, "--check"],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = (proc.stdout or "")[-4000:]
    return {"status": "passed" if proc.returncode == 0 else "failed", "exit_code": proc.returncode, "output_tail": out}


def find_orphan_docs(project_root: Path, registry: dict[str, Any], type_map: dict[str, dict[str, Any]]) -> list[str]:
    """
    Returns repo-relative paths for docs under managed doc_type dirs that are not present in registry.docs[]
    or registry.generated_artifacts[].
    """
    reg_paths: set[str] = set()

    docs = registry.get("docs") if isinstance(registry.get("docs"), list) else []
    for it in docs:
        if isinstance(it, dict) and isinstance(it.get("path"), str) and it.get("path").strip():
            norm = normalize_repo_relative_posix_path(it["path"].strip())
            if norm:
                reg_paths.add(norm)

    gen = registry.get("generated_artifacts") if isinstance(registry.get("generated_artifacts"), list) else []
    for it in gen:
        if isinstance(it, dict) and isinstance(it.get("path"), str) and it.get("path").strip():
            norm = normalize_repo_relative_posix_path(it["path"].strip())
            if norm:
                reg_paths.add(norm)

    managed_dirs: set[str] = set()
    for dt in type_map.values():
        dir_ = dt.get("dir")
        if isinstance(dir_, str) and dir_.strip():
            dn = normalize_repo_relative_posix_path(dir_.strip())
            if dn:
                managed_dirs.add(dn.rstrip("/"))

    orphans: list[str] = []
    for d in sorted(managed_dirs):
        root = (project_root / d).resolve()
        if not root.exists() or not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            try:
                rel = p.resolve().relative_to(project_root.resolve()).as_posix()
            except Exception:
                continue
            if rel.startswith("docs/_templates/"):
                continue
            if rel not in reg_paths:
                orphans.append(rel)
    return sorted(set(orphans))


_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def find_broken_links(project_root: Path, *, doc_paths: list[str], max_per_doc: int = 200) -> list[dict[str, str]]:
    """
    Best-effort markdown link validation:
    - checks relative file links (no http/https/mailto)
    - ignores anchors (#...)
    """
    issues: list[dict[str, str]] = []
    root = project_root.resolve()
    for rel in doc_paths:
        norm = normalize_repo_relative_posix_path(rel)
        if not norm:
            continue
        path = (root / norm).resolve()
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        base = path.parent
        count = 0
        for m in _MD_LINK_RE.finditer(content):
            raw = (m.group(1) or "").strip()
            if not raw:
                continue
            if raw.startswith(("http://", "https://", "mailto:")):
                continue
            raw = raw.split("#", 1)[0].strip()
            if not raw:
                continue
            # Ignore pure anchors and weird protocols.
            if "://" in raw:
                continue
            # Normalize to filesystem path.
            cand = Path(raw)
            target = (base / cand).resolve() if not cand.is_absolute() else cand
            try:
                target.relative_to(root)
            except Exception:
                # Outside repo root: treat as broken (predictable + safe).
                issues.append({"doc": norm, "link": raw, "reason": "link resolves outside repo root"})
                count += 1
                if count >= max_per_doc:
                    break
                continue
            if not target.exists():
                issues.append({"doc": norm, "link": raw, "reason": "target does not exist"})
                count += 1
                if count >= max_per_doc:
                    break
    return issues


def match_globs(path: str, globs: list[str]) -> bool:
    p = path.replace("\\", "/")
    for g in globs:
        if not isinstance(g, str) or not g.strip():
            continue
        if fnmatch.fnmatch(p, g.strip()):
            return True
    return False
