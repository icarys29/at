#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Run configured quality suite (format/lint/typecheck/test/build)

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from lib.io import utc_now, write_json, write_text  # noqa: E402
from lib.project import detect_project_dir, get_sessions_dir, load_project_config  # noqa: E402
from lib.session import resolve_session_dir  # noqa: E402


@dataclass(frozen=True)
class CommandSpec:
    id: str
    command: str
    requires_env: list[str]
    requires_files: list[str]
    env_file: str | None


def _has_glob_chars(s: str) -> bool:
    return any(ch in s for ch in ["*", "?", "[", "]"])


def _files_exist(project_root: Path, patterns: list[str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for pat in patterns:
        if not isinstance(pat, str) or not pat.strip():
            continue
        p = pat.strip()
        if _has_glob_chars(p):
            matches = list((project_root).glob(p))
            if not matches:
                missing.append(p)
        else:
            if not (project_root / p).exists():
                missing.append(p)
    return (len(missing) == 0, missing)


def _load_language_packs(project_root: Path) -> dict[str, dict[str, Any]]:
    root = (project_root / ".claude" / "at" / "languages").resolve()
    if not root.exists() or not root.is_dir():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(root.glob("*.json"))[:50]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("version") != 1:
            continue
        lang = data.get("language")
        if isinstance(lang, str) and lang.strip():
            out[lang.strip()] = data
    return out


def _load_e2e_config(project_root: Path) -> dict[str, Any] | None:
    """
    Load `.claude/at/e2e.json` if present.
    This is a project overlay file (not `project.yaml`) to keep setup deterministic.
    """
    p = (project_root / ".claude" / "at" / "e2e.json").resolve()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("version") == 1 else None


def _suite_from_e2e_config(project_root: Path, *, cfg: dict[str, Any] | None) -> list[CommandSpec]:
    if not cfg:
        return []
    if cfg.get("enabled") is not True:
        return []
    cid = cfg.get("id") if isinstance(cfg.get("id"), str) and cfg.get("id").strip() else "e2e"
    cmd = cfg.get("command") if isinstance(cfg.get("command"), str) else ""
    if not cmd.strip():
        return []
    req_env = cfg.get("requires_env") if isinstance(cfg.get("requires_env"), list) else []
    req_files = cfg.get("requires_files") if isinstance(cfg.get("requires_files"), list) else []
    env_file = cfg.get("env_file") if isinstance(cfg.get("env_file"), str) and cfg.get("env_file").strip() else None
    return [
        CommandSpec(
            id=str(cid).strip(),
            command=str(cmd).strip(),
            requires_env=[str(x).strip() for x in req_env if isinstance(x, str) and x.strip()],
            requires_files=[str(x).strip() for x in req_files if isinstance(x, str) and x.strip()],
            env_file=env_file.strip() if isinstance(env_file, str) else None,
        )
    ]


def _suite_from_language_packs(
    project_root: Path,
    *,
    packs: dict[str, dict[str, Any]],
    languages: list[str],
) -> list[CommandSpec]:
    suite: list[CommandSpec] = []
    for lang in languages[:12]:
        pack = packs.get(lang)
        if not isinstance(pack, dict):
            continue
        items = pack.get("suggested_quality_suite")
        if not isinstance(items, list) or not items:
            continue
        for it in items[:50]:
            if not isinstance(it, dict):
                continue
            cid = it.get("id")
            cmd = it.get("command")
            if not isinstance(cid, str) or not cid.strip() or not isinstance(cmd, str) or not cmd.strip():
                continue
            req_env = it.get("requires_env") if isinstance(it.get("requires_env"), list) else []
            req_files = it.get("requires_files") if isinstance(it.get("requires_files"), list) else []
            suite.append(
                CommandSpec(
                    id=cid.strip(),
                    command=cmd.strip(),
                    requires_env=[str(x).strip() for x in req_env if isinstance(x, str) and x.strip()],
                    requires_files=[str(x).strip() for x in req_files if isinstance(x, str) and x.strip()],
                    env_file=None,
                )
            )
    return suite


def _build_suite_from_config(project_root: Path, config: dict[str, Any] | None) -> list[CommandSpec]:
    cfg = config if isinstance(config, dict) else {}
    commands = cfg.get("commands") if isinstance(cfg.get("commands"), dict) else {}

    # Preferred: explicit list under commands.quality_suite
    explicit = commands.get("quality_suite")
    if isinstance(explicit, list) and explicit:
        suite: list[CommandSpec] = []
        for i, item in enumerate(explicit[:200]):
            if not isinstance(item, dict):
                continue
            cid = item.get("id")
            cmd = item.get("command")
            if not isinstance(cid, str) or not cid.strip():
                cid = f"cmd-{i+1:02d}"
            if not isinstance(cmd, str) or not cmd.strip():
                continue
            req_env = item.get("requires_env") if isinstance(item.get("requires_env"), list) else []
            req_files = item.get("requires_files") if isinstance(item.get("requires_files"), list) else []
            suite.append(
                CommandSpec(
                    id=str(cid).strip(),
                    command=str(cmd).strip(),
                    requires_env=[str(x).strip() for x in req_env if isinstance(x, str) and x.strip()],
                    requires_files=[str(x).strip() for x in req_files if isinstance(x, str) and x.strip()],
                    env_file=str(item.get("env_file")).strip() if isinstance(item.get("env_file"), str) and item.get("env_file").strip() else None,
                )
            )
        return suite

    # Legacy: derive from commands.<language>.{format,lint,typecheck,test,build}
    project = cfg.get("project") if isinstance(cfg.get("project"), dict) else {}
    langs = project.get("primary_languages") if isinstance(project.get("primary_languages"), list) else []
    lang_ids = [str(x).strip() for x in langs if isinstance(x, str) and str(x).strip()]
    selected = [l for l in lang_ids if isinstance(commands.get(l), dict)]
    if not selected:
        selected = [k for k, v in commands.items() if isinstance(k, str) and isinstance(v, dict) and k != "allow_unlisted"]

    suite = []
    for lang in selected[:8]:
        block = commands.get(lang)
        if not isinstance(block, dict):
            continue
        for step in ("format", "lint", "typecheck", "test", "build"):
            cmd = block.get(step)
            if isinstance(cmd, str) and cmd.strip():
                suite.append(CommandSpec(id=f"{lang}:{step}", command=cmd.strip(), requires_env=[], requires_files=[], env_file=None))

    # Optional defaults from installed language packs (opt-in only).
    allow_defaults = commands.get("allow_language_pack_defaults") is True
    if allow_defaults:
        packs = _load_language_packs(project_root)
        # Fill missing language blocks only (avoid surprising duplicates).
        missing_langs = [l for l in (lang_ids or sorted(packs.keys())) if l not in selected]
        suite.extend(_suite_from_language_packs(project_root, packs=packs, languages=missing_langs))

    # Optional: append E2E command configured via `.claude/at/e2e.json`.
    # This stays deterministic and avoids YAML mutation.
    suite.extend(_suite_from_e2e_config(project_root, cfg=_load_e2e_config(project_root)))

    return suite


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_command(project_root: Path, spec: CommandSpec, log_path: Path) -> dict[str, Any]:
    env = dict(os.environ)

    # Optional: load env_file (dotenv-style) for this command (commonly used for E2E).
    if isinstance(spec.env_file, str) and spec.env_file.strip():
        p = (project_root / spec.env_file.strip()).resolve()
        # Do not fail here; treat missing file as a "missing file" skip if declared in requires_files.
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if "=" not in raw:
                        continue
                    k, v = raw.split("=", 1)
                    k = k.strip()
                    if not k:
                        continue
                    env.setdefault(k, v.strip())
            except Exception:
                pass

    missing_env = [k for k in spec.requires_env if not env.get(k)]
    if missing_env:
        return {"id": spec.id, "status": "skipped", "reason": f"missing env: {', '.join(missing_env)}"}

    ok_files, missing = _files_exist(project_root, spec.requires_files)
    if not ok_files:
        return {"id": spec.id, "status": "skipped", "reason": f"missing files: {', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}"}

    start = time.time()
    proc = subprocess.run(
        spec.command,
        cwd=str(project_root),
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    dur_ms = int((time.time() - start) * 1000)

    _write_log(
        log_path,
        f"$ {spec.command}\n\n"
        f"[exit_code={proc.returncode} duration_ms={dur_ms}]\n\n"
        f"{proc.stdout}",
    )

    return {
        "id": spec.id,
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "duration_ms": dur_ms,
        "log_path": str(log_path).replace("\\", "/"),
        "command": spec.command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic quality commands configured in .claude/project.yaml.")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--sessions-dir", default=None)
    parser.add_argument("--session", default=None, help="Session id or directory (default: most recent)")
    args = parser.parse_args()

    project_root = detect_project_dir(args.project_dir)
    config = load_project_config(project_root) or {}
    sessions_dir = args.sessions_dir or get_sessions_dir(project_root, config)
    session_dir = resolve_session_dir(project_root, sessions_dir, args.session)

    suite = _build_suite_from_config(project_root, config)
    out_dir = session_dir / "quality"
    logs_dir = out_dir / "command_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for spec in suite:
        safe_id = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", ":") else "_" for ch in spec.id)[:120]
        log_path = logs_dir / f"{safe_id}.log"
        results.append(_run_command(project_root, spec, log_path))

    # Optional: run repo-local enforcements if installed (CI-friendly).
    enforcement_report: dict[str, Any] | None = None
    runner = project_root / ".claude" / "at" / "scripts" / "run_enforcements.py"
    if runner.exists():
        start = time.time()
        # Prefer writing enforcement evidence under the session for deterministic auditing.
        enforcement_out = out_dir / "enforcement_report.json"

        proc = subprocess.run(
            [sys.executable, str(runner), "--project-root", str(project_root), "--config", str(project_root / ".claude" / "at" / "enforcement.json"), "--json", str(enforcement_out)],
            cwd=str(project_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.returncode != 0:
            # Back-compat: older runners may not support args; retry with no args.
            proc2 = subprocess.run(
                f"python3 \"{runner}\"",
                cwd=str(project_root),
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if proc2.returncode == 0 or proc2.stdout:
                proc = proc2

        dur_ms = int((time.time() - start) * 1000)
        _write_log(logs_dir / "enforcements.log", f"$ {sys.executable} \"{runner}\" …\n\n[exit_code={proc.returncode} duration_ms={dur_ms}]\n\n{proc.stdout}")
        # Best-effort read of generated report (prefer session-scoped file; fallback to repo-local).
        try:
            src = enforcement_out if enforcement_out.exists() else (project_root / ".claude" / "at" / "enforcement_report.json")
            enforcement_report = json.loads(src.read_text(encoding="utf-8"))
        except Exception:
            enforcement_report = {"version": 1, "ok": proc.returncode == 0, "note": "missing/invalid enforcement_report.json"}
        results.append(
            {
                "id": "enforcement",
                "status": "passed" if proc.returncode == 0 else "failed",
                "exit_code": proc.returncode,
                "duration_ms": dur_ms,
                "log_path": str((logs_dir / "enforcements.log")).replace("\\", "/"),
                "command": f"{sys.executable} \"{runner}\"",
            }
        )

    failed = [r for r in results if r.get("status") == "failed"]
    ok = len(failed) == 0

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "ok": ok,
        "commands_total": len(results),
        "commands_failed": len(failed),
        "results": results,
    }
    write_json(out_dir / "quality_report.json", report)
    if enforcement_report is not None:
        write_json(out_dir / "enforcement_report.json", enforcement_report)

    md_lines = [
        "# Quality Report (at)",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- ok: `{str(ok).lower()}`",
        f"- failed: `{len(failed)}` / `{len(results)}`",
        "",
        "## Commands",
        "",
    ]
    for r in results:
        rid = r.get("id", "")
        status = r.get("status", "")
        if status == "skipped":
            md_lines.append(f"- `{rid}`: `skipped` — {r.get('reason','')}")
        elif status == "passed":
            md_lines.append(f"- `{rid}`: `passed` — log: `{r.get('log_path','')}`")
        else:
            md_lines.append(f"- `{rid}`: `failed` (exit={r.get('exit_code','')}) — log: `{r.get('log_path','')}`")
    md_lines.append("")
    write_text(out_dir / "quality_report.md", "\n".join(md_lines))

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
