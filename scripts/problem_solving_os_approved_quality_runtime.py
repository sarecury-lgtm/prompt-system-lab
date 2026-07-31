#!/usr/bin/env python3
"""Run the PSOS quality runtime with approved PROMPT baselines enabled."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALITY_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os_quality_runtime.py"
APPROVED_PATH = ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


QUALITY = _load_module(
    "psos_quality_runtime_with_approved_baselines",
    QUALITY_RUNTIME_PATH,
)
APPROVED = _load_module(
    "psos_approved_prompt_baseline_runtime",
    APPROVED_PATH,
)
APPROVED.patch_quality_runtime(QUALITY)

run_request = QUALITY.run_request
OS = QUALITY.OS


def main(argv: list[str] | None = None) -> int:
    return QUALITY.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
