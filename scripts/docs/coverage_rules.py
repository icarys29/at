#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Coverage rule engine for docs-keeper (deterministic)

Rules are defined in docs/DOCUMENTATION_REGISTRY.json (v2) under coverage_rules[].

This engine is intentionally project-agnostic:
- rules provide all path globs and keyword phrases (no language assumptions)
- keyword matching is limited to explicit session summaries (no commit/PR inference)

Back-compat:
- supports legacy rule shape: {id, description, match:{...}, actions:{require_doc_ids, require_create_types, note}}
- supports optional advanced rule shape:
  {id, priority?, when?, match_any:[{...predicates...}], requires:[...], checks?}
  where requires entries with explicit "id" become required_doc_ids, and requires entries with "type"
  become required_create_types (for known doc types).

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from lib.docs_validation import match_globs


@dataclass(frozen=True)
class RuleTrigger:
    rule_id: str
    matched_paths: list[str]
    note: str | None
    matched_keywords: list[str]


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


_KNOWN_CREATE_TYPES = {"context", "architecture", "adr", "ard", "pattern", "runbook"}


def _normalize_globs(globs: list[str]) -> list[str]:
    out: list[str] = []
    for g in globs[:500]:
        if not isinstance(g, str) or not g.strip():
            continue
        s = g.strip().replace("\\", "/")
        # Allow using "dir/" as a prefix shorthand (project-agnostic convenience).
        if s.endswith("/") and not any(ch in s for ch in ["*", "?", "[", "]"]):
            s = s + "**"
        out.append(s)
    return out


def _normalize_keywords(phrases: list[str]) -> list[str]:
    out: list[str] = []
    for p in phrases[:500]:
        if not isinstance(p, str) or not p.strip():
            continue
        tokens = _TOKEN_RE.findall(p.strip().lower())
        if tokens:
            out.append(" ".join(tokens))
    return out


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _text_blob(keywords_text: str | None) -> str:
    if not isinstance(keywords_text, str) or not keywords_text.strip():
        return ""
    tokens = _TOKEN_RE.findall(keywords_text.lower())
    if not tokens:
        return ""
    # Space-padded token stream enables deterministic word-boundary phrase matching using substring.
    return " " + " ".join(tokens) + " "


def _keywords_any_match(blob: str, phrases: list[str]) -> tuple[bool, list[str]]:
    if not blob or not phrases:
        return (False, [])
    matched: list[str] = []
    for p in phrases[:500]:
        if not p:
            continue
        if f" {p} " in blob:
            matched.append(p)
    return (len(matched) > 0, matched[:20])


def _keywords_all_match(blob: str, phrases: list[str]) -> tuple[bool, list[str]]:
    if not phrases:
        return (True, [])
    if not blob:
        return (False, [])
    missing: list[str] = []
    for p in phrases[:500]:
        if not p:
            continue
        if f" {p} " not in blob:
            missing.append(p)
    return (len(missing) == 0, [])


def _eval_match_group(group: dict[str, Any], *, paths: dict[str, list[str]], blob: str) -> tuple[bool, list[str], list[str]]:
    """
    Returns: (matched, matched_paths, matched_keywords)
    A group matches if all specified predicates match (AND).
    """
    matched_paths: list[str] = []
    matched_keywords: list[str] = []

    if group.get("always") is True:
        return (True, [], [])

    # Paths predicates (globs against appropriate action buckets)
    mapping = {
        "paths_any": "any",
        "changed_paths_any": "any",
        "created_paths_any": "created",
        "modified_paths_any": "modified",
        "deleted_paths_any": "deleted",
    }
    for key, bucket in mapping.items():
        globs = group.get(key)
        if globs is None:
            continue
        if not isinstance(globs, list):
            return (False, [], [])
        gs = _normalize_globs([str(g) for g in globs if isinstance(g, str)])
        if not gs:
            return (False, [], [])
        hits = [p for p in paths[bucket] if match_globs(p, gs)]
        if not hits:
            return (False, [], [])
        matched_paths.extend(hits[:40])

    # Keyword predicates (substring match against provided blob)
    kwa = group.get("keywords_any")
    if kwa is not None:
        if not isinstance(kwa, list):
            return (False, [], [])
        phrases = _normalize_keywords([str(x) for x in kwa if isinstance(x, str)])
        ok, hits = _keywords_any_match(blob, phrases)
        if not ok:
            return (False, [], [])
        matched_keywords.extend(hits)

    kwa_all = group.get("keywords_all")
    if kwa_all is not None:
        if not isinstance(kwa_all, list):
            return (False, [], [])
        phrases = _normalize_keywords([str(x) for x in kwa_all if isinstance(x, str)])
        ok, _ = _keywords_all_match(blob, phrases)
        if not ok:
            return (False, [], [])

    return (True, sorted(set(matched_paths))[:40], sorted(set(matched_keywords))[:20])


def _extract_required_from_requires(requires: Any) -> tuple[set[str], set[str]]:
    req_docs: set[str] = set()
    req_types: set[str] = set()
    if not isinstance(requires, list):
        return (req_docs, req_types)
    for it in requires[:500]:
        if not isinstance(it, dict):
            continue
        did = it.get("id")
        if isinstance(did, str) and did.strip():
            req_docs.add(did.strip())
        typ = it.get("type")
        if isinstance(typ, str) and typ.strip() and typ.strip() in _KNOWN_CREATE_TYPES:
            req_types.add(typ.strip())
    return (req_docs, req_types)


def evaluate_coverage_rules(
    rules: Any,
    *,
    changed_files: list[dict[str, Any]],
    keywords_text: str | None = None,
) -> CoveragePlan:
    if not isinstance(rules, list) or not rules:
        return CoveragePlan(required_doc_ids=[], required_create_types=[], triggered=[])

    paths = _paths_by_action(changed_files)
    blob = _text_blob(keywords_text)
    req_docs: set[str] = set()
    req_types: set[str] = set()
    triggered: list[RuleTrigger] = []

    # Evaluate deterministically top-to-bottom by priority desc (advanced rules), else preserve input order.
    def _rule_sort_key(it: Any) -> tuple[int, int]:
        if not isinstance(it, dict):
            return (0, 0)
        pr = it.get("priority")
        p = int(pr) if isinstance(pr, int) else 0
        return (-p, 0)

    ordered = [r for r in rules if isinstance(r, dict)]
    ordered.sort(key=_rule_sort_key)

    for rule in ordered[:800]:
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        rid_s = rid.strip()

        note = rule.get("when")
        if not isinstance(note, str) or not note.strip():
            note = rule.get("description") if isinstance(rule.get("description"), str) else None

        matched_paths: list[str] = []
        matched_keywords: list[str] = []

        # Advanced rule shape: match_any groups + requires
        match_any = rule.get("match_any")
        requires = rule.get("requires")
        if isinstance(match_any, list):
            group_matched = False
            for group in match_any[:50]:
                if not isinstance(group, dict):
                    continue
                ok, mp, mk = _eval_match_group(group, paths=paths, blob=blob)
                if ok:
                    group_matched = True
                    matched_paths = mp
                    matched_keywords = mk
                    break
            if not group_matched:
                continue
            r_docs, r_types = _extract_required_from_requires(requires)
            req_docs |= r_docs
            req_types |= r_types
            triggered.append(
                RuleTrigger(
                    rule_id=rid_s,
                    matched_paths=matched_paths,
                    note=note.strip() if isinstance(note, str) and note.strip() else None,
                    matched_keywords=matched_keywords,
                )
            )
            continue

        # Legacy rule shape: match + actions
        match = rule.get("match") if isinstance(rule.get("match"), dict) else {}
        actions = rule.get("actions") if isinstance(rule.get("actions"), dict) else {}

        any_globs = _normalize_globs(match.get("paths_any")) if isinstance(match.get("paths_any"), list) else []
        created_globs = _normalize_globs(match.get("created_paths_any")) if isinstance(match.get("created_paths_any"), list) else []
        modified_globs = _normalize_globs(match.get("modified_paths_any")) if isinstance(match.get("modified_paths_any"), list) else []
        deleted_globs = _normalize_globs(match.get("deleted_paths_any")) if isinstance(match.get("deleted_paths_any"), list) else []

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

        legacy_note = actions.get("note")
        triggered.append(
            RuleTrigger(
                rule_id=rid_s,
                matched_paths=matched_paths[:40],
                note=legacy_note if isinstance(legacy_note, str) and legacy_note.strip() else (note if isinstance(note, str) else None),
                matched_keywords=[],
            )
        )

    return CoveragePlan(
        required_doc_ids=sorted(req_docs),
        required_create_types=sorted(req_types),
        triggered=triggered,
    )


def evaluate_coverage_rules_for_write_scopes(
    rules: Any,
    *,
    write_scopes: list[str],
    keywords_text: str | None = None,
) -> CoveragePlan:
    """
    Deterministic evaluation for planning-time enforcement:
    treat each planned write scope as a "modified path" (best-effort).
    """
    changed_files: list[dict[str, Any]] = []
    for w in write_scopes[:5000]:
        if isinstance(w, str) and w.strip():
            changed_files.append({"path": w.strip().replace("\\", "/"), "action": "modified"})
    return evaluate_coverage_rules(rules, changed_files=changed_files, keywords_text=keywords_text)
