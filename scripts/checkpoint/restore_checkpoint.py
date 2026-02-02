#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Restore a rollback checkpoint for a session (git required)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.git import detect_git  # noqa: E402
from lib.io import utc_now, write_text  # noqa: E402
from lib.path_policy import normalize_repo_relative_posix_path  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402

import subprocess  # noqa: E402


def _run_git(project_root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _safe_extract_tar(project_root: Path, tar_path: Path) -> tuple[int, list[str]]:
    warnings: list[str] = []
    if not tar_path.exists():
        return (0, warnings)
    n = 0
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            norm = normalize_repo_relative_posix_path(member.name)
            if not norm:
                warnings.append(f"skip unsafe tar member: {member.name!r}")
                continue
            target = (project_root / norm).resolve()
            try:
                target.relative_to(project_root.resolve())
            except Exception:
                warnings.append(f"skip tar member outside project root: {member.name!r}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            f = tf.extractfile(member)
            if f is None:
                continue
            target.write_bytes(f.read())
            n += 1
    return (n, warnings)


def _select_checkpoint_dir(session_dir: Path, checkpoint_arg: str | None) -> Path:
    checkpoints = session_dir / "checkpoints"
    if not checkpoints.exists():
        raise RuntimeError(f"No checkpoints directory under session: {checkpoints}")
    if checkpoint_arg:
        p = Path(checkpoint_arg).expanduser()
        candidates = [p, session_dir / "checkpoints" / checkpoint_arg]
        for c in candidates:
            try:
                r = c.resolve()
            except Exception:
                continue
            if r.is_dir() and (r / "checkpoint.json").exists():
                return r
        raise RuntimeError(f"Checkpoint not found: {checkpoint_arg!r}")
    dirs = [p for p in sorted(checkpoints.iterdir(), reverse=True) if p.is_dir() and (p / "checkpoint.json").exists()]
    if not dirs:
        raise RuntimeError("No checkpoints found.")
    return dirs[0].resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a checkpoint created by create_checkpoint.py (git required).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--checkpoint", default=None, help="Checkpoint id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)
    cp_dir = _select_checkpoint_dir(session_dir, args.checkpoint)

    report_path = cp_dir / "RESTORE_REPORT.md"

    info = detect_git(project_root)
    if not info.ok:
        write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- reason: git unavailable\n")
        print(f"ERROR: git unavailable (cannot restore checkpoint).", file=sys.stderr)
        return 1

    meta_path = cp_dir / "checkpoint.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- reason: invalid checkpoint.json ({exc})\n")
        print(f"ERROR: invalid checkpoint.json: {exc}", file=sys.stderr)
        return 1

    git_meta = meta.get("git") if isinstance(meta, dict) else None
    head = (git_meta.get("head") if isinstance(git_meta, dict) else None) if git_meta else None
    if not isinstance(head, str) or not head.strip():
        write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- reason: checkpoint missing git.head\n")
        print("ERROR: checkpoint missing git.head", file=sys.stderr)
        return 1

    # Restore tracked state.
    reset = _run_git(project_root, ["reset", "--hard", head.strip()])
    if reset.returncode != 0:
        err = reset.stderr.decode("utf-8", errors="ignore").strip()
        write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- git.reset: `{reset.returncode}`\n- stderr: {err}\n")
        print(f"ERROR: git reset failed: {err}", file=sys.stderr)
        return 1

    # Remove untracked (non-ignored) created since checkpoint.
    clean = _run_git(project_root, ["clean", "-fd"])
    clean_warn = clean.stderr.decode("utf-8", errors="ignore").strip() if clean.returncode != 0 else ""

    # Restore untracked snapshot (best-effort).
    extracted, extract_warnings = _safe_extract_tar(project_root, cp_dir / "untracked.tar.gz")

    # Restore staged/unstaged diffs.
    staged_patch = cp_dir / "staged.patch"
    if staged_patch.exists() and staged_patch.stat().st_size > 0:
        ap = _run_git(project_root, ["apply", "--binary", "--index", str(staged_patch)])
        if ap.returncode != 0:
            err = ap.stderr.decode("utf-8", errors="ignore").strip()
            write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- reason: git apply --index failed\n- stderr: {err}\n")
            print(f"ERROR: git apply --index failed: {err}", file=sys.stderr)
            return 1

    unstaged_patch = cp_dir / "unstaged.patch"
    if unstaged_patch.exists() and unstaged_patch.stat().st_size > 0:
        ap2 = _run_git(project_root, ["apply", "--binary", str(unstaged_patch)])
        if ap2.returncode != 0:
            err = ap2.stderr.decode("utf-8", errors="ignore").strip()
            write_text(report_path, f"# Checkpoint Restore\n\n- time: `{utc_now()}`\n- status: FAILED\n- reason: git apply failed\n- stderr: {err}\n")
            print(f"ERROR: git apply failed: {err}", file=sys.stderr)
            return 1

    warn_lines = []
    if clean_warn:
        warn_lines.append(f"- warning: git clean stderr: {clean_warn}")
    for w in extract_warnings[:20]:
        warn_lines.append(f"- warning: {w}")
    warn_block = "\n".join(warn_lines) + ("\n" if warn_lines else "")

    write_text(
        report_path,
        "# Checkpoint Restore\n\n"
        f"- time: `{utc_now()}`\n"
        "- status: OK\n"
        f"- restored_head: `{head.strip()}`\n"
        f"- untracked_extracted: `{extracted}`\n"
        f"{warn_block}",
    )
    print(str(cp_dir))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
