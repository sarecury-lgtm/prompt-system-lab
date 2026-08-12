#!/usr/bin/env python3
"""Add Request Contract evidence verification to the persisted Controller session."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Mapping

import problem_solving_controller_session as BASE
import problem_solving_domain_adapters as DOMAINS
import problem_solving_evidence_verifier as VERIFIER
import problem_solving_request_contract as REQUEST
import problem_solving_selection_profiles as PROFILES


REQUEST_CONTRACT_FILE = "request_contract.json"
OBLIGATIONS_FILE = "evidence_obligations.json"
VERIFICATION_HISTORY_FILE = "verification_history.json"
DOMAIN_ADAPTER_FILE = "domain_adapter.json"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BASE.ControllerSessionError(f"검증 상태 파일이 손상됐습니다: {path.name}") from exc


def _metadata(session_dir: Path) -> dict[str, Any]:
    return {
        "request_contract": _read_json(session_dir / REQUEST_CONTRACT_FILE, {}),
        "evidence_obligations": _read_json(session_dir / OBLIGATIONS_FILE, []),
        "verification_history": _read_json(session_dir / VERIFICATION_HISTORY_FILE, []),
        "domain_adapter_id": _read_json(session_dir / DOMAIN_ADAPTER_FILE, {}).get("adapter_id"),
    }


def _save_metadata(
    session_dir: Path,
    *,
    request_contract: Mapping[str, Any],
    obligations: list[dict[str, Any]],
    history: list[dict[str, Any]],
    adapter_id: str | None,
) -> None:
    _write_json(session_dir / REQUEST_CONTRACT_FILE, dict(request_contract))
    _write_json(session_dir / OBLIGATIONS_FILE, obligations)
    _write_json(session_dir / VERIFICATION_HISTORY_FILE, history)
    _write_json(session_dir / DOMAIN_ADAPTER_FILE, {"adapter_id": adapter_id})


def _result_example(packet: Mapping[str, Any]) -> dict[str, Any]:
    coverage = PROFILES.prepare_coverage_template(
        packet.get("request_contract", {}),
        VERIFIER.empty_coverage(),
    )
    return {
        "version": 1,
        "session_id": packet["session_id"],
        "action_id": packet["action_id"],
        "route": packet["route"],
        "status": "completed",
        "completion": {"met": True, "missing": []},
        "evidence": [],
        "coverage": coverage,
        "artifacts": [],
        "limitations": [],
        "continuation": {
            "objective": "",
            "suggested_route": None,
            "changed_dimension": "none",
            "question": "",
        },
    }


def build_execution_prompt(packet: Mapping[str, Any]) -> str:
    example = _result_example(packet)
    profile_guidance = PROFILES.execution_guidance(packet.get("request_contract", {}))
    return f"""당신은 PSOS Controller가 선택한 현재 행동 하나를 실행하는 AI 엔진이다.
전체 워크플로를 임의로 재설계하지 말고, Action Packet의 objective를 수행하라.

[중요]
1. request_contract는 사용자가 실제로 요구한 행동·시점·범위·산출물이다. 더 쉬운 다른 문제로 바꾸지 않는다.
2. evidence_obligations는 Controller가 완료를 인정하기 위해 실제로 확인할 기록이다.
3. 검색·비교·선택을 했다고 말하는 것으로는 부족하다. coverage에 후보 범위, 확인 시점, 공통 비교, 선택, 행동 적합성과 가정 출처를 구조화한다.
4. 계정 메모리나 다른 대화에서 얻은 정보는 user 또는 context 근거로 속이지 않는다.
5. material=true인 가정은 basis를 user, context 또는 explicit_default로 기록한다. user/context이면 실제 request_contract에 있는 짧은 원문을 source_excerpt에 그대로 넣고, explicit_default이면 결론이 달라지는 조건을 sensitivity에 적는다.
6. 현재 상태나 후보 범위를 썼다면 evidence의 id/source/url을 coverage.current_state, coverage.search_scope와 관련 domain record의 evidence_refs에서 실제로 참조한다.
7. request_contract.domain_requirements.coverage_template가 있으면 그 구조를 coverage.domain 아래에 그대로 채운다.
8. {profile_guidance}
9. completion을 스스로 선언할 수는 있지만 Controller가 별도로 재검증한다. 증거가 없으면 partial로 기록한다.
10. 사용자용 실제 결과를 먼저 작성하고 내부 사고 과정은 출력하지 않는다.
11. 마지막에는 두 마커 사이에 JSON Action Result 하나만 넣는다.
12. needs_user_input은 합리적인 명시적 기본값이나 민감도 분석으로 진행할 수 없고, 답이 결론을 크게 바꿀 때만 사용한다.

[Action Result 형식]
{BASE.START_MARKER}
```json
{json.dumps(example, ensure_ascii=False, indent=2)}
```
{BASE.END_MARKER}

[PSOS Controller Action Packet]
```json
{json.dumps(dict(packet), ensure_ascii=False, indent=2)}
```
"""


def _enrich_current_action(
    session_dir: Path,
    state: dict[str, Any],
    metadata: Mapping[str, Any],
    *,
    replace_initial_objective: bool = False,
) -> dict[str, Any]:
    current = state.get("current_action")
    if not isinstance(current, dict):
        return state
    packet = current["packet"]
    packet["request_contract"] = metadata["request_contract"]
    packet["evidence_obligations"] = metadata["evidence_obligations"]
    known_state = packet.setdefault("known_state", {})
    known_state["verification_history"] = metadata["verification_history"]
    if replace_initial_objective and packet.get("action_number") == 1:
        packet["objective"] = REQUEST.initial_objective(metadata["request_contract"])
        packet["reason"] = (
            "Request Contract에서 생성된 완료 의무를 충족하는 가장 작은 초기 행동입니다."
        )
    current["execution_prompt"] = build_execution_prompt(packet)
    state["current_action"] = current
    for index, action in enumerate(state["actions"]):
        if action["packet"]["action_id"] == packet["action_id"]:
            state["actions"][index] = current
            break
    BASE._write_state(session_dir, state)
    return state


def _build_contract_and_obligations(
    request: str,
    context: str,
    adapter_id: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract = REQUEST.build_request_contract(
        request,
        context=context,
        domain_hint=adapter_id or "generic",
    )
    contract = DOMAINS.augment_contract(contract, adapter_id)
    obligations = [
        *REQUEST.build_evidence_obligations(contract),
        *DOMAINS.additional_obligations(contract, adapter_id),
    ]
    return contract, obligations


def create_session(
    request: str,
    *,
    context: str = "",
    route_hint: str = "",
    output_root: Path,
    session_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    adapter_id = DOMAINS.detect_adapter_id(request)
    contract, obligations = _build_contract_and_obligations(request, context, adapter_id)
    session_dir, state = BASE.create_session(
        request,
        context=context,
        route_hint=route_hint,
        output_root=output_root,
        session_id=session_id,
    )
    _save_metadata(
        session_dir,
        request_contract=contract,
        obligations=obligations,
        history=[],
        adapter_id=adapter_id,
    )

    preference_question = REQUEST.preference_question_if_needed(contract)
    if preference_question:
        state["status"] = "awaiting_user_input"
        state["current_action"] = None
        state["awaiting_user_question"] = preference_question
        state["unresolved"] = BASE._unique_strings(
            [*state["unresolved"], "최종 선택 전에 사용자의 우선 기준을 확인해야 합니다."]
        )
        BASE._write_state(session_dir, state)
        return session_dir, state

    state = _enrich_current_action(
        session_dir,
        state,
        _metadata(session_dir),
        replace_initial_objective=True,
    )
    return session_dir, state


def load_session(session_dir: Path) -> dict[str, Any]:
    return BASE.load_session(session_dir)


def _base_result(result: Mapping[str, Any], verdict: Mapping[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    completion = dict(result.get("completion") or {})
    missing = [
        *[str(item).strip() for item in completion.get("missing", []) if str(item).strip()],
        *[str(item).strip() for item in verdict.get("missing_conditions", []) if str(item).strip()],
    ]
    missing = list(dict.fromkeys(missing))
    if status == "completed" and not verdict.get("satisfied"):
        status = "partial"
        completion = {"met": False, "missing": missing}
    elif status == "partial":
        completion = {"met": False, "missing": missing}
    continuation = dict(result.get("continuation") or {})
    if missing and verdict.get("next_objective"):
        continuation["objective"] = verdict["next_objective"]
        continuation["suggested_route"] = verdict.get("suggested_route")
        continuation["changed_dimension"] = verdict.get("changed_dimension") or "information_source"
    limitations = [
        *[str(item).strip() for item in result.get("limitations", []) if str(item).strip()],
        *[str(item).strip() for item in verdict.get("warnings", []) if str(item).strip()],
    ]
    return {
        "version": result.get("version", 1),
        "session_id": result.get("session_id"),
        "action_id": result.get("action_id"),
        "route": result.get("route"),
        "status": status,
        "completion": completion,
        "evidence": result.get("evidence", []),
        "artifacts": result.get("artifacts", []),
        "limitations": list(dict.fromkeys(limitations)),
        "continuation": {
            "objective": str(continuation.get("objective") or "").strip(),
            "suggested_route": continuation.get("suggested_route"),
            "changed_dimension": continuation.get("changed_dimension") or "none",
            "question": str(continuation.get("question") or "").strip(),
        },
    }


def _raw_for_base(answer: str, result: Mapping[str, Any]) -> str:
    return (
        answer.strip()
        + "\n\n"
        + BASE.START_MARKER
        + "\n```json\n"
        + json.dumps(dict(result), ensure_ascii=False, indent=2)
        + "\n```\n"
        + BASE.END_MARKER
    )


def _merge_profile_verdict(
    base_verdict: Mapping[str, Any],
    profile_verdict: Mapping[str, Any],
) -> dict[str, Any]:
    verdict = dict(base_verdict)
    profile_missing = [
        str(item).strip()
        for item in profile_verdict.get("missing_conditions", [])
        if str(item).strip()
    ]
    profile_warnings = [
        str(item).strip()
        for item in profile_verdict.get("warnings", [])
        if str(item).strip()
    ]
    verdict["missing_conditions"] = list(
        dict.fromkeys([*verdict.get("missing_conditions", []), *profile_missing])
    )
    verdict["warnings"] = list(
        dict.fromkeys([*verdict.get("warnings", []), *profile_warnings])
    )
    verdict["checks"] = [
        *verdict.get("checks", []),
        *profile_verdict.get("checks", []),
    ]
    verdict["satisfied"] = bool(
        verdict.get("satisfied") and profile_verdict.get("satisfied", True)
    )
    if profile_missing and not str(verdict.get("next_objective") or "").strip():
        verdict["next_objective"] = str(profile_verdict.get("next_objective") or "").strip()
        verdict["changed_dimension"] = "interaction"
    return verdict


def submit_action_result(session_dir: Path, raw_answer: str) -> dict[str, Any]:
    state = BASE.load_session(session_dir)
    current = state.get("current_action")
    if state.get("status") != "awaiting_execution" or not isinstance(current, dict):
        raise BASE.ControllerSessionError("현재 실행 결과를 받을 상태가 아닙니다.")
    packet = current["packet"]
    imported = BASE.parse_action_result(raw_answer, packet=packet)
    result = imported.get("result")
    metadata = _metadata(session_dir)
    history = list(metadata["verification_history"])

    if not isinstance(result, dict):
        next_state = BASE.submit_action_result(session_dir, raw_answer)
        history.append(
            {
                "version": 1,
                "checked_at": _now(),
                "action_id": packet["action_id"],
                "satisfied": False,
                "missing_conditions": ["구조화된 Action Result가 없어 증거 의무를 검사할 수 없습니다."],
                "warnings": imported.get("warnings", []),
                "checks": [],
            }
        )
        _save_metadata(
            session_dir,
            request_contract=metadata["request_contract"],
            obligations=metadata["evidence_obligations"],
            history=history,
            adapter_id=metadata["domain_adapter_id"],
        )
        return next_state

    adapter = DOMAINS.get_adapter(metadata["domain_adapter_id"])
    generic_obligations = [
        item
        for item in metadata["evidence_obligations"]
        if item.get("verifier") != PROFILES.PROFILE_VERIFIER_ID
    ]
    verdict = VERIFIER.verify_result(
        metadata["request_contract"],
        generic_obligations,
        imported.get("answer", ""),
        result,
        domain_adapter=adapter,
    )
    verdict = _merge_profile_verdict(
        verdict,
        PROFILES.verify_result(metadata["request_contract"], result),
    )
    history_record = {
        "version": 1,
        "checked_at": _now(),
        "action_id": packet["action_id"],
        "model_status": result.get("status"),
        "satisfied": verdict["satisfied"],
        "missing_conditions": verdict["missing_conditions"],
        "warnings": verdict["warnings"],
        "checks": verdict["checks"],
    }
    history.append(history_record)
    adjusted = _base_result(result, verdict)
    next_state = BASE.submit_action_result(
        session_dir,
        _raw_for_base(str(imported.get("answer") or ""), adjusted),
    )
    _save_metadata(
        session_dir,
        request_contract=metadata["request_contract"],
        obligations=metadata["evidence_obligations"],
        history=history,
        adapter_id=metadata["domain_adapter_id"],
    )
    if next_state.get("status") == "awaiting_execution":
        next_state = _enrich_current_action(
            session_dir,
            next_state,
            _metadata(session_dir),
        )
    return next_state


def _resolve_pre_execution_question(
    session_dir: Path,
    state: dict[str, Any],
    metadata: Mapping[str, Any],
    answer: str,
) -> dict[str, Any] | None:
    question = REQUEST.preference_question_if_needed(dict(metadata["request_contract"]))
    if (
        not question
        or state.get("status") != "awaiting_user_input"
        or state.get("budget", {}).get("used_actions") != 0
    ):
        return None

    clean_answer = str(answer or "").strip()
    if not clean_answer:
        raise BASE.ControllerSessionError("사용자 답변이 비어 있습니다.")
    actual_question = str(state.get("awaiting_user_question") or question).strip()
    state["goal"]["fixed_constraints"] = BASE._unique_strings(
        [
            *state["goal"]["fixed_constraints"],
            f"사용자 확인: {actual_question} → {clean_answer}",
        ]
    )
    state["context"] = (
        state["context"].rstrip()
        + ("\n\n" if state["context"].strip() else "")
        + f"[사용자 확인]\n질문: {actual_question}\n답변: {clean_answer}"
    )
    state["awaiting_user_question"] = None
    state["unresolved"] = [
        item
        for item in state["unresolved"]
        if item != "최종 선택 전에 사용자의 우선 기준을 확인해야 합니다."
    ]

    adapter_id = metadata["domain_adapter_id"] or DOMAINS.detect_adapter_id(state["request"])
    contract, obligations = _build_contract_and_obligations(
        state["request"],
        state["context"],
        adapter_id,
    )
    _save_metadata(
        session_dir,
        request_contract=contract,
        obligations=obligations,
        history=list(metadata["verification_history"]),
        adapter_id=adapter_id,
    )

    if not state.get("actions"):
        raise BASE.ControllerSessionError("재개할 초기 Controller action이 없습니다.")
    action = state["actions"][-1]
    packet = action["packet"]
    packet["goal"] = state["goal"]
    packet.setdefault("known_state", {})["context"] = state["context"]
    packet["objective"] = REQUEST.initial_objective(contract)
    packet["reason"] = "최종 선택 전에 사용자 우선 기준을 확인했고, 같은 첫 행동을 그 기준으로 실행합니다."
    action["packet"] = packet
    state["actions"][-1] = action
    state["current_action"] = action
    state["status"] = "awaiting_execution"
    BASE._write_state(session_dir, state)
    return _enrich_current_action(
        session_dir,
        state,
        _metadata(session_dir),
    )


def submit_user_input(session_dir: Path, answer: str) -> dict[str, Any]:
    state = BASE.load_session(session_dir)
    metadata = _metadata(session_dir)
    pre_execution = _resolve_pre_execution_question(
        session_dir,
        state,
        metadata,
        answer,
    )
    if pre_execution is not None:
        return pre_execution

    state = BASE.submit_user_input(session_dir, answer)
    adapter_id = metadata["domain_adapter_id"] or DOMAINS.detect_adapter_id(state["request"])
    contract, obligations = _build_contract_and_obligations(
        state["request"],
        state["context"],
        adapter_id,
    )
    _save_metadata(
        session_dir,
        request_contract=contract,
        obligations=obligations,
        history=list(metadata["verification_history"]),
        adapter_id=adapter_id,
    )
    if state.get("status") == "awaiting_execution":
        state = _enrich_current_action(session_dir, state, _metadata(session_dir))
    return state


def public_session(state: Mapping[str, Any], *, session_dir: Path | None = None) -> dict[str, Any]:
    payload = BASE.public_session(state)
    if session_dir is None:
        return payload
    metadata = _metadata(session_dir)
    payload["request_contract"] = metadata["request_contract"]
    payload["evidence_obligations"] = metadata["evidence_obligations"]
    payload["domain_adapter_id"] = metadata["domain_adapter_id"]
    payload["verification_history"] = metadata["verification_history"]
    payload["last_verification"] = (
        metadata["verification_history"][-1]
        if metadata["verification_history"]
        else None
    )
    return payload
