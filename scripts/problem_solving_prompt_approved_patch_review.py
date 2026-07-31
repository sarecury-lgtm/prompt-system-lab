#!/usr/bin/env python3
"""Run the manual prompt patch review with approved baseline assets enabled."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "scripts" / "problem_solving_prompt_patch_review.py"
APPROVED_PATH = ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEW = _load_module(
    "psos_manual_patch_review_with_approved_baselines",
    REVIEW_PATH,
)
APPROVED = _load_module(
    "psos_approved_baseline_for_manual_review",
    APPROVED_PATH,
)
_ORIGINAL_BASELINE_PROMPT = REVIEW.baseline_prompt


def approved_baseline_prompt(case: Mapping[str, Any]) -> str:
    request = REVIEW._require_text(case.get("request"), "case.request")
    approved = APPROVED.select_approved_prompt(request)
    return approved["prompt"] if approved is not None else _ORIGINAL_BASELINE_PROMPT(case)


REVIEW.baseline_prompt = approved_baseline_prompt

prepare_review = REVIEW.prepare_review
finalize_review = REVIEW.finalize_review


def main(argv: list[str] | None = None) -> int:
    return REVIEW.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
