#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
at: Verifications gate (binary)

Thin wrapper around scripts/validate/run_verifications.py.

Version: 0.1.0
Updated: 2026-02-01
"""
from __future__ import annotations

from validate.run_verifications import main


if __name__ == "__main__":
    raise SystemExit(main())

