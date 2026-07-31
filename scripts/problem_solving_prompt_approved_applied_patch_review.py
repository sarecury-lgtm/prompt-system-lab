#!/usr/bin/env python3
"""Run applied-task patch review with approved baseline assets enabled."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
APPLIED_REVIEW_PATH = ROOT / "scripts" / "problem_solving_prompt_applied_patch_review.py"
APPROVED_PATH = ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


APPLIED = _load_module(
    "psos_applied_patch_review_with_approved_baselines",
    APPLIED_REVIEW_PATH,
)
APPROVED = _load_module(
    "psos_approved_baseline_for_applied_review",
    APPROVED_PATH,
)
_ORIGINAL_BASELINE_PROMPT = APPLIED.REVIEW.baseline_prompt


def approved_applied_baseline_prompt(case: Mapping[str, Any]) -> str:
    request = APPLIED.REVIEW._require_text(case.get("request"), "case.request")
    approved = APPROVED.select_approved_prompt(request)
    return approved["prompt"] if approved is not None else _ORIGINAL_BASELINE_PROMPT(case)


APPLIED.REVIEW.baseline_prompt = approved_applied_baseline_prompt

prepare_review = APPLIED.REVIEW.prepare_review
finalize_review = APPLIED.REVIEW.finalize_review
PromptPatchReviewError = APPLIED.REVIEW.PromptPatchReviewError


def main(argv: list[str] | None = None) -> int:
    return APPLIED.REVIEW.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
