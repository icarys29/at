#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Coverage rule engine for docs-keeper (deterministic)

Rules are defined in docs/DOCUMENTATION_REGISTRY.json (v2) under coverage_rules[].

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.docs_validation import match_globs


@dataclass(frozen=True)
class RuleTrigger:
    rule_id: str
    matched_paths: list[str]
    note: str | None


@dataclass(frozen=True)
class CoveragePlan:
    required_doc_ids: list[str]
    required_create_types: list[str]
    triggered: list[RuleTrigger]


def _paths_by_action(changed_files: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"created": [], "modified": [], "deleted": [], "any": []}
    for it in changed_files[:5000]:
        if not isinstance(it, dict):
            continue
        p = it.get("path")
        a = it.get("action")
        if not isinstance(p, str) or not p.strip():
            continue
        path = p.strip().replace("\\", "/")
        out["any"].append(path)
        if a in {"created", "modified", "deleted"}:
            out[a].append(path)
    return out


def evaluate_coverage_rules(rules: Any, *, changed_files: list[dict[str, Any]]) -> CoveragePlan:
    if not isinstance(rules, list) or not rules:
        return CoveragePlan(required_doc_ids=[], required_create_types=[], triggered=[])

    paths = _paths_by_action(changed_files)
    req_docs: set[str] = set()
    req_types: set[str] = set()
    triggered: list[RuleTrigger] = []

    for rule in rules[:500]:
        if not isinstance(rule, dict):
            continue
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
        actions = rule.get("actions") if isinstance(rule.get("actions"), dict) else {}

        matched_paths: list[str] = []

        any_globs = match.get("paths_any") if isinstance(match.get("paths_any"), list) else []
        created_globs = match.get("created_paths_any") if isinstance(match.get("created_paths_any"), list) else []
        modified_globs = match.get("modified_paths_any") if isinstance(match.get("modified_paths_any"), list) else []
        deleted_globs = match.get("deleted_paths_any") if isinstance(match.get("deleted_paths_any"), list) else []

        if any_globs:
            matched_paths.extend([p for p in paths["any"] if match_globs(p, any_globs)])
        if created_globs:
            matched_paths.extend([p for p in paths["created"] if match_globs(p, created_globs)])
        if modified_globs:
            matched_paths.extend([p for p in paths["modified"] if match_globs(p, modified_globs)])
        if deleted_globs:
            matched_paths.extend([p for p in paths["deleted"] if match_globs(p, deleted_globs)])

        matched_paths = sorted(set(matched_paths))
        if not matched_paths:
            continue

        doc_ids = actions.get("require_doc_ids")
        if isinstance(doc_ids, list):
            for d in doc_ids[:200]:
                if isinstance(d, str) and d.strip():
                    req_docs.add(d.strip())

        create_types = actions.get("require_create_types")
        if isinstance(create_types, list):
            for t in create_types[:50]:
                if isinstance(t, str) and t.strip():
                    req_types.add(t.strip())

        note = actions.get("note")
        triggered.append(RuleTrigger(rule_id=rid.strip(), matched_paths=matched_paths[:40], note=note if isinstance(note, str) else None))

    return CoveragePlan(
        required_doc_ids=sorted(req_docs),
        required_create_types=sorted(req_types),
        triggered=triggered,
    )


def evaluate_coverage_rules_for_write_scopes(rules: Any, *, write_scopes: list[str]) -> CoveragePlan:
    """
    Deterministic evaluation for planning-time enforcement:
    treat each planned write scope as a "modified path" (best-effort).
    """
    changed_files: list[dict[str, Any]] = []
    for w in write_scopes[:5000]:
        if isinstance(w, str) and w.strip():
            changed_files.append({"path": w.strip().replace("\\", "/"), "action": "modified"})
    return evaluate_coverage_rules(rules, changed_files=changed_files)
