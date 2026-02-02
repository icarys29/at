#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Friendly error messages library

Version: 0.5.0
Updated: 2026-02-02

Provides user-friendly error messages with fix suggestions.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO


@dataclass
class FriendlyError:
    """A user-friendly error with context and fix suggestions."""
    title: str
    details: str
    fix: str | None = None
    example: str | None = None
    help_topic: str | None = None


# Error catalog - add new errors here
ERROR_CATALOG: dict[str, FriendlyError] = {
    "ACTIONS_MISSING_ACCEPTANCE_CRITERIA": FriendlyError(
        title="Plan validation failed: Missing acceptance criteria",
        details="Task '{task_id}' needs acceptance criteria to define how to verify it's complete.",
        fix="Add an 'acceptance_criteria' array to the task with at least one criterion.",
        example='''"acceptance_criteria": [
  {
    "id": "ac-1",
    "statement": "Function returns expected output",
    "verifications": [
      {"type": "command", "command": "pytest tests/test_feature.py -k test_name"}
    ]
  }
]''',
        help_topic="acceptance-criteria",
    ),
    "ACTIONS_MISSING_FILE_SCOPE": FriendlyError(
        title="Plan validation failed: Missing file scope",
        details="Task '{task_id}' needs file_scope.allow[] to define which files it can read.",
        fix="Add a 'file_scope' object with an 'allow' array of glob patterns.",
        example='''"file_scope": {
  "allow": ["src/**/*.py", "tests/**/*.py"],
  "writes": ["src/feature.py"]
}''',
        help_topic="file-scope",
    ),
    "ACTIONS_MISSING_WRITES": FriendlyError(
        title="Plan validation failed: Missing write scope",
        details="Task '{task_id}' is a code task but doesn't declare file_scope.writes[].",
        fix="Add exact file paths (no globs) to file_scope.writes[].",
        example='''"file_scope": {
  "allow": ["src/**/*.py"],
  "writes": ["src/auth/login.py", "src/auth/utils.py"]
}''',
        help_topic="parallel-execution",
    ),
    "ACTIONS_OVERLAPPING_WRITES": FriendlyError(
        title="Plan validation failed: Overlapping write scopes",
        details="Tasks '{task1}' and '{task2}' in the same parallel group both write to '{path}'.",
        fix="Either move tasks to different parallel groups or split the file into separate concerns.",
        example="Group tasks that write to the same directory in sequence, not parallel.",
        help_topic="parallel-execution",
    ),
    "ACTIONS_GLOB_IN_WRITES": FriendlyError(
        title="Plan validation failed: Glob pattern in writes",
        details="Task '{task_id}' uses glob pattern '{pattern}' in file_scope.writes[].",
        fix="Use exact file paths or directory prefixes (ending in '/') instead of globs.",
        example='''"writes": ["src/components/"] or "writes": ["src/components/Button.tsx"]''',
        help_topic="file-scope",
    ),
    "ACTIONS_TASK_NOT_IN_GROUP": FriendlyError(
        title="Plan validation failed: Task not in parallel group",
        details="Task '{task_id}' is a code task but isn't in any parallel_execution.groups[].",
        fix="Add the task ID to a parallel group's tasks[] array.",
        example='''"parallel_execution": {
  "enabled": true,
  "groups": [
    {"group_id": "g1", "execution_order": 1, "tasks": ["task-id-here"]}
  ]
}''',
        help_topic="parallel-execution",
    ),
    "ACTIONS_CIRCULAR_DEPENDENCY": FriendlyError(
        title="Plan validation failed: Circular dependency",
        details="Tasks form a cycle: {cycle}",
        fix="Remove one of the depends_on references to break the cycle.",
        example="If A depends on B and B depends on A, remove one dependency.",
        help_topic="task-dependencies",
    ),
    "GATE_QUALITY_FAILED": FriendlyError(
        title="Quality gate failed",
        details="Command '{command}' exited with code {exit_code}.",
        fix="Review the command output in the log file and fix the issues.",
        example="See: {log_path}",
        help_topic="quality-gate",
    ),
    "GATE_DOCS_FAILED": FriendlyError(
        title="Documentation gate failed",
        details="Documentation is out of sync with code changes.",
        fix="Run /at:docs sync to update documentation, or manually update the affected docs.",
        help_topic="docs-keeper",
    ),
    "SCOPE_VIOLATION": FriendlyError(
        title="Write scope violation",
        details="Task '{task_id}' attempted to write to '{path}' which is outside its declared scope.",
        fix="Either add the path to file_scope.writes[] in the plan, or modify a different file.",
        example="Allowed writes: {allowed_writes}",
        help_topic="file-scope",
    ),
    "SESSION_NOT_FOUND": FriendlyError(
        title="Session not found",
        details="Could not find session '{session_id}' in {sessions_dir}.",
        fix="Run /at:sessions to list available sessions, or start a new session with /at:run.",
        help_topic="sessions",
    ),
    "CONFIG_INVALID": FriendlyError(
        title="Configuration error",
        details="{details}",
        fix="Run /at:doctor to diagnose and fix configuration issues.",
        help_topic="configuration",
    ),
}


def format_error(
    error_code: str,
    **kwargs: str,
) -> str:
    """Format a friendly error message with substitutions.

    Args:
        error_code: Key from ERROR_CATALOG
        stream: Output stream (default stderr)
        **kwargs: Values to substitute in the error template

    Returns:
        Formatted error string
    """
    err = ERROR_CATALOG.get(error_code)
    if not err:
        return f"Unknown error: {error_code}"

    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"ERROR: {err.title.format(**kwargs)}")
    lines.append(f"{'='*60}\n")
    lines.append(err.details.format(**kwargs))
    lines.append("")

    if err.fix:
        lines.append(f"FIX: {err.fix.format(**kwargs)}")
        lines.append("")

    if err.example:
        lines.append("EXAMPLE:")
        for line in err.example.format(**kwargs).split("\n"):
            lines.append(f"  {line}")
        lines.append("")

    if err.help_topic:
        lines.append(f"MORE INFO: /at:help {err.help_topic}")
        lines.append("")

    return "\n".join(lines)


def print_error(error_code: str, *, stream: TextIO = sys.stderr, **kwargs: str) -> None:
    """Print a friendly error message."""
    print(format_error(error_code, **kwargs), file=stream)


def print_simple_error(title: str, details: str, *, fix: str | None = None, stream: TextIO = sys.stderr) -> None:
    """Print a simple error without using the catalog."""
    lines = []
    lines.append(f"\nERROR: {title}")
    lines.append(details)
    if fix:
        lines.append(f"\nFIX: {fix}")
    lines.append("")
    print("\n".join(lines), file=stream)
