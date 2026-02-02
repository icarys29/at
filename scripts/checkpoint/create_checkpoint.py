#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Create a rollback checkpoint for a session (git best-effort)

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
from lib.io import utc_now, write_json, write_text  # noqa: E402
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


def _next_checkpoint_id(checkpoints_dir: Path) -> str:
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted([p.name for p in checkpoints_dir.iterdir() if p.is_dir()])
    n = 1
    while True:
        cid = f"cp-{n:03d}"
        if cid not in existing:
            return cid
        n += 1


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _tar_untracked(project_root: Path, untracked_paths: list[str], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with tarfile.open(out_path, "w:gz") as tf:
        for raw in untracked_paths:
            norm = normalize_repo_relative_posix_path(raw)
            if not norm:
                continue
            src = (project_root / norm).resolve()
            try:
                src.relative_to(project_root.resolve())
            except Exception:
                continue
            if not src.exists() or not src.is_file():
                continue
            tf.add(str(src), arcname=norm, recursive=False)
            added += 1
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a git-based checkpoint under SESSION_DIR/checkpoints/ for rollback.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    parser.add_argument("--checkpoint-id", default=None, help="Optional checkpoint id (default: cp-###)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    checkpoints_dir = session_dir / "checkpoints"
    checkpoint_id = args.checkpoint_id.strip() if isinstance(args.checkpoint_id, str) and args.checkpoint_id.strip() else _next_checkpoint_id(checkpoints_dir)
    cp_dir = (checkpoints_dir / checkpoint_id).resolve()
    cp_dir.mkdir(parents=True, exist_ok=True)

    info = detect_git(project_root)
    meta: dict[str, object] = {"version": 1, "created_at": utc_now(), "checkpoint_id": checkpoint_id, "git": {"available": bool(info.ok)}}

    if not info.ok:
        write_json(cp_dir / "checkpoint.json", meta)
        write_text(cp_dir / "CHECKPOINT.md", "# Checkpoint\n\n- git: unavailable (checkpoint contains no repo snapshot)\n")
        print(str(cp_dir))
        return 0

    head = info.head or ""
    branch = info.branch or ""
    meta["git"] = {"available": True, "repo_root": str(info.repo_root or ""), "head": head, "branch": branch}

    status = _run_git(project_root, ["status", "--porcelain=v1"])
    _write_bytes(cp_dir / "status_porcelain.txt", status.stdout)

    unstaged = _run_git(project_root, ["diff", "--binary"])
    staged = _run_git(project_root, ["diff", "--binary", "--staged"])
    _write_bytes(cp_dir / "unstaged.patch", unstaged.stdout)
    _write_bytes(cp_dir / "staged.patch", staged.stdout)

    untracked = _run_git(project_root, ["ls-files", "--others", "--exclude-standard", "-z"])
    untracked_paths = [p.decode("utf-8", errors="ignore") for p in untracked.stdout.split(b"\x00") if p]
    (cp_dir / "untracked_paths.txt").write_text("\n".join(untracked_paths) + ("\n" if untracked_paths else ""), encoding="utf-8")
    untracked_count = _tar_untracked(project_root, untracked_paths, cp_dir / "untracked.tar.gz") if untracked_paths else 0

    write_json(cp_dir / "checkpoint.json", meta)
    write_text(
        cp_dir / "CHECKPOINT.md",
        "# Checkpoint\n\n"
        f"- id: `{checkpoint_id}`\n"
        f"- created_at: `{meta.get('created_at','')}`\n"
        f"- git.head: `{head}`\n"
        f"- git.branch: `{branch}`\n"
        f"- untracked_files_archived: `{untracked_count}`\n",
    )

    print(str(cp_dir))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
