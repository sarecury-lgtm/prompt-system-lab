#!/usr/bin/env python3
"""Domain-neutral purpose-specific winner profiles for multi-objective selections."""

from __future__ import annotations

import re
from typing import Any, Mapping


PROFILE_VERIFIER_ID = "selection_profile"
MAX_PROFILES = 3


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _profile_id(label: str, index: int) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", label.strip().lower()).strip("-")
    return slug or f"profile-{index}"


def _extract_profiles(text: str, source: str) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    patterns = [
        re.compile(
            r"(?P<label>[가-힣A-Za-z][가-힣A-Za-z0-9_-]{0,20})\s*(?:픽|pick)\s*(?P<count>\d{1,2})",
            re.I,
        ),
        re.compile(
            r"(?P<label>[가-힣A-Za-z][가-힣A-Za-z0-9_-]{0,20})\s*(?:선택|추천)\s*(?P<count>\d{1,2})",
            re.I,
        ),
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            label = _text(match.group("label"))
            count = max(1, min(5, int(match.group("count"))))
            normalized = label.lower()
            if not label or normalized in seen:
                continue
            seen.add(normalized)
            profiles.append(
                {
                    "id": _profile_id(label, len(profiles) + 1),
                    "label": label,
                    "count": count,
                    "source": source,
                }
            )
            if len(profiles) >= MAX_PROFILES:
                return profiles
    return profiles


def build_selection_policy(request: str, context: str = "") -> dict[str, Any]:
    """Extract explicit purpose-specific winner slots without inventing domain roles."""

    request_profiles = _extract_profiles(_text(request), "request")
    context_profiles = _extract_profiles(_text(context), "context")
    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*request_profiles, *context_profiles]:
        normalized = _text(item.get("label")).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            profiles.append(item)
        if len(profiles) >= MAX_PROFILES:
            break

    if len(profiles) < 2:
        return {
            "mode": "single_winner",
            "profiles": [],
            "allow_profile_overlap": True,
            "force_profile_slots": False,
            "source": "none",
        }
    source = "request" if any(item["source"] == "request" for item in profiles) else "context"
    return {
        "mode": "multi_profile",
        "profiles": profiles,
        "allow_profile_overlap": True,
        "force_profile_slots": True,
        "source": source,
    }


def requested_slot_count(policy: Mapping[str, Any]) -> int | None:
    if _text(policy.get("mode")) != "multi_profile":
        return None
    total = 0
    for item in _list(policy.get("profiles")):
        if isinstance(item, Mapping):
            total += max(1, int(item.get("count") or 1))
    return total or None


def build_obligations(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    policy = _mapping(contract.get("selection_policy"))
    if _text(policy.get("mode")) != "multi_profile":
        return []
    return [
        {
            "version": 1,
            "id": "profiled_selection",
            "category": "decision_structure",
            "required": True,
            "verifier": PROFILE_VERIFIER_ID,
            "description": "Distinct user-requested decision purposes are preserved as separate winner slots instead of being collapsed into one aggregate score.",
        }
    ]


def prepare_coverage_template(contract: Mapping[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    policy = _mapping(contract.get("selection_policy"))
    if _text(policy.get("mode")) != "multi_profile":
        return coverage
    selection = _mapping(coverage.get("selection"))
    selection["profile_winners"] = [
        {
            "profile_id": _text(item.get("id")),
            "label": _text(item.get("label")),
            "selected_ids": [],
            "action": "",
            "reason": "",
        }
        for item in _list(policy.get("profiles"))
        if isinstance(item, Mapping)
    ]
    coverage["selection"] = selection
    return coverage


def execution_guidance(contract: Mapping[str, Any]) -> str:
    policy = _mapping(contract.get("selection_policy"))
    if _text(policy.get("mode")) != "multi_profile":
        return (
            "selection_policy가 single_winner이면 목적별 슬롯을 억지로 만들지 않는다. "
            "사용자가 실제로 요구한 하나의 결론 구조를 유지한다."
        )
    profiles = [
        f"{_text(item.get('label'))} {_text(item.get('count') or 1)}개"
        for item in _list(policy.get("profiles"))
        if isinstance(item, Mapping)
    ]
    return (
        "selection_policy가 multi_profile이다. 하나의 종합점수로 합치지 말고 "
        f"각 목적({', '.join(profiles)})의 우승자를 독립적으로 고른다. "
        "coverage.selection.profile_winners에 각 profile_id, label, selected_ids, action, reason을 채우고, "
        "coverage.selection.selected_ids에는 모든 슬롯의 선택을 같은 순서로 합쳐 기록한다. "
        "같은 후보가 여러 목적을 실제로 이길 때는 중복 선택할 수 있지만 이유를 목적별로 따로 쓴다."
    )


def verify_result(contract: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    policy = _mapping(contract.get("selection_policy"))
    if _text(policy.get("mode")) != "multi_profile":
        return {
            "satisfied": True,
            "missing_conditions": [],
            "warnings": [],
            "checks": [],
            "next_objective": "",
        }

    coverage = _mapping(result.get("coverage"))
    selection = _mapping(coverage.get("selection"))
    rows = [item for item in _list(selection.get("profile_winners")) if isinstance(item, Mapping)]
    by_id = {_text(item.get("profile_id")): dict(item) for item in rows if _text(item.get("profile_id"))}
    missing: list[str] = []
    observed: list[dict[str, Any]] = []

    for profile in _list(policy.get("profiles")):
        if not isinstance(profile, Mapping):
            continue
        profile_id = _text(profile.get("id"))
        label = _text(profile.get("label"))
        count = max(1, int(profile.get("count") or 1))
        row = by_id.get(profile_id, {})
        selected_ids = [_text(item) for item in _list(row.get("selected_ids")) if _text(item)]
        ok = bool(
            _text(row.get("label")) == label
            and len(selected_ids) == count
            and _text(row.get("action"))
            and _text(row.get("reason"))
        )
        observed.append(
            {
                "profile_id": profile_id,
                "label": label,
                "requested_count": count,
                "selected_ids": selected_ids,
                "satisfied": ok,
            }
        )
        if not ok:
            missing.append(
                f"목적별 선택 '{label}'에서 요청한 {count}개 우승자와 별도 행동·선정 이유가 확인되지 않습니다."
            )

    return {
        "satisfied": not missing,
        "missing_conditions": missing,
        "warnings": [],
        "checks": [
            {
                "id": "profiled_selection",
                "satisfied": not missing,
                "observed": observed,
            }
        ],
        "next_objective": (
            "Preserve the requested decision profiles and fill each purpose-specific winner slot independently instead of collapsing them into one total score."
            if missing
            else ""
        ),
    }
