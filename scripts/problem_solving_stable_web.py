#!/usr/bin/env python3
"""Serve the canonical PSOS UI with stabilized routing and execution semantics."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_core_semantic_fixes as semantic_fixes
import problem_solving_os as problem_os

semantic_fixes.apply(problem_os)

import problem_solving_web as problem_web

# problem_solving_web imported the same module object; keep the dependency explicit.
problem_web.problem_os = problem_os


if __name__ == "__main__":
    raise SystemExit(problem_web.main())
