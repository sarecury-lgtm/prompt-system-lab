#!/usr/bin/env python3
"""Run canonical PSOS with the stabilized router and execution semantics."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_core_semantic_fixes as semantic_fixes
import problem_solving_os as problem_os

semantic_fixes.apply(problem_os)


if __name__ == "__main__":
    raise SystemExit(problem_os.main())
