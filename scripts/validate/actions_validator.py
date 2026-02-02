#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: actions.json validation (shared)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.docs_registry import build_doc_id_to_path_map, get_docs_registry_path, get_docs_require_registry, load_docs_registry
from lib.path_policy import forbid_globs_from_project_config, is_forbidden_path, normalize_repo_relative_posix_path
from lib.paths import has_glob_chars, validate_write_scope  # noqa: F401
from lib.project import detect_project_dir, load_project_config
from docs.coverage_rules import evaluate_coverage_rules_for_write_scopes


@dataclass(frozen=True)
class ValidationError:
    path: str
    message: str


ALLOWED_WORKFLOWS = {"deliver", "triage", "review", "ideate"}
ALLOWED_OWNERS = {
    "action-planner",
    "implementor",
    "tests-builder",
    "quality-gate",
    "compliance-checker",
    "root-cause-analyzer",
    "reviewer",
    "ideation",
}
CODE_OWNERS = {"implementor", "tests-builder"}


def _contains_glob_chars(value: str) -> bool:
    # Use lib.paths.has_glob_chars for consistency, but keep wrapper for backwards compat
    return has_glob_chars(value)


def _expect_type(errors: list[ValidationError], value: Any, expected: type, path: str) -> bool:
    if not isinstance(value, expected):
        errors.append(ValidationError(path, f"Expected {expected.__name__}, got {type(value).__name__}"))
        return False
    return True


@dataclass(frozen=True)
class WriteScope:
    raw: str
    path: str  # normalized repo-relative posix (no leading ./)
    kind: str  # "file" | "dir"


def _parse_write_scopes(errors: list[ValidationError], writes: list[Any], path_prefix: str) -> list[WriteScope]:
    scopes: list[WriteScope] = []
    seen: set[tuple[str, str]] = set()
    for i, raw in enumerate(writes):
        p = f"{path_prefix}[{i}]"
        if not isinstance(raw, str) or not raw.strip():
            errors.append(ValidationError(p, "Must be a non-empty string"))
            continue
        s = raw.strip()
        if _contains_glob_chars(s):
            errors.append(ValidationError(p, "Globs are forbidden in file_scope.writes (use exact files or dir prefixes ending in '/')"))
            continue
        is_dir = s.endswith("/")
        norm = normalize_repo_relative_posix_path(s)
        if norm is None:
            errors.append(ValidationError(p, f"Invalid repo-relative path: {raw!r}"))
            continue
        if is_dir and not norm.endswith("/"):
            norm = norm + "/"
        if not is_dir and norm.endswith("/"):
            errors.append(ValidationError(p, "File path must not end with '/'"))
            continue
        kind = "dir" if is_dir else "file"
        key = (kind, norm)
        if key in seen:
            errors.append(ValidationError(p, f"Duplicate write scope: {raw!r}"))
            continue
        seen.add(key)
        scopes.append(WriteScope(raw=s, path=norm, kind=kind))
    return scopes


def _scopes_overlap(a: WriteScope, b: WriteScope) -> bool:
    # dir-dir: overlap if either is prefix of the other.
    if a.kind == "dir" and b.kind == "dir":
        return a.path.startswith(b.path) or b.path.startswith(a.path)
    # file-file: overlap if same file.
    if a.kind == "file" and b.kind == "file":
        return a.path == b.path
    # file-dir: overlap if file under dir.
    if a.kind == "file" and b.kind == "dir":
        return a.path.startswith(b.path)
    if a.kind == "dir" and b.kind == "file":
        return b.path.startswith(a.path)
    return False


def validate_actions_data(
    data: dict[str, Any],
    *,
    project_root: Path | None = None,
    strategy_override: str | None = None,
) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if project_root is None:
        project_root = detect_project_dir()
    config = load_project_config(project_root) or {}
    forbid_globs = forbid_globs_from_project_config(config)
    workflow_cfg = config.get("workflow") if isinstance(config.get("workflow"), dict) else {}
    require_verifications_for_code = bool(workflow_cfg.get("require_verifications_for_code_tasks") is True)
    require_user_stories = bool(workflow_cfg.get("require_user_stories") is True)
    strategy = workflow_cfg.get("strategy") if isinstance(workflow_cfg.get("strategy"), str) else "default"
    if strategy not in {"default", "tdd"}:
        strategy = "default"
    if isinstance(strategy_override, str) and strategy_override in {"default", "tdd"}:
        strategy = strategy_override
    lsp_cfg = config.get("lsp") if isinstance(config.get("lsp"), dict) else {}
    lsp_enabled = bool(lsp_cfg.get("enabled") is True)

    # Top-level structure.
    if data.get("version") != 1:
        errors.append(ValidationError("version", "Must be 1"))

    workflow = data.get("workflow")
    if workflow not in ALLOWED_WORKFLOWS:
        errors.append(ValidationError("workflow", f"Must be one of {sorted(ALLOWED_WORKFLOWS)}, got {workflow!r}"))

    tasks = data.get("tasks")
    if not _expect_type(errors, tasks, list, "tasks"):
        return errors
    if not tasks:
        errors.append(ValidationError("tasks", "Must have at least one task"))
        return errors

    # Parallel execution must be explicit (default ON UX).
    parallel = data.get("parallel_execution")
    if not isinstance(parallel, dict):
        errors.append(ValidationError("parallel_execution", "Required object (set enabled=true by default)"))
        parallel = {}

    parallel_enabled = parallel.get("enabled")
    if not isinstance(parallel_enabled, bool):
        errors.append(ValidationError("parallel_execution.enabled", "Required boolean"))
        parallel_enabled = False

    groups = parallel.get("groups")
    if parallel_enabled:
        if not isinstance(groups, list) or not groups:
            errors.append(ValidationError("parallel_execution.groups", "Required non-empty array when enabled=true"))
            groups = []

    # Task ids unique.
    seen_task_ids: set[str] = set()
    task_by_id: dict[str, dict[str, Any]] = {}

    require_registry = get_docs_require_registry(config)
    registry_path = get_docs_registry_path(config)
    registry = load_docs_registry(project_root, registry_path)
    docs_map = build_doc_id_to_path_map(registry)
    if require_registry and not docs_map:
        errors.append(ValidationError("docs.registry_path", f"docs.require_registry=true but registry is missing/invalid: {registry_path!r}"))

    for i, t in enumerate(tasks):
        tp = f"tasks[{i}]"
        if not _expect_type(errors, t, dict, tp):
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.strip():
            errors.append(ValidationError(f"{tp}.id", "Required non-empty string"))
            continue
        tid = tid.strip()
        if tid in seen_task_ids:
            errors.append(ValidationError(f"{tp}.id", f"Duplicate task id: {tid!r}"))
            continue
        seen_task_ids.add(tid)
        task_by_id[tid] = t

        owner = t.get("owner")
        if owner not in ALLOWED_OWNERS:
            errors.append(ValidationError(f"{tp}.owner", f"Must be one of {sorted(ALLOWED_OWNERS)}, got {owner!r}"))

        summary = t.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            # Common mistake: using 'title'
            if isinstance(t.get("title"), str) and t.get("title"):
                errors.append(ValidationError(tp, "Uses 'title' but schema requires 'summary'"))
            errors.append(ValidationError(f"{tp}.summary", "Required non-empty string"))
        summary_text_for_keywords = summary.strip() if isinstance(summary, str) else ""
        acs = t.get("acceptance_criteria")
        if isinstance(acs, list):
            for ac in acs[:50]:
                if isinstance(ac, dict) and isinstance(ac.get("statement"), str) and ac.get("statement").strip():
                    summary_text_for_keywords += "\n" + ac.get("statement").strip()

        file_scope = t.get("file_scope")
        if not _expect_type(errors, file_scope, dict, f"{tp}.file_scope"):
            continue
        allow = file_scope.get("allow")
        if not isinstance(allow, list) or not allow:
            if isinstance(file_scope.get("reads"), list):
                errors.append(ValidationError(f"{tp}.file_scope", "Uses 'reads' but schema requires 'allow'"))
            errors.append(ValidationError(f"{tp}.file_scope.allow", "Required non-empty array"))

        # Code tasks need writes if parallel enabled.
        parsed_writes: list[WriteScope] = []
        if owner in CODE_OWNERS and parallel_enabled:
            writes = file_scope.get("writes")
            if not isinstance(writes, list) or not writes:
                errors.append(ValidationError(f"{tp}.file_scope.writes", "Required non-empty array for code tasks when parallel_execution.enabled=true"))
            else:
                parsed_writes = _parse_write_scopes(errors, writes, f"{tp}.file_scope.writes")

        acceptance = t.get("acceptance_criteria")
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(ValidationError(f"{tp}.acceptance_criteria", "Required non-empty array"))
        else:
            any_verifications = False
            for j, ac in enumerate(acceptance):
                ap = f"{tp}.acceptance_criteria[{j}]"
                if not isinstance(ac, dict):
                    errors.append(ValidationError(ap, "Must be an object"))
                    continue
                if not isinstance(ac.get("id"), str) or not str(ac.get("id")).strip():
                    errors.append(ValidationError(f"{ap}.id", "Required non-empty string"))
                if not isinstance(ac.get("statement"), str) or not str(ac.get("statement")).strip():
                    errors.append(ValidationError(f"{ap}.statement", "Required non-empty string"))
                verifs = ac.get("verifications")
                if isinstance(verifs, list) and any(isinstance(v, dict) for v in verifs):
                    any_verifications = True
                if verifs is None:
                    continue
                if not isinstance(verifs, list):
                    errors.append(ValidationError(f"{ap}.verifications", "Must be an array of verification objects"))
                    continue
                for vk, v in enumerate(verifs[:200]):
                    vp = f"{ap}.verifications[{vk}]"
                    if not isinstance(v, dict):
                        errors.append(ValidationError(vp, "Must be an object"))
                        continue
                    vtype = v.get("type")
                    if not isinstance(vtype, str) or not vtype.strip():
                        errors.append(ValidationError(f"{vp}.type", "Required non-empty string"))
                        continue
                    vtype = vtype.strip()
                    if vtype not in {"file", "grep", "command", "lsp"}:
                        errors.append(ValidationError(f"{vp}.type", f"Unknown verification type: {vtype!r}"))
                        continue

                    if vtype in {"file", "grep"}:
                        p = v.get("path")
                        if not isinstance(p, str) or not p.strip():
                            errors.append(ValidationError(f"{vp}.path", f"Required non-empty string for type={vtype!r}"))

                    if vtype == "grep":
                        pat = v.get("pattern")
                        if not isinstance(pat, str) or not pat.strip():
                            errors.append(ValidationError(f"{vp}.pattern", "Required non-empty string for type='grep'"))
                        else:
                            try:
                                re.compile(pat)
                            except re.error as exc:
                                errors.append(ValidationError(f"{vp}.pattern", f"Invalid regex: {exc}"))

                    if vtype == "command":
                        cmd = v.get("command")
                        if not isinstance(cmd, str) or not cmd.strip():
                            errors.append(ValidationError(f"{vp}.command", "Required non-empty string for type='command'"))
                        ms = v.get("must_succeed")
                        if ms is not None and not isinstance(ms, bool):
                            errors.append(ValidationError(f"{vp}.must_succeed", "Must be a boolean"))

                    if vtype == "lsp":
                        if not lsp_enabled:
                            errors.append(
                                ValidationError(
                                    vp,
                                    "lsp verifications require lsp.enabled=true in .claude/project.yaml (or remove type='lsp' verifications)",
                                )
                            )
                        spec = v.get("lsp")
                        if not isinstance(spec, dict):
                            errors.append(ValidationError(f"{vp}.lsp", "Required object for type='lsp'"))
                            continue
                        kind = spec.get("kind")
                        if kind not in {"definition_exists", "hover_contains", "references_min"}:
                            errors.append(ValidationError(f"{vp}.lsp.kind", "Must be one of 'definition_exists'|'hover_contains'|'references_min'"))
                        lp = spec.get("path")
                        sym = spec.get("symbol")
                        if not isinstance(lp, str) or not lp.strip():
                            errors.append(ValidationError(f"{vp}.lsp.path", "Required non-empty string"))
                        if not isinstance(sym, str) or not sym.strip():
                            errors.append(ValidationError(f"{vp}.lsp.symbol", "Required non-empty string"))
                        if kind == "hover_contains":
                            mc = spec.get("must_contain")
                            if not isinstance(mc, str) or not mc.strip():
                                errors.append(ValidationError(f"{vp}.lsp.must_contain", "Required non-empty string for kind='hover_contains'"))
                        if kind == "references_min":
                            mr = spec.get("min_results")
                            if not isinstance(mr, int) or mr < 0:
                                errors.append(ValidationError(f"{vp}.lsp.min_results", "Required integer >= 0 for kind='references_min'"))

            # Optional strictness: require at least one verification for code tasks.
            # This makes "done" evidence deterministic and improves self-healing (gates can prove failures).
            if owner in CODE_OWNERS and require_verifications_for_code and not any_verifications:
                errors.append(
                    ValidationError(
                        f"{tp}.acceptance_criteria",
                        "workflow.require_verifications_for_code_tasks=true but no acceptance_criteria.verifications[] were provided",
                    )
                )

        # Optional strictness: require user-story linkage for code tasks.
        if owner in CODE_OWNERS and require_user_stories:
            us = t.get("user_story_ids")
            ids = [str(x).strip() for x in us if isinstance(x, str) and str(x).strip()] if isinstance(us, list) else []
            if not ids:
                errors.append(ValidationError(f"{tp}.user_story_ids", "workflow.require_user_stories=true but task is missing user_story_ids[] (non-empty)"))

        # Docs registry constraints (code tasks only).
        if owner in CODE_OWNERS and require_registry:
            ctx = t.get("context")
            if not isinstance(ctx, dict):
                errors.append(ValidationError(f"{tp}.context", "Required object for code tasks when docs.require_registry=true"))
            else:
                doc_ids = ctx.get("doc_ids")
                if not isinstance(doc_ids, list) or not doc_ids:
                    errors.append(ValidationError(f"{tp}.context.doc_ids", "Required non-empty array when docs.require_registry=true"))
                else:
                    for k, doc_id in enumerate(doc_ids):
                        if not isinstance(doc_id, str) or not doc_id.strip():
                            errors.append(ValidationError(f"{tp}.context.doc_ids[{k}]", "Must be a non-empty string"))
                            continue
                        if docs_map and doc_id.strip() not in docs_map:
                            errors.append(ValidationError(f"{tp}.context.doc_ids[{k}]", f"Unknown doc id: {doc_id!r}"))

                # Coverage rules enforcement (planning-time, deterministic):
                # Ensure required_doc_ids for this task's planned write scopes are included in context.doc_ids[].
                rules = registry.get("coverage_rules") if isinstance(registry, dict) else None
                if isinstance(rules, list) and parsed_writes:
                    plan = evaluate_coverage_rules_for_write_scopes(
                        rules,
                        write_scopes=[w.raw for w in parsed_writes],
                        keywords_text=summary_text_for_keywords,
                    )
                    required = plan.required_doc_ids
                    if required:
                        doc_set = set([d.strip() for d in doc_ids if isinstance(d, str)]) if isinstance(doc_ids, list) else set()
                        missing = [d for d in required if d not in doc_set]
                        if missing:
                            why: list[str] = []
                            for tr in plan.triggered[:4]:
                                kws = ", ".join(tr.matched_keywords[:3]) if tr.matched_keywords else ""
                                paths = ", ".join(tr.matched_paths[:2]) if tr.matched_paths else ""
                                bits: list[str] = [tr.rule_id]
                                if kws:
                                    bits.append(f"kws={kws}")
                                if paths:
                                    bits.append(f"paths={paths}")
                                why.append("[" + " ".join(bits) + "]")
                            why_s = (" Triggered rules: " + " ".join(why)) if why else ""
                            errors.append(
                                ValidationError(
                                    f"{tp}.context.doc_ids",
                                    "Missing required docs for this task per docs.coverage_rules: "
                                    + ", ".join([repr(d) for d in missing])
                                    + why_s,
                                )
                            )

        # Optional: code pointers (best-effort safety validation).
        ctx = t.get("context")
        if isinstance(ctx, dict) and "code_pointers" in ctx:
            cps = ctx.get("code_pointers")
            if cps is None:
                pass
            elif not isinstance(cps, list):
                errors.append(ValidationError(f"{tp}.context.code_pointers", "Must be an array of {path, pattern} objects"))
            else:
                for j, cp in enumerate(cps[:200]):
                    cp_path = f"{tp}.context.code_pointers[{j}]"
                    if not isinstance(cp, dict):
                        errors.append(ValidationError(cp_path, "Must be an object"))
                        continue
                    p = cp.get("path")
                    pat = cp.get("pattern")
                    if not isinstance(p, str) or not p.strip():
                        errors.append(ValidationError(f"{cp_path}.path", "Required non-empty string"))
                    else:
                        norm = normalize_repo_relative_posix_path(p.strip())
                        if norm is None:
                            errors.append(ValidationError(f"{cp_path}.path", f"Invalid repo-relative path: {p!r}"))
                        elif is_forbidden_path(norm, forbid_globs):
                            errors.append(ValidationError(f"{cp_path}.path", f"Forbidden by policies.forbid_secrets_globs: {norm!r}"))
                    if not isinstance(pat, str) or not pat.strip():
                        errors.append(ValidationError(f"{cp_path}.pattern", "Required non-empty string (regex)"))
                    cl = cp.get("context_lines")
                    if cl is not None and (not isinstance(cl, int) or cl < 0):
                        errors.append(ValidationError(f"{cp_path}.context_lines", "Must be an integer >= 0"))
                    mm = cp.get("max_matches")
                    if mm is not None and (not isinstance(mm, int) or mm < 1):
                        errors.append(ValidationError(f"{cp_path}.max_matches", "Must be an integer >= 1"))

    # depends_on references exist (best-effort; cycle detection is deferred).
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.strip():
            continue
        depends = t.get("depends_on")
        if depends is None:
            continue
        if not isinstance(depends, list):
            errors.append(ValidationError(f"tasks[{i}].depends_on", "Must be an array of task ids"))
            continue
        for j, dep in enumerate(depends):
            if not isinstance(dep, str) or not dep.strip():
                errors.append(ValidationError(f"tasks[{i}].depends_on[{j}]", "Must be a non-empty string"))
                continue
            if dep.strip() not in task_by_id:
                errors.append(ValidationError(f"tasks[{i}].depends_on[{j}]", f"Unknown task id: {dep!r}"))

    # Optional: TDD strategy enforcement (tests-first planning contract).
    if strategy == "tdd":
        tests_task_ids = [tid for tid, t in task_by_id.items() if isinstance(t, dict) and t.get("owner") == "tests-builder"]
        implementor_idxs: list[int] = []
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                continue
            if t.get("owner") != "implementor":
                continue
            tid = t.get("id")
            if isinstance(tid, str) and tid.strip():
                implementor_idxs.append(i)
        if implementor_idxs and not tests_task_ids:
            errors.append(ValidationError("workflow.strategy", "workflow.strategy=tdd requires at least one tests-builder task when implementor tasks are present"))
        for i in implementor_idxs:
            t = tasks[i]
            if not isinstance(t, dict):
                continue
            depends = t.get("depends_on")
            deps = [str(x).strip() for x in depends if isinstance(x, str) and str(x).strip()] if isinstance(depends, list) else []
            if tests_task_ids and not any(d in tests_task_ids for d in deps):
                errors.append(ValidationError(f"tasks[{i}].depends_on", "workflow.strategy=tdd requires implementor tasks to depend on at least one tests-builder task id"))

    # Parallel groups invariants + write-scope overlap detection.
    if parallel_enabled and isinstance(groups, list):
        all_group_tasks: list[str] = []
        max_tests_order: int | None = None
        min_impl_order: int | None = None
        for gi, g in enumerate(groups):
            gp = f"parallel_execution.groups[{gi}]"
            if not isinstance(g, dict):
                errors.append(ValidationError(gp, "Must be an object"))
                continue
            if not isinstance(g.get("group_id"), str) or not str(g.get("group_id")).strip():
                errors.append(ValidationError(f"{gp}.group_id", "Required non-empty string"))
            if not isinstance(g.get("execution_order"), int) or g.get("execution_order", 0) < 1:
                errors.append(ValidationError(f"{gp}.execution_order", "Required integer >= 1"))
            gt = g.get("tasks")
            if not isinstance(gt, list) or not gt:
                errors.append(ValidationError(f"{gp}.tasks", "Required non-empty array of task ids"))
                continue
            order = g.get("execution_order") if isinstance(g.get("execution_order"), int) else None
            has_tests = False
            has_impl = False
            for tj, task_id in enumerate(gt):
                if not isinstance(task_id, str) or not task_id.strip():
                    errors.append(ValidationError(f"{gp}.tasks[{tj}]", "Must be a non-empty string"))
                    continue
                task_id = task_id.strip()
                all_group_tasks.append(task_id)
                task = task_by_id.get(task_id)
                if task is None:
                    errors.append(ValidationError(f"{gp}.tasks[{tj}]", f"Unknown task id: {task_id!r}"))
                    continue
                owner = task.get("owner")
                if owner not in CODE_OWNERS:
                    errors.append(ValidationError(f"{gp}.tasks[{tj}]", f"Task owner must be implementor/tests-builder, got {owner!r}"))
                if owner == "tests-builder":
                    has_tests = True
                    if isinstance(order, int):
                        max_tests_order = order if max_tests_order is None else max(max_tests_order, order)
                if owner == "implementor":
                    has_impl = True
                    if isinstance(order, int):
                        min_impl_order = order if min_impl_order is None else min(min_impl_order, order)

            if strategy == "tdd" and has_tests and has_impl:
                errors.append(ValidationError(gp, "workflow.strategy=tdd forbids mixing tests-builder and implementor tasks in the same parallel group"))

            # Overlaps within this group.
            scopes_by_task: dict[str, list[WriteScope]] = {}
            for task_id in [str(x).strip() for x in gt if isinstance(x, str) and str(x).strip()]:
                task = task_by_id.get(task_id)
                if not isinstance(task, dict):
                    continue
                fs = task.get("file_scope")
                if not isinstance(fs, dict):
                    continue
                writes = fs.get("writes")
                if not isinstance(writes, list) or not writes:
                    continue
                scopes_by_task[task_id] = _parse_write_scopes(errors, writes, f"tasks[{task_id}].file_scope.writes")

            task_ids = sorted(scopes_by_task.keys())
            for ai, a_id in enumerate(task_ids):
                for b_id in task_ids[ai + 1 :]:
                    for a_scope in scopes_by_task[a_id]:
                        for b_scope in scopes_by_task[b_id]:
                            if _scopes_overlap(a_scope, b_scope):
                                errors.append(
                                    ValidationError(
                                        gp,
                                        f"Write-scope overlap in group between {a_id!r} ({a_scope.raw!r}) and {b_id!r} ({b_scope.raw!r})",
                                    )
                                )
                                break

        # Each code task appears in exactly one group.
        code_task_ids = [tid for tid, t in task_by_id.items() if isinstance(t, dict) and t.get("owner") in CODE_OWNERS]
        missing = [tid for tid in code_task_ids if tid not in all_group_tasks]
        if missing:
            errors.append(ValidationError("parallel_execution.groups", f"Missing code tasks from groups: {missing!r}"))
        dupes = sorted({t for t in all_group_tasks if all_group_tasks.count(t) > 1})
        if dupes:
            errors.append(ValidationError("parallel_execution.groups", f"Duplicate task ids across groups: {dupes!r}"))

        if strategy == "tdd" and max_tests_order is not None and min_impl_order is not None and max_tests_order >= min_impl_order:
            errors.append(
                ValidationError(
                    "parallel_execution.groups",
                    "workflow.strategy=tdd requires tests-builder groups to have lower execution_order than implementor groups",
                )
            )

    return errors


def validate_actions_file(path: Path, *, project_root: Path | None = None) -> list[ValidationError]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [ValidationError(str(path), "File not found")]
    except json.JSONDecodeError as exc:
        return [ValidationError(str(path), f"Invalid JSON: {exc}")]
    if not isinstance(data, dict):
        return [ValidationError(str(path), f"Root must be an object, got {type(data).__name__}")]

    # Optional session override: allow the session to enforce TDD without mutating repo config.
    # If present, it must be a stable, explicit value ("default"|"tdd").
    strategy_override = None
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        resolved = path
    if resolved.name == "actions.json" and resolved.parent.name == "planning":
        session_dir = resolved.parent.parent
        sess = session_dir / "session.json"
        if sess.exists():
            try:
                sess_data = json.loads(sess.read_text(encoding="utf-8"))
            except Exception:
                sess_data = None
            if isinstance(sess_data, dict):
                st = sess_data.get("workflow_strategy")
                if isinstance(st, str) and st in {"default", "tdd"}:
                    strategy_override = st

    return validate_actions_data(data, project_root=project_root, strategy_override=strategy_override)
