#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Simple YAML parser

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class YamlLine:
    indent: int
    content: str


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def _parse_scalar(value: str) -> Any:
    v = value.strip()
    v = _strip_quotes(v)
    low = v.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    if low.isdigit():
        try:
            return int(low)
        except Exception:
            return v
    return v


def _preprocess(text: str) -> list[YamlLine]:
    lines: list[YamlLine] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        if stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        lines.append(YamlLine(indent=indent, content=stripped))
    return lines


def load_minimal_yaml(text: str) -> dict[str, Any]:
    """
    Parse a minimal YAML subset:
    - mappings: `key: value` and `key:` (nested)
    - lists:
      - scalars: `- item` under a `key:` where the next line starts with `- `
      - flat objects: `- key: value` plus additional `key: value` lines indented under the list item
    - scalars: strings/bools/ints (strings may be quoted)

    This is intentionally conservative and is designed for the plugin-generated
    `.claude/project.yaml` format. It is not a general-purpose YAML parser.
    """

    lines = _preprocess(text)
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    def _peek_next(i: int) -> YamlLine | None:
        return lines[i + 1] if i + 1 < len(lines) else None

    for i, item in enumerate(lines):
        indent = item.indent
        content = item.content

        while indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]

        if content.startswith("- "):
            if not isinstance(container, list):
                raise ValueError(f"Invalid YAML: list item without list container: {content!r}")
            body = content[2:].strip()
            if not body:
                # Nested container as a list item (rare in our plugin; supported conservatively)
                next_line = _peek_next(i)
                new_value: Any
                if next_line and next_line.indent > indent and next_line.content.startswith("- "):
                    new_value = []
                else:
                    new_value = {}
                container.append(new_value)
                stack.append((indent, new_value))
                continue

            # Flat mapping item (e.g. "- path: foo")
            if ":" in body:
                key, rest = body.split(":", 1)
                key = key.strip()
                rest = rest.strip()
                if not key:
                    raise ValueError(f"Invalid YAML: empty key in list item: {content!r}")
                if rest == "":
                    # We intentionally do not support nested values under a list-item inline key,
                    # because it complicates parsing and isn't needed for our generated files.
                    raise ValueError(
                        "Invalid YAML: list item inline mapping with nested value is not supported "
                        f"(use '- {key}: <scalar>' instead): {content!r}"
                    )
                obj: dict[str, Any] = {key: _parse_scalar(rest)}
                container.append(obj)
                stack.append((indent, obj))
                continue

            # Scalar list item
            container.append(_parse_scalar(body))
            continue

        if ":" not in content:
            raise ValueError(f"Invalid YAML: expected key:value mapping, got: {content!r}")

        key, rest = content.split(":", 1)
        key = key.strip()
        rest = rest.strip()

        if not isinstance(container, dict):
            raise ValueError(f"Invalid YAML: mapping inside non-mapping container: {content!r}")

        if rest:
            container[key] = _parse_scalar(rest)
            continue

        # Nested mapping or list (decide via lookahead)
        next_line = _peek_next(i)
        if next_line and next_line.indent > indent and next_line.content.startswith("- "):
            new_value: Any = []
        else:
            new_value = {}
        container[key] = new_value
        stack.append((indent, new_value))

    return root
