#!/usr/bin/env python3
"""Verify Action Results against generated obligations instead of model completion claims."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping


class EvidenceVerifierError(ValueError):
    """Raised when evidence records are malformed beyond safe normalization."""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in output:
            output.append(text)
    return output


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value).lower()).strip()


def empty_coverage() -> dict[str, Any]:
    return {
        "search_scope": {
            "description": "",
            "universe": "",
            "screened_count": 0,
            "filters": [],
            "finalist_ids": [],
            "evidence_refs": [],
        },
        "current_state": {
            "checked_at": "",
            "items": [],
        },
        "comparison": {
            "criteria": [],
            "candidate_ids": [],
            "records": [],
        },
        "selection": {
            "selected_ids": [],
            "selected_id": "",
            "action": "",
            "reason": "",
        },
        "action_fit": {
            "selected_id": "",
            "requested_action": "",
            "time_basis": "",
            "upside_reference": "",
            "downside_reference": "",
            "invalidation": "",
            "evidence_refs": [],
        },
        "assumptions": [],
        "obligation_evidence": [],
        "domain": {},
    }


def normalize_coverage(value: Any) -> dict[str, Any]:
    source = _mapping(value)
    template = empty_coverage()
    output: dict[str, Any] = {}
    for key, default in template.items():
        if isinstance(default, dict):
            output[key] = {**default, **_mapping(source.get(key))}
        elif isinstance(default, list):
            output[key] = _list(source.get(key))
        else:
            output[key] = source.get(key, default)
    output["assumptions"] = [
        dict(item) for item in _list(output["assumptions"]) if isinstance(item, Mapping)
    ]
    output["obligation_evidence"] = [
        dict(item)
        for item in _list(output["obligation_evidence"])
        if isinstance(item, Mapping)
    ]
    output["domain"] = _mapping(output["domain"])
    return output


def _evidence_ids(result: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in _list(result.get("evidence")):
        if not isinstance(item, Mapping):
            continue
        for key in ("id", "source", "url"):
            text = _text(item.get(key))
            if text:
                ids.add(text)
    return ids


def _refs_resolve(refs: Any, known: set[str]) -> bool:
    values = [_text(item) for item in _list(refs) if _text(item)]
    return bool(values) and all(value in known for value in values)


def _check_goal_fidelity(
    contract: Mapping[str, Any],
    answer: str,
    coverage: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    selection = _mapping(coverage.get("selection"))
    deliverable = contract.get("deliverable")
    selected_ids = [
        _text(item) for item in _list(selection.get("selected_ids")) if _text(item)
    ]
    selected_id = _text(selection.get("selected_id"))
    if selected_id and selected_id not in selected_ids:
        selected_ids.append(selected_id)
    if deliverable in {"selection", "action_decision"}:
        ok = bool(answer.strip() and selected_ids and _text(selection.get("action")))
    else:
        ok = bool(answer.strip())
    return ok, {
        "deliverable": deliverable,
        "answer_present": bool(answer.strip()),
        "selected_ids": selected_ids,
        "action": _text(selection.get("action")),
    }


def _contract_source_texts(contract: Mapping[str, Any]) -> dict[str, list[str]]:
    output = {"request": [], "context": []}
    request = _normalized_text(contract.get("original_request"))
    if request:
        output["request"].append(request)
    for item in _list(contract.get("user_constraints")):
        if not isinstance(item, Mapping):
            continue
        source = _text(item.get("source"))
        text = _normalized_text(item.get("text"))
        if source in output and text:
            output[source].append(text)
    return output


def _check_assumptions(
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []
    sources = _contract_source_texts(contract)
    for item in _list(coverage.get("assumptions")):
        if not isinstance(item, Mapping):
            continue
        record = dict(item)
        observed.append(record)
        if not bool(record.get("material")):
            continue
        basis = _text(record.get("basis"))
        sensitivity = _text(record.get("sensitivity"))
        excerpt = _normalized_text(record.get("source_excerpt"))
        if basis in {"user", "context"}:
            source_key = "request" if basis == "user" else "context"
            source_match = bool(
                excerpt
                and any(excerpt in source_text for source_text in sources[source_key])
            )
            if not source_match:
                bad.append(record)
        elif basis == "explicit_default":
            if not sensitivity:
                bad.append(record)
        else:
            bad.append(record)
    return not bad, {
        "observed": observed,
        "unsupported_material": bad,
        "available_sources": sources,
    }


def _check_current_state(
    coverage: Mapping[str, Any],
    known_evidence: set[str],
) -> tuple[bool, dict[str, Any]]:
    record = _mapping(coverage.get("current_state"))
    items = [item for item in _list(record.get("items")) if isinstance(item, Mapping)]
    item_refs_ok = bool(items) and all(
        _refs_resolve(item.get("evidence_refs"), known_evidence) for item in items
    )
    ok = bool(_text(record.get("checked_at")) and items and item_refs_ok)
    return ok, {
        "checked_at": _text(record.get("checked_at")),
        "item_count": len(items),
        "evidence_refs_resolve": item_refs_ok,
    }


def _check_search_scope(
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
    known_evidence: set[str],
) -> tuple[bool, dict[str, Any]]:
    record = _mapping(coverage.get("search_scope"))
    finalists = [_text(item) for item in _list(record.get("finalist_ids")) if _text(item)]
    filters = [_text(item) for item in _list(record.get("filters")) if _text(item)]
    count = record.get("screened_count")
    refs_ok = _refs_resolve(record.get("evidence_refs"), known_evidence)
    minimum_finalists = max(1, int(contract.get("selection_count") or 1))
    ok = bool(
        _text(record.get("description"))
        and _text(record.get("universe"))
        and isinstance(count, int)
        and count >= len(finalists) >= minimum_finalists
        and filters
        and refs_ok
    )
    return ok, {
        "description": _text(record.get("description")),
        "universe": _text(record.get("universe")),
        "screened_count": count,
        "finalist_ids": finalists,
        "filters": filters,
        "evidence_refs": _list(record.get("evidence_refs")),
        "evidence_refs_resolve": refs_ok,
    }


def _check_comparison(
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    record = _mapping(coverage.get("comparison"))
    candidate_ids = [_text(item) for item in _list(record.get("candidate_ids")) if _text(item)]
    criteria = [_text(item) for item in _list(record.get("criteria")) if _text(item)]
    rows = [item for item in _list(record.get("records")) if isinstance(item, Mapping)]
    row_ids = {_text(item.get("candidate_id")) for item in rows if _text(item.get("candidate_id"))}
    minimum = max(2, int(contract.get("selection_count") or 1))
    ok = bool(
        len(candidate_ids) >= minimum
        and criteria
        and all(candidate_id in row_ids for candidate_id in candidate_ids)
    )
    return ok, {
        "candidate_ids": candidate_ids,
        "criteria": criteria,
        "record_candidate_ids": sorted(row_ids),
    }


def _check_selection(
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    record = _mapping(coverage.get("selection"))
    selected_ids = [_text(item) for item in _list(record.get("selected_ids")) if _text(item)]
    selected_id = _text(record.get("selected_id"))
    if selected_id and selected_id not in selected_ids:
        selected_ids.append(selected_id)
    requested_count = int(contract.get("selection_count") or 1)
    ok = bool(
        len(selected_ids) == requested_count
        and _text(record.get("action"))
        and _text(record.get("reason"))
    )
    return ok, {
        "requested_count": requested_count,
        "selected_ids": selected_ids,
        "action": _text(record.get("action")),
        "reason": _text(record.get("reason")),
    }


def _check_generic_action_fit(
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
    known_evidence: set[str],
) -> tuple[bool, dict[str, Any]]:
    record = _mapping(coverage.get("action_fit"))
    requested_action = _text(record.get("requested_action"))
    contract_action = _text(contract.get("requested_action"))
    required = {
        "selected_id": _text(record.get("selected_id")),
        "requested_action": requested_action,
        "time_basis": _text(record.get("time_basis")),
        "upside_reference": _text(record.get("upside_reference")),
        "downside_reference": _text(record.get("downside_reference")),
        "invalidation": _text(record.get("invalidation")),
    }
    refs_ok = _refs_resolve(record.get("evidence_refs"), known_evidence)
    action_matches = bool(requested_action and requested_action == contract_action)
    return bool(all(required.values()) and refs_ok and action_matches), {
        "fields": required,
        "contract_requested_action": contract_action,
        "requested_action_matches": action_matches,
        "evidence_refs_resolve": refs_ok,
    }


def _missing_text(obligation_id: str) -> str:
    messages = {
        "goal_fidelity": "요청한 행동과 최종 산출물이 실제 답변에서 확인되지 않습니다.",
        "assumption_traceability": "결론을 바꾸는 물질적 가정이 사용자·문맥·명시적 기본값과 연결되지 않았습니다.",
        "current_state_record": "현재 상태의 확인 시점과 근거 연결 기록이 부족합니다.",
        "candidate_search_scope": "후보군의 범위, 필터, 선별 수, 최종 후보와 근거 참조 기록이 부족합니다.",
        "comparable_evaluation": "공통 기준으로 복수 후보를 비교한 구조화 기록이 부족합니다.",
        "final_selection": "요청한 수의 최종 선택과 구체적 행동·선정 이유가 확인되지 않습니다.",
        "current_action_fit": "선택 대상이 요청한 시점의 행동에 적합하다는 상방·하방·무효화 근거가 부족합니다.",
    }
    return messages.get(obligation_id, f"완료 의무를 확인할 증거가 없습니다: {obligation_id}")


def verify_result(
    contract: Mapping[str, Any],
    obligations: list[dict[str, Any]],
    answer: str,
    result: Mapping[str, Any],
    *,
    domain_adapter: Any | None = None,
) -> dict[str, Any]:
    coverage = normalize_coverage(result.get("coverage"))
    known_evidence = _evidence_ids(result)
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    warnings: list[str] = []

    generic_checkers = {
        "goal_fidelity": lambda: _check_goal_fidelity(contract, answer, coverage),
        "assumption_traceability": lambda: _check_assumptions(contract, coverage),
        "current_state_record": lambda: _check_current_state(coverage, known_evidence),
        "candidate_search_scope": lambda: _check_search_scope(contract, coverage, known_evidence),
        "comparable_evaluation": lambda: _check_comparison(contract, coverage),
        "final_selection": lambda: _check_selection(contract, coverage),
        "current_action_fit": lambda: _check_generic_action_fit(contract, coverage, known_evidence),
    }

    domain_obligation_ids = {
        str(item.get("id"))
        for item in obligations
        if item.get("required") and item.get("verifier") not in {"generic", "domain"}
    }
    for obligation in obligations:
        if not obligation.get("required") or obligation.get("verifier") not in {"generic", "domain"}:
            continue
        obligation_id = str(obligation.get("id") or "")
        if obligation.get("verifier") == "domain" and domain_adapter is not None:
            continue
        checker = generic_checkers.get(obligation_id)
        if checker is None:
            missing.append(_missing_text(obligation_id))
            checks.append({"id": obligation_id, "satisfied": False, "observed": None})
            continue
        satisfied, observed = checker()
        checks.append({"id": obligation_id, "satisfied": satisfied, "observed": observed})
        if not satisfied:
            missing.append(_missing_text(obligation_id))

    domain_verdict = {
        "missing_conditions": [],
        "warnings": [],
        "checks": [],
        "next_objective": "",
        "suggested_route": None,
        "changed_dimension": "none",
    }
    if domain_adapter is not None:
        domain_verdict = domain_adapter.verify(contract, answer, {**dict(result), "coverage": coverage})
        checks.extend(_list(domain_verdict.get("checks")))
        missing.extend(_text(item) for item in _list(domain_verdict.get("missing_conditions")))
        warnings.extend(_text(item) for item in _list(domain_verdict.get("warnings")))
        checked_ids = {
            _text(item.get("id"))
            for item in _list(domain_verdict.get("checks"))
            if isinstance(item, Mapping)
        }
        for obligation_id in sorted(domain_obligation_ids - checked_ids):
            missing.append(_missing_text(obligation_id))
            checks.append({"id": obligation_id, "satisfied": False, "observed": None})

    missing = _unique(missing)
    warnings = _unique(warnings)
    categories = {
        str(item.get("category") or "")
        for item in obligations
        if _text(item.get("id"))
        and any(check.get("id") == item.get("id") and not check.get("satisfied") for check in checks)
    }
    evidence_gap = bool(categories & {"time", "search", "comparison", "domain_search", "domain_decision"})
    next_objective = _text(domain_verdict.get("next_objective"))
    if not next_objective and missing:
        next_objective = (
            "Resolve the observable evidence obligations that failed Controller verification: "
            + "; ".join(missing[:3])
        )
    domain_dimension = _text(domain_verdict.get("changed_dimension"))
    changed_dimension = (
        domain_dimension
        if domain_dimension and domain_dimension != "none"
        else "information_source"
        if evidence_gap
        else "interaction"
    )
    return {
        "version": 1,
        "satisfied": not missing,
        "missing_conditions": missing,
        "warnings": warnings,
        "checks": checks,
        "coverage": coverage,
        "next_objective": next_objective,
        "suggested_route": domain_verdict.get("suggested_route") or ("RESEARCH" if evidence_gap else None),
        "changed_dimension": changed_dimension,
        "debug_summary": json.dumps(
            {
                "required_obligations": [item.get("id") for item in obligations if item.get("required")],
                "missing_count": len(missing),
            },
            ensure_ascii=False,
        ),
    }
