#!/usr/bin/env python3
"""Candidate state and deterministic correction planning for the PSOS next-loop."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping, Sequence


SOURCE_FAMILIES = {"COMMUNITY", "MARKETPLACE", "PRIMARY", "REUSE_INDEX", "BROAD_WEB"}
CORRECTION_TYPES = {
    "exclude_candidate",
    "constraint_change",
    "scope_expand",
    "scope_reduce",
    "preference_update",
    "request_more",
    "request_verification",
    "accept_candidates",
}
ACTION_BY_TYPE = {
    "exclude_candidate": "RERANK",
    "constraint_change": "FILTER",
    "scope_expand": "PARTIAL_RESEARCH",
    "scope_reduce": "FILTER",
    "preference_update": "RERANK",
    "request_more": "PARTIAL_RESEARCH",
    "request_verification": "VERIFY_CANDIDATE",
    "accept_candidates": "VERIFY_COMPLETION",
}
WORKING_STATES = {
    "collecting",
    "awaiting_correction",
    "researching",
    "ready_for_verification",
    "completed",
    "partial",
}


class CandidateWorkingSetError(ValueError):
    """Raised when candidate state or a correction violates its contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateWorkingSetError(f"{label}이 비어 있습니다.")
    return value.strip()


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise CandidateWorkingSetError(f"{label}은 배열이어야 합니다.")
    result: list[str] = []
    for item in value:
        text = _text(item, label)
        if text not in result:
            result.append(text)
    return result


def _identifier(value: Any, label: str) -> str:
    text = _text(value, label)
    if re.fullmatch(r"[A-Za-z0-9._-]+", text) is None:
        raise CandidateWorkingSetError(f"{label} 형식이 올바르지 않습니다.")
    return text


def validate_candidate(candidate: Any) -> dict[str, Any]:
    required = {
        "id",
        "name",
        "source_family",
        "source_url",
        "why_actionable",
        "attributes",
        "evidence",
        "strengths",
        "risks",
        "status",
        "verification_status",
        "exclusion_reason",
    }
    if not isinstance(candidate, dict) or set(candidate) != required:
        raise CandidateWorkingSetError("candidate 필드가 올바르지 않습니다.")
    result = copy.deepcopy(candidate)
    result["id"] = _identifier(candidate["id"], "candidate.id")
    result["name"] = _text(candidate["name"], "candidate.name")
    if candidate["source_family"] not in SOURCE_FAMILIES:
        raise CandidateWorkingSetError("candidate.source_family가 올바르지 않습니다.")
    result["source_url"] = _text(candidate["source_url"], "candidate.source_url")
    result["why_actionable"] = _text(candidate["why_actionable"], "candidate.why_actionable")
    if not isinstance(candidate["attributes"], dict):
        raise CandidateWorkingSetError("candidate.attributes는 객체여야 합니다.")
    if not isinstance(candidate["evidence"], list):
        raise CandidateWorkingSetError("candidate.evidence는 배열이어야 합니다.")
    result["strengths"] = _strings(candidate["strengths"], "candidate.strengths")
    result["risks"] = _strings(candidate["risks"], "candidate.risks")
    if candidate["status"] not in {"kept", "excluded", "needs_check"}:
        raise CandidateWorkingSetError("candidate.status가 올바르지 않습니다.")
    if candidate["verification_status"] not in {
        "unverified",
        "partially_verified",
        "verified",
        "blocked",
    }:
        raise CandidateWorkingSetError("candidate.verification_status가 올바르지 않습니다.")
    reason = candidate["exclusion_reason"]
    if candidate["status"] == "excluded":
        result["exclusion_reason"] = _text(reason, "candidate.exclusion_reason")
    elif reason is not None:
        raise CandidateWorkingSetError("제외되지 않은 후보에는 exclusion_reason을 둘 수 없습니다.")
    return result


def validate_correction(correction: Any) -> dict[str, Any]:
    required = {
        "id",
        "text",
        "type",
        "target_candidate_ids",
        "constraint_updates",
        "scope_terms",
        "verification_fields",
        "planned_action",
    }
    if not isinstance(correction, dict) or set(correction) != required:
        raise CandidateWorkingSetError("correction 필드가 올바르지 않습니다.")
    result = copy.deepcopy(correction)
    result["id"] = _identifier(correction["id"], "correction.id")
    result["text"] = _text(correction["text"], "correction.text")
    correction_type = correction["type"]
    if correction_type not in CORRECTION_TYPES:
        raise CandidateWorkingSetError("correction.type이 올바르지 않습니다.")
    result["target_candidate_ids"] = _strings(
        correction["target_candidate_ids"], "correction.target_candidate_ids"
    )
    if not isinstance(correction["constraint_updates"], dict):
        raise CandidateWorkingSetError("correction.constraint_updates는 객체여야 합니다.")
    result["scope_terms"] = _strings(correction["scope_terms"], "correction.scope_terms")
    result["verification_fields"] = _strings(
        correction["verification_fields"], "correction.verification_fields"
    )
    if correction["planned_action"] != ACTION_BY_TYPE[correction_type]:
        raise CandidateWorkingSetError("correction.planned_action이 type과 맞지 않습니다.")
    if correction_type in {"exclude_candidate", "request_verification"} and not result["target_candidate_ids"]:
        raise CandidateWorkingSetError("대상 후보가 필요한 correction입니다.")
    if correction_type == "constraint_change" and not correction["constraint_updates"]:
        raise CandidateWorkingSetError("constraint_change에는 변경 조건이 필요합니다.")
    if correction_type in {"scope_expand", "scope_reduce", "request_more"} and not result["scope_terms"]:
        raise CandidateWorkingSetError("범위 관련 correction에는 scope_terms가 필요합니다.")
    return result


def validate_working_set(value: Any) -> dict[str, Any]:
    required = {
        "version",
        "run_id",
        "request",
        "goal",
        "constraints",
        "source_plan",
        "candidates",
        "user_corrections",
        "unresolved_requirements",
        "state",
        "next_action",
        "revision",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise CandidateWorkingSetError("candidate_working_set 필드가 올바르지 않습니다.")
    result = copy.deepcopy(value)
    if value["version"] != 1:
        raise CandidateWorkingSetError("candidate_working_set.version은 1이어야 합니다.")
    result["run_id"] = _identifier(value["run_id"], "candidate_working_set.run_id")
    result["request"] = _text(value["request"], "candidate_working_set.request")
    result["goal"] = _text(value["goal"], "candidate_working_set.goal")
    if not isinstance(value["constraints"], dict) or not isinstance(value["source_plan"], dict):
        raise CandidateWorkingSetError("constraints와 source_plan은 객체여야 합니다.")
    if value["state"] not in WORKING_STATES:
        raise CandidateWorkingSetError("candidate_working_set.state가 올바르지 않습니다.")
    if value["next_action"] is not None and value["next_action"] not in set(ACTION_BY_TYPE.values()):
        raise CandidateWorkingSetError("candidate_working_set.next_action이 올바르지 않습니다.")
    if not isinstance(value["revision"], int) or value["revision"] < 0:
        raise CandidateWorkingSetError("candidate_working_set.revision이 올바르지 않습니다.")
    result["candidates"] = [validate_candidate(item) for item in value["candidates"]]
    ids = [item["id"] for item in result["candidates"]]
    if len(ids) != len(set(ids)):
        raise CandidateWorkingSetError("candidate id가 중복되었습니다.")
    result["user_corrections"] = [validate_correction(item) for item in value["user_corrections"]]
    result["unresolved_requirements"] = _strings(
        value["unresolved_requirements"], "unresolved_requirements"
    )
    return result


def source_scout_to_source_plan(state: Mapping[str, Any]) -> dict[str, Any]:
    scout = state["source_scout"]
    decision = state["decision"]
    scores = decision.get("scores", {})
    return {
        "strategy": decision["strategy"],
        "primary_source_family": decision["primary_source_family"],
        "secondary_source_family": decision["secondary_source_family"],
        "next_action": decision["next_action"],
        "probes": [
            {
                "family": probe["family"],
                "score": int(scores.get(probe["family"], 0)),
                "signal_summary": probe["signal_summary"],
                "verification_need": probe["verification_need"],
            }
            for probe in scout["probes"]
        ],
    }


def source_scout_to_candidates(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for probe in state["source_scout"]["probes"]:
        for lead in probe["concrete_leads"]:
            url = lead["url"].strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "id": f"candidate-{len(candidates) + 1:03d}",
                    "name": lead["name"].strip(),
                    "source_family": probe["family"],
                    "source_url": url,
                    "why_actionable": lead["why_actionable"].strip(),
                    "attributes": {},
                    "evidence": [
                        {
                            "source": url,
                            "finding": lead["why_actionable"].strip(),
                            "kind": "source-scout-lead",
                        }
                    ],
                    "strengths": [],
                    "risks": ["정찰 단계 단서이므로 세부 속성과 현재 상태를 아직 검증하지 않음"],
                    "status": "needs_check",
                    "verification_status": "unverified",
                    "exclusion_reason": None,
                }
            )
    return candidates


def source_scout_to_dynamic_scan(state: Mapping[str, Any]) -> dict[str, Any]:
    scout = state["source_scout"]
    decision = state["decision"]
    vocabulary: list[str] = []
    adjacent: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []
    for probe in scout["probes"]:
        for query in probe["queries"]:
            if query not in vocabulary:
                vocabulary.append(query)
        for lead in probe["concrete_leads"]:
            adjacent.append(
                {
                    "name": lead["name"],
                    "relation": lead["why_actionable"],
                    "source": lead["url"],
                }
            )
        observations.append(
            {
                "finding": probe["signal_summary"],
                "source": probe["family"],
                "decision_relevance": f"{probe['family']} 정보원의 조사 우선순위를 정함",
                "evidence_strength": probe["actionability"],
            }
        )
    return {
        "terrain_summary": decision["selection_reason"],
        "vocabulary": vocabulary[:12],
        "adjacent_possibilities": adjacent[:6],
        "observations": observations[:8],
        "source_gaps": list(scout["scouting_limitations"])[:5],
    }


def new_working_set(
    *,
    run_id: str,
    request: str,
    goal: str,
    source_scout_state: Mapping[str, Any],
    constraints: Mapping[str, Any] | None = None,
    unresolved_requirements: Sequence[str] = (),
) -> dict[str, Any]:
    candidates = source_scout_to_candidates(source_scout_state)
    return validate_working_set(
        {
            "version": 1,
            "run_id": run_id,
            "request": request,
            "goal": goal,
            "constraints": copy.deepcopy(dict(constraints or {})),
            "source_plan": source_scout_to_source_plan(source_scout_state),
            "candidates": candidates,
            "user_corrections": [],
            "unresolved_requirements": list(unresolved_requirements),
            "state": "awaiting_correction" if candidates else "collecting",
            "next_action": None,
            "revision": 0,
        }
    )


def plan_correction(
    *,
    correction_id: str,
    text: str,
    correction_type: str,
    target_candidate_ids: Sequence[str] = (),
    constraint_updates: Mapping[str, Any] | None = None,
    scope_terms: Sequence[str] = (),
    verification_fields: Sequence[str] = (),
) -> dict[str, Any]:
    if correction_type not in ACTION_BY_TYPE:
        raise CandidateWorkingSetError("지원하지 않는 correction_type입니다.")
    return validate_correction(
        {
            "id": correction_id,
            "text": text,
            "type": correction_type,
            "target_candidate_ids": list(target_candidate_ids),
            "constraint_updates": copy.deepcopy(dict(constraint_updates or {})),
            "scope_terms": list(scope_terms),
            "verification_fields": list(verification_fields),
            "planned_action": ACTION_BY_TYPE[correction_type],
        }
    )


def apply_correction(working_set: Mapping[str, Any], correction: Mapping[str, Any]) -> dict[str, Any]:
    current = validate_working_set(dict(working_set))
    planned = validate_correction(dict(correction))
    known = {candidate["id"] for candidate in current["candidates"]}
    if set(planned["target_candidate_ids"]) - known:
        raise CandidateWorkingSetError("존재하지 않는 후보를 교정 대상으로 지정했습니다.")
    if any(item["id"] == planned["id"] for item in current["user_corrections"]):
        raise CandidateWorkingSetError("correction id가 중복되었습니다.")
    if planned["type"] == "exclude_candidate":
        targets = set(planned["target_candidate_ids"])
        for candidate in current["candidates"]:
            if candidate["id"] in targets:
                candidate["status"] = "excluded"
                candidate["exclusion_reason"] = planned["text"]
    if planned["type"] == "constraint_change":
        current["constraints"].update(planned["constraint_updates"])
    if planned["type"] in {"scope_expand", "scope_reduce", "request_more"}:
        key = "excluded_scope" if planned["type"] == "scope_reduce" else "included_scope"
        existing = current["constraints"].get(key, [])
        if not isinstance(existing, list):
            existing = []
        current["constraints"][key] = list(dict.fromkeys([*existing, *planned["scope_terms"]]))
    current["user_corrections"].append(planned)
    current["revision"] += 1
    current["next_action"] = planned["planned_action"]
    if planned["planned_action"] == "PARTIAL_RESEARCH":
        current["state"] = "researching"
    elif planned["planned_action"] in {"VERIFY_CANDIDATE", "VERIFY_COMPLETION"}:
        current["state"] = "ready_for_verification"
    else:
        current["state"] = "awaiting_correction"
    return validate_working_set(current)


def kept_candidates(working_set: Mapping[str, Any]) -> list[dict[str, Any]]:
    current = validate_working_set(dict(working_set))
    return [item for item in current["candidates"] if item["status"] != "excluded"]


def _matches(actual: Any, rule: Any) -> bool | None:
    if not isinstance(rule, Mapping):
        return actual == rule
    if set(rule) != {"op", "value"}:
        return None
    op, expected = rule["op"], rule["value"]
    try:
        return {
            "eq": actual == expected,
            "neq": actual != expected,
            "lte": actual <= expected,
            "lt": actual < expected,
            "gte": actual >= expected,
            "gt": actual > expected,
            "in": actual in expected,
            "contains": expected in actual,
        }.get(op)
    except (TypeError, ValueError):
        return None


def apply_known_constraint_filter(
    working_set: Mapping[str, Any],
    constraint_updates: Mapping[str, Any],
    *,
    reason: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    if not constraint_updates:
        raise CandidateWorkingSetError("적용할 constraint_updates가 없습니다.")
    current = validate_working_set(dict(working_set))
    stats = {"evaluated": 0, "excluded": 0, "kept": 0, "unknown": 0}
    for candidate in current["candidates"]:
        if candidate["status"] == "excluded":
            continue
        outcomes: list[bool] = []
        for key, rule in constraint_updates.items():
            if key not in candidate["attributes"]:
                outcomes = []
                break
            outcome = _matches(candidate["attributes"][key], rule)
            if outcome is None:
                outcomes = []
                break
            outcomes.append(outcome)
        if not outcomes:
            candidate["status"] = "needs_check"
            candidate["exclusion_reason"] = None
            stats["unknown"] += 1
        elif all(outcomes):
            candidate["status"] = "kept"
            candidate["exclusion_reason"] = None
            stats["evaluated"] += 1
            stats["kept"] += 1
        else:
            candidate["status"] = "excluded"
            candidate["exclusion_reason"] = reason
            stats["evaluated"] += 1
            stats["excluded"] += 1
    return validate_working_set(current), stats


def _scalar(value: str) -> Any:
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in {"true", "yes", "예", "포함"}:
        return True
    if lowered in {"false", "no", "아니오", "제외"}:
        return False
    compact = cleaned.replace(",", "")
    if re.fullmatch(r"-?\d+", compact):
        return int(compact)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", compact):
        return float(compact)
    return cleaned


def correction_from_model_output(
    payload: Any,
    *,
    working_set: Mapping[str, Any],
    correction_id: str,
    original_text: str,
) -> dict[str, Any]:
    current = validate_working_set(dict(working_set))
    if not isinstance(payload, dict) or set(payload) != {"candidate_correction"}:
        raise CandidateWorkingSetError("candidate_correction 최상위 형식이 올바르지 않습니다.")
    value = payload["candidate_correction"]
    required = {
        "correction_type",
        "target_candidate_ids",
        "constraint_updates",
        "scope_terms",
        "verification_fields",
        "interpretation",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise CandidateWorkingSetError("candidate_correction 필드가 올바르지 않습니다.")
    correction_type = value["correction_type"]
    target_ids = _strings(value["target_candidate_ids"], "target_candidate_ids")
    known = {candidate["id"] for candidate in current["candidates"]}
    if set(target_ids) - known:
        raise CandidateWorkingSetError("candidate_correction이 존재하지 않는 후보를 가리킵니다.")
    if not isinstance(value["constraint_updates"], list):
        raise CandidateWorkingSetError("constraint_updates는 배열이어야 합니다.")
    updates: dict[str, Any] = {}
    for item in value["constraint_updates"]:
        if not isinstance(item, dict) or set(item) != {"key", "operator", "value"}:
            raise CandidateWorkingSetError("constraint_updates 항목 형식이 올바르지 않습니다.")
        key = _text(item["key"], "constraint_update.key")
        operator = item["operator"]
        if operator not in {"eq", "neq", "lte", "lt", "gte", "gt", "in", "contains"}:
            raise CandidateWorkingSetError("constraint_update.operator가 올바르지 않습니다.")
        raw_value = _text(item["value"], "constraint_update.value")
        parsed = [_scalar(part) for part in raw_value.split(",") if part.strip()] if operator == "in" else _scalar(raw_value)
        updates[key] = parsed if operator == "eq" else {"op": operator, "value": parsed}
    interpretation = _text(value["interpretation"], "candidate_correction.interpretation")
    text = _text(original_text, "original_text")
    if interpretation not in text:
        text = f"{text} — {interpretation}"
    return plan_correction(
        correction_id=correction_id,
        text=text,
        correction_type=correction_type,
        target_candidate_ids=target_ids,
        constraint_updates=updates,
        scope_terms=_strings(value["scope_terms"], "scope_terms"),
        verification_fields=_strings(value["verification_fields"], "verification_fields"),
    )
