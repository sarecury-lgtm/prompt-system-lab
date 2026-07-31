#!/usr/bin/env python3
"""Run the goal-aware A/B experiment with harness-owned case metadata."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_goal_aware_behavior_ab as AB  # noqa: E402


_BASE_VALIDATE_ASSESSMENT = AB._validate_assessment


def _validate_assessment_with_harness_case_id(
    payload: Any,
    case_id: str,
) -> dict[str, Any]:
    """Treat case_id as runner metadata rather than a model judgment."""

    if isinstance(payload, dict):
        normalized = dict(payload)
        if normalized.get("version") == 1 and "case_id" in normalized:
            normalized["case_id"] = case_id
            return _BASE_VALIDATE_ASSESSMENT(normalized, case_id)
    return _BASE_VALIDATE_ASSESSMENT(payload, case_id)


AB._validate_assessment = _validate_assessment_with_harness_case_id


if __name__ == "__main__":
    raise SystemExit(AB.main())
