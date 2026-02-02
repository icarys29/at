#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Git helpers (best-effort)

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitInfo:
    ok: bool
    repo_root: Path | None = None
    head: str | None = None
    branch: str | None = None


def _run_git(project_root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def detect_git(project_root: Path) -> GitInfo:
    try:
        inside = _run_git(project_root, ["rev-parse", "--is-inside-work-tree"])
    except Exception:
        return GitInfo(ok=False)
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        return GitInfo(ok=False)

    root = _run_git(project_root, ["rev-parse", "--show-toplevel"])
    repo_root: Path | None = None
    if root.returncode == 0:
        try:
            repo_root = Path(root.stdout.decode("utf-8", errors="ignore").strip()).resolve()
        except Exception:
            repo_root = None

    head = _run_git(project_root, ["rev-parse", "HEAD"])
    head_s = head.stdout.decode("utf-8", errors="ignore").strip() if head.returncode == 0 else None

    branch = _run_git(project_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch_s = branch.stdout.decode("utf-8", errors="ignore").strip() if branch.returncode == 0 else None

    return GitInfo(ok=True, repo_root=repo_root, head=head_s or None, branch=branch_s or None)


def git_changed_files(project_root: Path) -> tuple[set[str], list[str]]:
    """
    Return (changed_files, warnings) best-effort.

    Includes:
    - staged tracked changes
    - unstaged tracked changes
    - untracked (non-ignored) files
    """
    warnings: list[str] = []
    info = detect_git(project_root)
    if not info.ok:
        return (set(), ["git not available"])

    files: set[str] = set()

    def _add_from(proc: subprocess.CompletedProcess[bytes], label: str) -> None:
        if proc.returncode != 0:
            warnings.append(f"git {label} failed: {proc.stderr.decode('utf-8', errors='ignore').strip()}")
            return
        for line in proc.stdout.splitlines():
            s = line.decode("utf-8", errors="ignore").strip().replace("\\", "/")
            if s:
                files.add(s)

    _add_from(_run_git(project_root, ["diff", "--name-only"]), "diff --name-only")
    _add_from(_run_git(project_root, ["diff", "--name-only", "--cached"]), "diff --name-only --cached")

    untracked = _run_git(project_root, ["ls-files", "--others", "--exclude-standard"])
    _add_from(untracked, "ls-files --others --exclude-standard")

    return (files, warnings)
