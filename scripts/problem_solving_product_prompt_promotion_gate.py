#!/usr/bin/env python3
"""Validate multi-case product prompt review evidence before baseline approval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISIONS = ROOT / "reviews" / "product-evidence-hard-2026-08-01" / "decisions.json"
ALLOWED_DECISIONS = {"promote_patch", "keep_baseline", "no_winner"}


class ProductPromptPromotionError(ValueError):
    """Raised when the recorded product prompt review is inconsistent."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductPromptPromotionError(f"검증 기록을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductPromptPromotionError("검증 기록은 JSON 객체여야 합니다.")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ProductPromptPromotionError(f"{label}은 비어 있지 않은 문자열 배열이어야 합니다.")
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ProductPromptPromotionError(f"{label}에 중복 값이 있습니다.")
    return normalized


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("version") != 1:
        raise ProductPromptPromotionError("지원하지 않는 검증 기록 버전입니다.")
    policy = payload.get("promotion_policy")
    if not isinstance(policy, dict):
        raise ProductPromptPromotionError("promotion_policy가 없습니다.")
    required_ids = _string_list(policy.get("required_case_ids"), "required_case_ids")
    minimum_wins = policy.get("minimum_patch_wins")
    maximum_failures = policy.get("maximum_patch_critical_failures")
    if not isinstance(minimum_wins, int) or minimum_wins < 1:
        raise ProductPromptPromotionError("minimum_patch_wins가 올바르지 않습니다.")
    if not isinstance(maximum_failures, int) or maximum_failures < 0:
        raise ProductPromptPromotionError("maximum_patch_critical_failures가 올바르지 않습니다.")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ProductPromptPromotionError("results가 배열이 아닙니다.")
    seen: set[str] = set()
    patch_wins = 0
    baseline_wins = 0
    ties = 0
    patch_critical_failures: list[str] = []

    for result in results:
        if not isinstance(result, dict):
            raise ProductPromptPromotionError("case 결과가 객체가 아닙니다.")
        case_id = result.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ProductPromptPromotionError("case_id가 비었거나 중복입니다.")
        seen.add(case_id)
        decision = result.get("decision")
        if decision not in ALLOWED_DECISIONS:
            raise ProductPromptPromotionError(f"{case_id}: 알 수 없는 decision입니다.")
        mapping = result.get("mapping")
        scores = result.get("scores")
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"A", "B"}
            or set(mapping.values()) != {"applied_baseline", "patched"}
            or not isinstance(scores, dict)
            or set(scores) != {"A", "B"}
        ):
            raise ProductPromptPromotionError(f"{case_id}: mapping 또는 scores가 올바르지 않습니다.")
        patched_id = next(key for key, value in mapping.items() if value == "patched")
        patched_score = scores.get(patched_id)
        if not isinstance(patched_score, dict):
            raise ProductPromptPromotionError(f"{case_id}: patched score가 없습니다.")
        failures = patched_score.get("critical_failures")
        if not isinstance(failures, list) or any(
            not isinstance(item, str) or not item.strip() for item in failures
        ):
            raise ProductPromptPromotionError(f"{case_id}: critical_failures가 올바르지 않습니다.")
        patch_critical_failures.extend(f"{case_id}: {item.strip()}" for item in failures)

        if decision == "promote_patch":
            patch_wins += 1
        elif decision == "keep_baseline":
            baseline_wins += 1
        else:
            ties += 1

    if seen != set(required_ids):
        missing = sorted(set(required_ids) - seen)
        extra = sorted(seen - set(required_ids))
        raise ProductPromptPromotionError(
            f"필수 사례 구성이 다릅니다. missing={missing}, extra={extra}"
        )

    approved = (
        patch_wins >= minimum_wins
        and len(patch_critical_failures) <= maximum_failures
    )
    decision = "approve_product_baseline" if approved else "retain_current_baseline"
    return {
        "approved": approved,
        "decision": decision,
        "patch_wins": patch_wins,
        "baseline_wins": baseline_wins,
        "ties": ties,
        "patch_critical_failure_count": len(patch_critical_failures),
        "patch_critical_failures": patch_critical_failures,
        "minimum_patch_wins": minimum_wins,
        "maximum_patch_critical_failures": maximum_failures,
    }


def evaluate_file(path: Path = DEFAULT_DECISIONS) -> dict[str, Any]:
    payload = _read_json(path)
    result = evaluate_payload(payload)
    expected = payload.get("recorded_gate_decision")
    if expected is not None and expected != result["decision"]:
        raise ProductPromptPromotionError(
            f"기록된 gate 결정({expected})과 계산 결과({result['decision']})가 다릅니다."
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    args = parser.parse_args(argv)
    try:
        result = evaluate_file(args.decisions)
    except ProductPromptPromotionError as exc:
        print(f"error: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
