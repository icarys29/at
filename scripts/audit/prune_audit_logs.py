#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Prune audit logs (dry-run default)

Prunes JSONL files under `.claude/audit_logs/` older than a cutoff (by mtime),
or when total size exceeds a limit.

Version: 0.5.0
Updated: 2026-02-02
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.project import detect_project_dir  # noqa: E402


@dataclass(frozen=True)
class Candidate:
    path: Path
    mtime: float
    size: int


def _iter_audit_files(audit_dir: Path) -> list[Candidate]:
    files: list[Candidate] = []
    if not audit_dir.exists():
        return files
    for p in audit_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in {".jsonl", ".log", ".txt"}:
            continue
        try:
            st = p.stat()
        except Exception:
            continue
        files.append(Candidate(path=p, mtime=st.st_mtime, size=st.st_size))
    files.sort(key=lambda c: (c.mtime, str(c.path)))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune .claude/audit_logs (dry-run default).")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--days", type=int, default=30, help="Delete files older than this many days (mtime).")
    parser.add_argument("--max-total-mb", type=int, default=200, help="If total exceeds this, prune oldest until under.")
    parser.add_argument("--apply", action="store_true", help="Actually delete files (otherwise dry-run).")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    audit_dir = (project_root / ".claude" / "audit_logs").resolve()
    files = _iter_audit_files(audit_dir)

    cutoff = time.time() - (max(args.days, 0) * 86400)
    to_delete: list[Candidate] = [c for c in files if c.mtime < cutoff]

    remaining = [c for c in files if c not in to_delete]
    total = sum(c.size for c in remaining)
    limit = max(args.max_total_mb, 0) * 1024 * 1024
    if limit > 0 and total > limit:
        # delete oldest remaining until under limit
        for c in remaining:
            to_delete.append(c)
            total -= c.size
            if total <= limit:
                break

    # unique paths
    seen: set[str] = set()
    uniq: list[Candidate] = []
    for c in to_delete:
        k = str(c.path)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)

    if not uniq:
        print("OK\t(no audit logs to prune)")
        return 0

    for c in uniq:
        rel = str(c.path.relative_to(project_root)).replace("\\", "/") if str(c.path).startswith(str(project_root)) else str(c.path)
        action = "DELETE" if args.apply else "DRYRUN_DELETE"
        print(f"{action}\t{rel}\t{c.size} bytes")
        if args.apply:
            try:
                c.path.unlink()
            except Exception as exc:
                print(f"WARNING: failed to delete {c.path}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
