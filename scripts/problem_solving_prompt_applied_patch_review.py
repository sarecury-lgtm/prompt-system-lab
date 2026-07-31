#!/usr/bin/env python3
"""Run manual PROMPT patch review with a direct applied-task baseline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "scripts" / "problem_solving_prompt_patch_review.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEW = _load_module(
    "psos_manual_patch_review_with_applied_baseline",
    REVIEW_PATH,
)


def _text_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise REVIEW.PromptPatchReviewError(f"{label}은 문자열 배열이어야 합니다.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise REVIEW.PromptPatchReviewError(f"{label}에 빈 값이 있습니다.")
        result.append(item.strip())
    return result


def applied_baseline_prompt(case: Mapping[str, Any]) -> str:
    """Render the fixture Brief as a minimal prompt that performs the task itself."""

    brief = case.get("brief")
    if not isinstance(brief, Mapping):
        raise REVIEW.PromptPatchReviewError("case.brief가 객체가 아닙니다.")
    goal = REVIEW._require_text(brief.get("goal"), "case.brief.goal")
    groups = (
        ("core_procedure", "처리 절차"),
        ("supporting_inputs", "입력에서 활용할 요소"),
        ("fixed_constraints", "고정 조건"),
        ("output_contract", "출력"),
        ("defaults_and_exceptions", "기본값과 예외"),
        ("exclusions", "제외"),
    )

    lines = [
        "당신은 아래 입력을 처리해 다음 목표를 달성하는 실행 보조자다.",
        "",
        "[목표]",
        goal,
    ]
    for field, heading in groups:
        values = _text_list(brief.get(field), f"case.brief.{field}")
        if not values:
            continue
        lines.extend(["", f"[{heading}]"])
        lines.extend(f"- {item}" for item in values)
    lines.extend(
        [
            "",
            "입력에 없는 사실을 만들지 말고, 위 조건을 만족하는 실제 결과만 출력한다.",
        ]
    )
    return "\n".join(lines).strip()


REVIEW.baseline_prompt = applied_baseline_prompt

prepare_review = REVIEW.prepare_review
finalize_review = REVIEW.finalize_review
PromptPatchReviewError = REVIEW.PromptPatchReviewError


def main(argv: list[str] | None = None) -> int:
    return REVIEW.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
