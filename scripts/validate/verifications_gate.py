#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Verifications gate (binary)

Thin wrapper around scripts/validate/run_verifications.py.

Version: 0.4.0
Updated: 2026-02-02
"""
from __future__ import annotations

import warnings

# DEPRECATION WARNING: This script will be removed in v0.5.0. See scripts/DEPRECATED.md
warnings.warn(
    "verifications_gate.py is deprecated and will be removed in v0.5.0. "
    "Merged into quality suite. See scripts/DEPRECATED.md for migration.",
    DeprecationWarning,
    stacklevel=2
)

from validate.run_verifications import main


if __name__ == "__main__":
    raise SystemExit(main())

