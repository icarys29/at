#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Subagent stop hook for artifact validation

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.active_session import resolve_session_dir_from_hook  # noqa: E402


AT_AGENT_IDS = {
    "action-planner",
    "solution-architect",
    "implementor",
    "tests-builder",
    "quality-gate",
    "compliance-checker",
    "docs-keeper",
    # Optional: remediation agent (if present)
    "remediator",
}


@dataclass(frozen=True)
class ParsedContract:
    status: str
    summary: str
    repo_diff_lines: list[str]
    session_artifact_lines: list[str]
    session_artifact_paths: list[str]


def _read_hook_input() -> dict[str, Any] | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _read_tail(path: Path, *, max_bytes: int = 400_000) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if max_bytes > 0 and len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="ignore")


def _iter_json_lines(path: Path, *, max_lines: int = 6000) -> Iterable[dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if max_lines > 0 and i >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except Exception:
        return


def _collect_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for v in value.values():
            out.extend(_collect_strings(v))
        return out
    if isinstance(value, list):
        for v in value:
            out.extend(_collect_strings(v))
        return out
    return out


def _extract_text_from_transcript(path: Path) -> str:
    chunks: list[str] = []
    for obj in _iter_json_lines(path):
        strings = _collect_strings(obj)
        if strings:
            chunks.append("\n".join(strings))
    if chunks:
        return "\n".join(chunks)
    return _read_tail(path)


def _find_session_dir_from_text(project_root: Path, sessions_dir: str, text: str) -> Path | None:
    patterns = [
        r"(?P<p>/[^\s\"']+?)/inputs/task_context/[A-Za-z0-9_.-]+\\.md",
        r"(?P<p>/[^\s\"']+?)/inputs/context_pack\\.md",
        r"(?P<p>/[^\s\"']+?)/planning/actions\\.json",
        rf"(?P<p>{re.escape(sessions_dir)}/[^\s\"']+?)/inputs/task_context/[A-Za-z0-9_.-]+\\.md",
        rf"(?P<p>{re.escape(sessions_dir)}/[^\s\"']+?)/inputs/context_pack\\.md",
        rf"(?P<p>{re.escape(sessions_dir)}/[^\s\"']+?)/planning/actions\\.json",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            base = m.group("p")
            candidate = Path(base.strip("\"'")).expanduser()
            candidate = candidate if candidate.is_absolute() else (project_root / candidate)
            candidate = candidate.resolve()
            if (candidate / "session.json").exists():
                return candidate

    blob = text.lower()
    if not any(marker in blob for marker in ("planning/actions.json", "inputs/task_context", "inputs/context_pack.md", "session_artifacts:")):
        return None

    root = (project_root / sessions_dir).resolve()
    if not root.exists() or not root.is_dir():
        return None
    best: tuple[float, Path] | None = None
    try:
        for p in root.iterdir():
            if not p.is_dir():
                continue
            if not (p / "session.json").exists():
                continue
            try:
                mtime = p.stat().st_mtime
            except Exception:
                continue
            if best is None or mtime > best[0]:
                best = (mtime, p)
    except Exception:
        return None
    return best[1] if best else None


def _parse_final_contract(text: str) -> ParsedContract | None:
    idx_art = text.rfind("SESSION_ARTIFACTS:")
    if idx_art < 0:
        return None
    idx_status = text.rfind("STATUS:", 0, idx_art)
    if idx_status < 0:
        return None
    block = text[idx_status:]

    m_status = re.search(r"(?im)^\\s*STATUS:\\s*(?P<v>.+?)\\s*$", block)
    m_summary = re.search(r"(?im)^\\s*SUMMARY:\\s*(?P<v>.+?)\\s*$", block)
    if not m_status or not m_summary:
        return None
    status = m_status.group("v").strip()
    summary = m_summary.group("v").strip()

    repo_diff_lines: list[str] = []
    m_repo = re.search(r"(?im)^\\s*REPO_DIFF:\\s*$", block)
    if m_repo:
        after = block[m_repo.end() :]
        for line in after.splitlines():
            if re.match(r"(?im)^\\s*SESSION_ARTIFACTS:\\s*$", line):
                break
            if not line.strip():
                continue
            repo_diff_lines.append(line.rstrip())

    artifact_lines: list[str] = []
    artifact_paths: list[str] = []
    m_art = re.search(r"(?im)^\\s*SESSION_ARTIFACTS:\\s*$", block)
    if not m_art:
        return None
    after = block[m_art.end() :]
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            break
        if stripped in ("---", "***", "___"):
            break
        artifact_lines.append(line.rstrip())
        m = re.match(r"(?im)^\\s*(?:[AMD]\\s+)?(?P<path>[^\\s].*?)\\s*$", line)
        if m:
            artifact_paths.append(m.group("path").strip())

    if not artifact_paths:
        return None

    return ParsedContract(
        status=status,
        summary=summary,
        repo_diff_lines=repo_diff_lines,
        session_artifact_lines=artifact_lines,
        session_artifact_paths=artifact_paths,
    )


def _validate_artifacts(session_dir: Path, contract: ParsedContract) -> list[str]:
    missing: list[str] = []
    for rel in contract.session_artifact_paths:
        if rel.startswith(("/", "~")):
            p = Path(rel).expanduser()
        else:
            p = (session_dir / rel).resolve()
        if not p.exists():
            missing.append(rel)
            continue
        if p.suffix.lower() == ".json":
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                missing.append(f"{rel} (invalid JSON)")
    return missing


_MAX_CONTRACT_RETRIES = 3
_MAX_RETRY_WINDOW_SECONDS = 300


def _circuit_breaker_path(session_dir: Path) -> Path:
    return session_dir / ".contract_retry_state.json"


def _load_circuit_breaker(session_dir: Path, transcript_key: str) -> dict[str, Any]:
    cb_path = _circuit_breaker_path(session_dir)
    state: dict[str, Any] = {"transcript": "", "count": 0, "first_failure_at": ""}
    if cb_path.exists():
        try:
            state = json.loads(cb_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if state.get("transcript") != transcript_key:
        state = {"transcript": transcript_key, "count": 0, "first_failure_at": ""}
    return state


def _save_circuit_breaker(session_dir: Path, state: dict[str, Any]) -> None:
    try:
        _circuit_breaker_path(session_dir).write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _clear_circuit_breaker(session_dir: Path) -> None:
    try:
        _circuit_breaker_path(session_dir).unlink(missing_ok=True)
    except Exception:
        pass


def _artifacts_exist_on_disk(session_dir: Path) -> bool:
    actions = session_dir / "planning" / "actions.json"
    if actions.exists():
        try:
            data = json.loads(actions.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tasks" in data:
                return True
        except Exception:
            pass
    for subdir in ("implementation/tasks", "testing/tasks"):
        d = session_dir / subdir
        try:
            if d.is_dir() and any(d.iterdir()):
                return True
        except Exception:
            pass
    return False


def _circuit_breaker_check(session_dir: Path, transcript_path: str) -> tuple[bool, str]:
    from datetime import datetime, timezone

    state = _load_circuit_breaker(session_dir, transcript_path)
    count = state.get("count", 0) + 1
    first_failure = state.get("first_failure_at", "")

    now_iso = datetime.now(timezone.utc).isoformat()
    if not first_failure:
        first_failure = now_iso

    state["count"] = count
    state["first_failure_at"] = first_failure
    _save_circuit_breaker(session_dir, state)

    elapsed = 0.0
    try:
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(first_failure)).total_seconds()
    except Exception:
        pass

    if elapsed > _MAX_RETRY_WINDOW_SECONDS:
        has_artifacts = _artifacts_exist_on_disk(session_dir)
        detail = "Artifacts found on disk; accepting without contract." if has_artifacts else "Passing through to prevent infinite loop."
        return True, f"Circuit breaker: timeout after {elapsed:.0f}s ({count} retries). {detail}"

    if count > _MAX_CONTRACT_RETRIES:
        has_artifacts = _artifacts_exist_on_disk(session_dir)
        if has_artifacts:
            return True, f"Circuit breaker: retries exceeded ({count}). Artifacts found on disk; accepting without contract."
        if count > _MAX_CONTRACT_RETRIES * 2:
            return True, f"Circuit breaker: hard limit reached ({count} retries). Passing through."

    return False, ""


def main() -> int:
    hook_input = _read_hook_input()
    if not hook_input or hook_input.get("hook_event_name") != "SubagentStop":
        return 0

    agent_name = hook_input.get("agent")
    if not isinstance(agent_name, str) or agent_name.strip() not in AT_AGENT_IDS:
        return 0

    agent_transcript = hook_input.get("agent_transcript_path")
    if not isinstance(agent_transcript, str) or not agent_transcript.strip():
        return 0

    project_root = detect_project_dir()
    sessions_dir = get_sessions_dir(project_root)

    transcript_path = Path(agent_transcript).expanduser()
    transcript_text = _extract_text_from_transcript(transcript_path)
    if not transcript_text:
        return 0

    claude_session_id = hook_input.get("session_id")
    active = resolve_session_dir_from_hook(
        project_root=project_root,
        sessions_dir=sessions_dir,
        claude_session_id=str(claude_session_id) if isinstance(claude_session_id, str) else None,
    )
    session_dir = active.session_dir if active else None
    if session_dir is None:
        session_dir = _find_session_dir_from_text(project_root, sessions_dir, transcript_text)
    if session_dir is None:
        return 0

    contract = _parse_final_contract(transcript_text)
    if contract is None:
        tripped, reason = _circuit_breaker_check(session_dir, agent_transcript)
        if tripped:
            print(f"at SubagentStop: {reason}", file=sys.stderr)
            return 0
        print(
            "at SubagentStop validation failed: missing final reply contract.\n"
            "Required block must include: STATUS, SUMMARY, REPO_DIFF, SESSION_ARTIFACTS.\n"
            "Fix by replying again with the exact contract block from your agent instructions.",
            file=sys.stderr,
        )
        return 2

    missing = _validate_artifacts(session_dir, contract)
    if missing:
        tripped, reason = _circuit_breaker_check(session_dir, agent_transcript)
        if tripped:
            print(f"at SubagentStop: {reason}", file=sys.stderr)
            return 0
        lines = ["at SubagentStop validation failed: missing session artifacts:"]
        lines.extend([f"- {m}" for m in missing[:50]])
        if len(missing) > 50:
            lines.append(f"- … ({len(missing) - 50} more)")
        lines.append("")
        lines.append("Create the missing artifacts and then re-send your final reply contract block.")
        print("\n".join(lines), file=sys.stderr)
        return 2

    _clear_circuit_breaker(session_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
