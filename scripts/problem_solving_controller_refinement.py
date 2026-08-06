#!/usr/bin/env python3
"""Reopen a terminal PSOS Controller session from explicit user feedback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import problem_solving_controller_session as BASE
import problem_solving_controller_session_verified as VERIFIED
import problem_solving_domain_adapters as DOMAINS
import problem_solving_request_contract as REQUEST


TERMINAL_STATUSES = {"completed", "partial", "blocked"}
MAX_FEEDBACK_CHARS = 8000


def _clean(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise BASE.ControllerSessionError(f"{label}이 비어 있습니다.")
    if len(text) > MAX_FEEDBACK_CHARS:
        raise BASE.ControllerSessionError(
            f"{label}은 {MAX_FEEDBACK_CHARS:,}자 이하여야 합니다."
        )
    return text


def _next_route(last_route: str, direction: str) -> str:
    inferred = BASE.infer_route(direction)
    if inferred == "DIRECT" and last_route != "DIRECT":
        return last_route
    return inferred


def submit_user_refinement(
    session_dir: Path,
    *,
    reason: str = "",
    direction: str,
) -> dict[str, Any]:
    """Use explicit user feedback to create one new action without spending method-change budget."""

    state = BASE.load_session(session_dir)
    if state["status"] not in TERMINAL_STATUSES:
        raise BASE.ControllerSessionError(
            "완료·부분 완료·차단 상태의 결과만 사용자 의견으로 다시 열 수 있습니다."
        )
    clean_reason = _clean(reason, "수정 이유")
    clean_direction = _clean(direction, "수정 방향", required=True)
    if state["budget"]["used_actions"] >= BASE.MAX_ACTIONS:
        raise BASE.ControllerSessionError(
            "이 세션은 AI action 한도를 모두 사용했습니다. 새 요청으로 시작해야 합니다."
        )

    feedback_lines = ["[사용자 결과 피드백]"]
    if clean_reason:
        feedback_lines.append(f"이유: {clean_reason}")
    feedback_lines.append(f"다음 방향: {clean_direction}")
    feedback_block = "\n".join(feedback_lines)

    new_constraints = list(state["goal"]["fixed_constraints"])
    if clean_reason:
        new_constraints.append(f"사용자 결과 피드백의 이유: {clean_reason}")
    new_constraints.append(f"사용자가 지정한 다음 방향: {clean_direction}")
    state["goal"]["fixed_constraints"] = BASE._unique_strings(new_constraints)
    state["context"] = (
        state["context"].rstrip()
        + ("\n\n" if state["context"].strip() else "")
        + feedback_block
    )
    state["unresolved"] = BASE._unique_strings(
        [*state["unresolved"], f"사용자 수정 방향: {clean_direction}"]
    )
    state["final_answer"] = ""
    state["awaiting_user_question"] = None

    last_route = state["actions"][-1]["packet"]["route"]
    next_route = _next_route(last_route, clean_direction)
    objective = (
        "기존 결과를 그대로 반복하지 말고, 사용자 피드백의 이유를 반영해 "
        f"다음 방향으로 결과를 수정한다: {clean_direction}"
    )
    action = BASE._build_action(
        state,
        route=next_route,
        objective=objective,
        reason=(
            "사용자가 기존 결과를 본 뒤 문제의 이유와 다음 방향을 직접 지정했습니다. "
            "이는 자동 재시도가 아니라 사용자 주도 수정입니다."
        ),
        changed_dimension="interaction",
    )
    state["actions"].append(action)
    state["current_action"] = action
    state["status"] = "awaiting_execution"
    BASE._write_state(session_dir, state)
    (session_dir / "result.md").unlink(missing_ok=True)

    metadata = VERIFIED._metadata(session_dir)
    adapter_id = metadata["domain_adapter_id"] or DOMAINS.detect_adapter_id(
        state["request"]
    )
    contract = REQUEST.build_request_contract(
        state["request"],
        context=state["context"],
        domain_hint=adapter_id or "generic",
    )
    contract = DOMAINS.augment_contract(contract, adapter_id)
    obligations = [
        *REQUEST.build_evidence_obligations(contract),
        *DOMAINS.additional_obligations(contract, adapter_id),
    ]
    VERIFIED._save_metadata(
        session_dir,
        request_contract=contract,
        obligations=obligations,
        history=list(metadata["verification_history"]),
        adapter_id=adapter_id,
    )
    return VERIFIED._enrich_current_action(
        session_dir,
        state,
        VERIFIED._metadata(session_dir),
    )
