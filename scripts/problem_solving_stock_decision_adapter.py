#!/usr/bin/env python3
"""Optional stock-decision evidence adapter for the general PSOS verifier."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping


ADAPTER_ID = "stock-decision-v1"


def matches(request: str) -> bool:
    text = str(request or "")
    subject = re.search(r"주식|종목|티커|ticker|나스닥|코스피|코스닥|미국장|미국 주식", text, re.I)
    decision = re.search(r"추천|매수|사도|사면|살까|진입|1순위|골라|오늘|지금", text, re.I)
    return bool(subject and decision)


def augment_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(contract))
    output["domain_hint"] = ADAPTER_ID
    output["domain_requirements"] = {
        "candidate_universe_record": True,
        "selected_current_entry_fit": True,
        "material_horizon_basis": True,
    }
    return output


def additional_obligations(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    if contract.get("domain_hint") != ADAPTER_ID:
        return []
    return [
        {
            "version": 1,
            "id": "stock_candidate_universe",
            "category": "domain_search",
            "required": True,
            "verifier": ADAPTER_ID,
            "description": "The stock recommendation records the tradable universe, screening time, filters, screened count, finalists and screening evidence before naming a winner.",
        },
        {
            "version": 1,
            "id": "stock_selected_entry_fit",
            "category": "domain_decision",
            "required": True,
            "verifier": ADAPTER_ID,
            "description": "The selected ticker has current price, entry zone, invalidation, upside and downside references, risk/reward, chase risk and evidence links.",
        },
        {
            "version": 1,
            "id": "stock_material_horizon_basis",
            "category": "domain_assumptions",
            "required": True,
            "verifier": ADAPTER_ID,
            "description": "A material holding-period assumption is sourced from the user/context or explicitly labeled with sensitivity rather than silently inserted as a user constraint.",
        },
    ]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _evidence_ids(result: Mapping[str, Any]) -> set[str]:
    output: set[str] = set()
    for item in _list(result.get("evidence")):
        if not isinstance(item, Mapping):
            continue
        for key in ("id", "source", "url"):
            text = _text(item.get(key))
            if text:
                output.add(text)
    return output


def verify(
    contract: Mapping[str, Any],
    answer: str,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Return observable stock-specific missing conditions without choosing a ticker."""

    if contract.get("domain_hint") != ADAPTER_ID:
        return {
            "missing_conditions": [],
            "warnings": [],
            "checks": [],
            "next_objective": "",
            "suggested_route": None,
            "changed_dimension": "none",
        }

    missing: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    coverage = _mapping(result.get("coverage"))
    domain = _mapping(coverage.get("domain"))
    stock = _mapping(domain.get("stock_decision"))
    screening = _mapping(stock.get("screening_record"))
    entry = _mapping(stock.get("selected_entry_fit"))
    selection = _mapping(coverage.get("selection"))
    known_evidence = _evidence_ids(result)

    universe = _text(screening.get("universe"))
    as_of = _text(screening.get("as_of"))
    filters = [_text(item) for item in _list(screening.get("filters")) if _text(item)]
    finalists = [_text(item) for item in _list(screening.get("finalist_ids")) if _text(item)]
    screened_count = screening.get("screened_count")
    screening_refs = [
        _text(item) for item in _list(screening.get("evidence_refs")) if _text(item)
    ]
    screening_refs_resolve = bool(screening_refs) and all(
        ref in known_evidence for ref in screening_refs
    )
    universe_ok = bool(
        universe
        and as_of
        and filters
        and isinstance(screened_count, int)
        and screened_count > len(finalists) >= 1
        and screening_refs_resolve
    )
    checks.append(
        {
            "id": "stock_candidate_universe",
            "satisfied": universe_ok,
            "observed": {
                "universe": universe,
                "as_of": as_of,
                "screened_count": screened_count,
                "finalist_count": len(finalists),
                "filters": filters,
                "evidence_refs": screening_refs,
                "evidence_refs_resolve": screening_refs_resolve,
            },
        }
    )
    if not universe_ok:
        missing.append(
            "주식 후보군의 시장 범위, 확인 시점, 필터, 실제 선별 수, 최종 후보와 선별 근거 참조가 부족합니다."
        )

    selected_id = _text(selection.get("selected_id"))
    ticker = _text(entry.get("ticker"))
    current_price = entry.get("current_price")
    risk_reward = entry.get("risk_reward")
    evidence_refs = [_text(item) for item in _list(entry.get("evidence_refs")) if _text(item)]
    required_texts = {
        "checked_at": _text(entry.get("checked_at")),
        "entry_zone": _text(entry.get("entry_zone")),
        "invalidation": _text(entry.get("invalidation")),
        "upside_reference": _text(entry.get("upside_reference")),
        "downside_reference": _text(entry.get("downside_reference")),
        "chase_risk": _text(entry.get("chase_risk")),
    }
    refs_resolve = bool(evidence_refs) and all(ref in known_evidence for ref in evidence_refs)
    finalist_keys = {item.upper() for item in finalists}
    entry_ok = bool(
        ticker
        and selected_id
        and ticker.upper() == selected_id.upper()
        and ticker.upper() in finalist_keys
        and isinstance(current_price, (int, float))
        and current_price > 0
        and isinstance(risk_reward, (int, float))
        and risk_reward > 0
        and all(required_texts.values())
        and refs_resolve
    )
    checks.append(
        {
            "id": "stock_selected_entry_fit",
            "satisfied": entry_ok,
            "observed": {
                "selected_id": selected_id,
                "ticker": ticker,
                "current_price": current_price,
                "risk_reward": risk_reward,
                "fields": required_texts,
                "evidence_refs": evidence_refs,
                "evidence_refs_resolve": refs_resolve,
            },
        }
    )
    if not entry_ok:
        missing.append(
            "선정 종목의 현재가·확인 시점·진입 구간·무효화·상방과 하방 기준·손익비·추격 위험이 근거와 연결되지 않았습니다."
        )

    assumptions = [item for item in _list(coverage.get("assumptions")) if isinstance(item, Mapping)]
    horizon = None
    for item in assumptions:
        name = _text(item.get("name")).lower()
        if re.search(r"보유|기간|horizon|holding", name, re.I):
            horizon = item
            break
    horizon_basis = _text(horizon.get("basis")) if isinstance(horizon, Mapping) else ""
    horizon_sensitivity = _text(horizon.get("sensitivity")) if isinstance(horizon, Mapping) else ""
    horizon_ok = bool(
        (
            horizon
            and horizon_basis in {"user", "context"}
        )
        or (
            horizon
            and horizon_basis == "explicit_default"
            and horizon_sensitivity
        )
    )
    checks.append(
        {
            "id": "stock_material_horizon_basis",
            "satisfied": horizon_ok,
            "observed": dict(horizon) if isinstance(horizon, Mapping) else None,
        }
    )
    if not horizon_ok:
        missing.append(
            "보유 기간처럼 결론을 바꾸는 가정의 출처나, 명시적 기본값을 썼을 때의 민감도 설명이 없습니다."
        )

    if re.search(r"전액|몰빵|신용|레버리지", answer, re.I) and not entry_ok:
        warnings.append("강한 실행 제안이 현재 진입 적합성 증거보다 앞서 있습니다.")

    return {
        "missing_conditions": missing,
        "warnings": warnings,
        "checks": checks,
        "next_objective": (
            "Broaden and record the stock screening universe, then evaluate the selected finalist's current entry fit with linked price, invalidation, upside, downside and risk/reward evidence."
            if missing
            else ""
        ),
        "suggested_route": "RESEARCH" if missing else None,
        "changed_dimension": "information_source" if missing else "none",
    }
