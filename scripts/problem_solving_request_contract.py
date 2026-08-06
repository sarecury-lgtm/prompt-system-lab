#!/usr/bin/env python3
"""Build a domain-neutral Request Contract and observable evidence obligations."""

from __future__ import annotations

import re
from typing import Any


REQUEST_CONTRACT_VERSION = 1
OBLIGATION_VERSION = 1


class RequestContractError(ValueError):
    """Raised when a request cannot be represented without changing its meaning."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestContractError(f"{label}이 비어 있습니다.")
    return value.strip()


def _contains(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I) is not None


def _infer_requested_action(text: str) -> str:
    if _contains(r"매수|사도|사면|살까|살 만|지금 사|오늘 사|구매|예약|신청|지원|진입", text):
        return "act_now"
    if _contains(r"매도|팔까|손절|청산|취소", text):
        return "exit_or_avoid"
    if _contains(r"추천|골라|선택|1순위|가장 좋은|베스트|best", text):
        return "select"
    if _contains(r"비교|차이|우열|순위", text):
        return "compare"
    if _contains(r"조사|검색|찾아|확인|검증", text):
        return "research"
    if _contains(r"만들|작성|구현|수정|고쳐|생성", text):
        return "produce"
    return "answer"


def _infer_decision_time(text: str) -> str:
    if _contains(r"오늘|지금|현재|당장|이번 주|이번주|금일|장 시작|개장|마감 전", text):
        return "current"
    if _contains(r"최신|최근|현행|이번 달|이번달", text):
        return "recent"
    if _contains(r"내일|다음 주|다음주|예정|앞으로", text):
        return "future"
    return "unspecified"


def _infer_selection_count(text: str, action: str) -> int | None:
    match = re.search(r"(?:최종|상위|추천)?\s*(\d{1,2})\s*(?:개|명|곳|종목|제품|후보)", text)
    if match:
        return max(1, int(match.group(1)))
    if _contains(r"1순위|한\s*(?:개|명|곳|종목|제품)|하나|단 하나|한 종목", text):
        return 1
    if action in {"select", "act_now", "exit_or_avoid"} and _contains(
        r"추천|골라|선택|가장 좋은|뭐가 좋|어떤 .* 좋|무엇 .* 좋", text
    ):
        return 1
    return None


def _infer_open_target_set(text: str, action: str) -> bool:
    if action not in {"select", "act_now", "compare"}:
        return False
    broad_scope = _contains(
        r"주식|종목|상품|제품|후보|도구|서비스|앱|학교|대학|지역|동네|여행지|식당|"
        r"호텔|차량|자동차|신발|러닝화|카드|보험|직업|회사|모델|옵션|선택지",
        text,
    )
    explicit_single = _contains(
        r"\b[A-Z]{2,6}\b|이 종목|이 제품|이 회사|이 파일|이 도구|이 모델|둘 중|두 개 중|"
        r"[가-힣A-Za-z0-9._-]+\s*(?:사도|살까|어때|분석)",
        text,
    )
    if _contains(r"추천|찾아|골라|가장 좋은|1순위|후보", text) and broad_scope:
        return True
    return broad_scope and not explicit_single


def _infer_user_constraints(text: str, context: str) -> list[dict[str, str]]:
    constraints: list[dict[str, str]] = []
    if text.strip():
        constraints.append({"source": "request", "text": text.strip()})
    if context.strip():
        constraints.append({"source": "context", "text": context.strip()})
    return constraints


def build_request_contract(
    request: str,
    *,
    context: str = "",
    domain_hint: str = "generic",
) -> dict[str, Any]:
    """Represent what the user asked before choosing tools or writing prompts."""

    clean_request = _text(request, "사용자 요청")
    clean_context = str(context or "").strip()
    action = _infer_requested_action(clean_request)
    decision_time = _infer_decision_time(clean_request)
    selection_count = _infer_selection_count(clean_request, action)
    open_target_set = _infer_open_target_set(clean_request, action)
    comparison_required = action == "compare" or selection_count is not None or _contains(
        r"추천|비교|순위|가장 좋은|1순위|골라|선택", clean_request
    )
    current_conditions_required = decision_time in {"current", "recent"} or _contains(
        r"가격|재고|뉴스|실적|법|규정|일정|버전|패치|현재 상태", clean_request
    )
    candidate_search_required = bool(open_target_set and comparison_required)
    action_fit_required = action in {"act_now", "exit_or_avoid"} or (
        selection_count is not None and decision_time in {"current", "recent"}
    )
    deliverable = (
        "action_decision"
        if action in {"act_now", "exit_or_avoid"}
        else "selection"
        if selection_count is not None
        else "comparison"
        if comparison_required
        else "usable_result"
    )
    return {
        "version": REQUEST_CONTRACT_VERSION,
        "original_request": clean_request,
        "requested_action": action,
        "decision_time": decision_time,
        "target_scope": {
            "kind": "open_set" if open_target_set else "specified_or_bounded",
            "candidate_search_required": candidate_search_required,
        },
        "deliverable": deliverable,
        "selection_count": selection_count,
        "comparison_required": comparison_required,
        "current_conditions_required": current_conditions_required,
        "action_fit_required": action_fit_required,
        "domain_hint": str(domain_hint or "generic").strip() or "generic",
        "user_constraints": _infer_user_constraints(clean_request, clean_context),
        "assumption_policy": {
            "silent_material_defaults_allowed": False,
            "material_unknown_resolution": "ask_or_label_and_test_sensitivity",
        },
    }


def build_evidence_obligations(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate observable completion duties from request meaning."""

    obligations: list[dict[str, Any]] = [
        {
            "version": OBLIGATION_VERSION,
            "id": "goal_fidelity",
            "category": "goal",
            "required": True,
            "verifier": "generic",
            "description": "The produced result answers the requested action and deliverable without replacing them with an easier problem.",
        },
        {
            "version": OBLIGATION_VERSION,
            "id": "assumption_traceability",
            "category": "assumptions",
            "required": True,
            "verifier": "generic",
            "description": "Every material assumption is tied to the user, supplied context, or an explicit default with sensitivity stated.",
        },
    ]
    if contract.get("current_conditions_required"):
        obligations.append(
            {
                "version": OBLIGATION_VERSION,
                "id": "current_state_record",
                "category": "time",
                "required": True,
                "verifier": "generic",
                "description": "Current or recent conditions that can change the answer are recorded with a check time and evidence references.",
            }
        )
    if contract.get("target_scope", {}).get("candidate_search_required"):
        obligations.append(
            {
                "version": OBLIGATION_VERSION,
                "id": "candidate_search_scope",
                "category": "search",
                "required": True,
                "verifier": "generic",
                "description": "The candidate universe, filters, screened count and finalists are observable rather than implied by a short hand-picked list.",
            }
        )
    if contract.get("comparison_required"):
        obligations.append(
            {
                "version": OBLIGATION_VERSION,
                "id": "comparable_evaluation",
                "category": "comparison",
                "required": True,
                "verifier": "generic",
                "description": "Multiple relevant candidates are compared using shared criteria linked to the requested action.",
            }
        )
    if contract.get("selection_count") is not None:
        obligations.append(
            {
                "version": OBLIGATION_VERSION,
                "id": "final_selection",
                "category": "decision",
                "required": True,
                "verifier": "generic",
                "description": "The requested number of winners is named with a concrete action and reason grounded in the comparison.",
            }
        )
    if contract.get("action_fit_required"):
        obligations.append(
            {
                "version": OBLIGATION_VERSION,
                "id": "current_action_fit",
                "category": "decision",
                "required": True,
                "verifier": "domain",
                "description": "The selected option is shown to fit the requested action at the requested time, not merely to be good in general.",
            }
        )
    return obligations


def initial_objective(contract: dict[str, Any]) -> str:
    if contract.get("target_scope", {}).get("candidate_search_required"):
        return (
            "Build an observable candidate search record, compare the strongest relevant finalists under shared criteria, "
            "and produce the requested selection only when the evidence obligations are satisfied."
        )
    if contract.get("current_conditions_required"):
        return (
            "Check the current conditions that can change the answer, connect them to the user's requested action, "
            "and produce a usable result with an observable completion record."
        )
    if contract.get("comparison_required"):
        return "Compare the bounded options under shared criteria and produce the requested usable conclusion."
    return "Produce the directly requested usable result while preserving the request and explicit context."
