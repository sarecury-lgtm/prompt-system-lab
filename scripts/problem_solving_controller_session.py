#!/usr/bin/env python3
"""Persist a domain-neutral PSOS Controller session across manual or automatic action adapters."""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping


ROUTES = ("DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT")
ROUTE_SET = set(ROUTES)
SESSION_STATUSES = {
    "awaiting_execution",
    "awaiting_user_input",
    "completed",
    "partial",
    "blocked",
}
RESULT_STATUSES = {"completed", "partial", "blocked", "needs_user_input"}
CHANGED_DIMENSIONS = {"none", "route", "tool", "information_source", "interaction"}
MUTATING_ROUTES = {"CODE", "PROJECT"}
MAX_ACTIONS = 4
MAX_METHOD_CHANGES = 1
START_MARKER = "<!-- PSOS_ACTION_RESULT_START -->"
END_MARKER = "<!-- PSOS_ACTION_RESULT_END -->"
STATE_FILENAME = "controller_session.json"


class ControllerSessionError(ValueError):
    """Raised when a persisted Controller session cannot preserve its contract."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControllerSessionError(f"{label}이 비어 있습니다.")
    return value.strip()


def _unique_strings(values: Any) -> list[str]:
    output: list[str] = []
    for value in values if isinstance(values, list) else []:
        text = str(value or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _safe_session_id(value: str) -> str:
    cleaned = _text(value, "session_id")
    if re.fullmatch(r"[A-Za-z0-9._-]+", cleaned) is None:
        raise ControllerSessionError("session_id 형식이 올바르지 않습니다.")
    return cleaned


def infer_route(request: str, route_hint: str = "") -> str:
    hint = str(route_hint or "").strip().upper()
    if hint in ROUTE_SET:
        return hint

    text = _text(request, "사용자 요청")
    write_target = re.search(
        r"코드|버그|파일|폴더|웹페이지|웹사이트|앱|저장소|레포|repository|"
        r"html|css|javascript|typescript|python|스크립트",
        text,
        re.I,
    )
    write_action = re.search(r"만들|구현|수정|고쳐|추가|삭제|리팩터|적용|배포|테스트", text, re.I)
    if write_target and write_action:
        return "CODE"

    reuse_target = re.search(r"기존|이미 있는|재사용|reuse|도구|템플릿|스크립트|자산", text, re.I)
    reuse_action = re.search(r"활용|재사용|쓸 수|검토|찾아|대신|새로 만들", text, re.I)
    if reuse_target and reuse_action:
        return "REUSE"

    if re.search(r"프롬프트|prompt", text, re.I) and re.search(
        r"만들|작성|설계|생성|짜|다듬|개선|최적화", text, re.I
    ):
        return "PROMPT"

    if re.search(r"장기|여러 단계|여러 파일|전체 시스템|프로젝트를|아키텍처", text, re.I):
        return "PROJECT"

    if re.search(
        r"최신|오늘|현재|지금|가격|뉴스|법|규정|일정|패치|버전|검색|조사|"
        r"찾아|확인|검증|판매 중|재고|추천|후보|비교|가장 좋은|1위",
        text,
        re.I,
    ):
        return "RESEARCH"
    return "DIRECT"


def completion_condition(route: str) -> str:
    conditions = {
        "DIRECT": "제공된 요청과 문맥만으로 사용자가 바로 쓸 수 있는 직접 결과가 완성되면 완료다.",
        "RESEARCH": "변동 가능한 핵심 사실이 현재 근거와 확인 시점에 연결되고 사용자가 판단할 결론이 완성되면 완료다.",
        "REUSE": "실제 기존 자산을 확인하고 재사용·부분 보완·신규 제작 중 하나를 근거와 실행 방법까지 결정하면 완료다.",
        "PROMPT": "다른 AI가 추가 해석 없이 바로 실행할 수 있는 최종 프롬프트 하나가 완성되면 완료다.",
        "CODE": "허용 범위의 적용 가능한 변경과 검증 결과가 제시되고 실제 적용 여부가 정직하게 구분되면 완료다.",
        "PROJECT": "상위 목표와 단계 상태가 보존된 실행 가능한 산출물 또는 정직한 다음 인계 상태가 만들어지면 완료다.",
    }
    return conditions[route]


def _initial_objective(route: str, request: str) -> str:
    objectives = {
        "DIRECT": "제공된 요청과 문맥을 직접 분석해 최종 결과를 완성한다.",
        "RESEARCH": "결론을 바꾸는 최신 사실을 확인하고 근거가 연결된 최종 판단을 만든다.",
        "REUSE": "실제 기존 자산을 확인해 재사용·보완·신규 제작 중 가장 작은 충분 방법을 결정한다.",
        "PROMPT": "목표와 고정 조건을 보존한 실행용 최종 프롬프트를 완성한다.",
        "CODE": "요청된 코드 또는 파일 변경을 최소 범위로 설계하고 검증 가능한 결과를 만든다.",
        "PROJECT": "상위 목표를 보존한 채 현재 세션에서 완료 가능한 가장 작은 실제 단계를 수행한다.",
    }
    return objectives[route]


def _required_output(route: str) -> list[str]:
    common = ["사용자가 읽을 실제 결과", "완료 여부와 남은 제한"]
    specific = {
        "DIRECT": ["직접 결론과 필요한 근거"],
        "RESEARCH": ["현재 근거와 확인 시점", "근거를 반영한 하나의 결론"],
        "REUSE": ["확인한 자산", "재사용·부분 보완·신규 제작 결정", "정확한 사용 방법"],
        "PROMPT": ["복사해 바로 사용할 최종 프롬프트 하나"],
        "CODE": ["변경 대상", "적용 가능한 변경 내용", "검증 방법 또는 실행 결과"],
        "PROJECT": ["현재 단계 산출물", "보존해야 할 상태", "다음 안전 상태"],
    }
    return [*specific[route], *common]


def _completion_checks(route: str) -> list[str]:
    common = [
        "사용자 목표와 명시적 조건을 다른 문제로 바꾸지 않았는가",
        "확인하지 않은 사실이나 실행을 완료했다고 주장하지 않았는가",
        "설명이나 계획만 남기지 않고 현재 행동의 실제 결과를 만들었는가",
    ]
    route_checks = {
        "DIRECT": ["질문에 직접 답했는가"],
        "RESEARCH": ["변동 가능한 핵심 주장에 출처와 확인 시점이 있는가", "자료 목록이 아니라 결론이 있는가"],
        "REUSE": ["기존 자산의 실제 존재와 적합성을 확인했는가", "새 제작보다 재사용이 나은지 비교했는가"],
        "PROMPT": ["다른 AI가 추가 질문 없이 바로 실행할 수 있는가", "최종 프롬프트 외 내부 생성 과정이 섞이지 않았는가"],
        "CODE": ["변경 범위와 적용 여부가 명확한가", "검증 명령 또는 결과가 있는가"],
        "PROJECT": ["상위 목표와 현재 단계가 연결되는가", "상태가 다음 세션에서도 이어질 수 있는가"],
    }
    return [*common, *route_checks[route]]


def _goal(request: str, context: str, route: str) -> dict[str, Any]:
    constraints = ["사용자가 요청에 명시한 대상, 범위와 조건을 보존한다."]
    if context.strip():
        constraints.append("제공된 문맥을 불투명한 외부 기억보다 우선한다.")
    return {
        "parent_goal": request,
        "fixed_constraints": constraints,
        "completion_condition": completion_condition(route),
    }


def _result_example(session_id: str, action_id: str, route: str) -> dict[str, Any]:
    return {
        "version": 1,
        "session_id": session_id,
        "action_id": action_id,
        "route": route,
        "status": "completed",
        "completion": {"met": True, "missing": []},
        "evidence": [],
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
    example = _result_example(
        str(packet["session_id"]),
        str(packet["action_id"]),
        str(packet["route"]),
    )
    return f"""당신은 PSOS Controller가 선택한 현재 행동 하나를 실행하는 AI 엔진이다.
전체 워크플로를 임의로 재설계하지 말고, 아래 Action Packet의 objective만 끝까지 수행하라.

[실행 원칙]
1. packet의 goal과 known_state를 현재 작업의 명시적 기준으로 사용한다.
2. 계정 메모리나 다른 대화에서 떠오른 정보는 필수 입력으로 간주하지 않는다. 그것이 결론을 바꾸면 현재 자료로 다시 확인하거나 가정이라고 밝힌다.
3. route에 필요한 검색·분석·재사용 검토·작성·코드 작업을 실제로 수행한다.
4. completion_checks를 모두 확인한다. 충족하지 못하면 completed라고 쓰지 않는다.
5. 사용자에게 보여줄 실제 결과를 먼저 작성한다. 내부 단계별 사고 과정은 출력하지 않는다.
6. 마지막에는 두 마커 사이에 JSON Action Result 하나만 넣는다.
7. status는 완료 조건 충족 시 completed, 다음 행동으로 메울 구체적 결손이 있으면 partial, 핵심 능력이 없으면 blocked, 사용자 답이 반드시 필요하면 needs_user_input이다.
8. partial이면 completion.missing에 관찰 가능한 결손을 적고 continuation에 다음 행동의 목적을 적는다. 같은 행동을 말만 바꿔 반복하도록 제안하지 않는다.
9. needs_user_input이면 continuation.question에 결론을 바꾸는 질문 하나만 적는다.
10. 실제 생성·수정하지 않은 파일을 artifacts에서 created 또는 modified라고 주장하지 않는다.

[Action Result 형식]
{START_MARKER}
```json
{json.dumps(example, ensure_ascii=False, indent=2)}
```
{END_MARKER}

[PSOS Controller Action Packet]
```json
{json.dumps(dict(packet), ensure_ascii=False, indent=2)}
```
"""


def _build_action(
    state: Mapping[str, Any],
    *,
    route: str,
    objective: str,
    reason: str,
    changed_dimension: str,
) -> dict[str, Any]:
    if route not in ROUTE_SET:
        raise ControllerSessionError(f"지원하지 않는 route입니다: {route}")
    if changed_dimension not in CHANGED_DIMENSIONS:
        raise ControllerSessionError("changed_dimension이 올바르지 않습니다.")
    action_number = len(state["actions"]) + 1
    if action_number > MAX_ACTIONS:
        raise ControllerSessionError("수동 Controller action 한도를 초과했습니다.")
    action_id = f"{state['session_id']}-a{action_number}"
    packet = {
        "version": 1,
        "session_id": state["session_id"],
        "action_id": action_id,
        "action_number": action_number,
        "route": route,
        "objective": _text(objective, "action objective"),
        "changed_dimension": changed_dimension,
        "reason": _text(reason, "action reason"),
        "goal": state["goal"],
        "known_state": {
            "context": state["context"],
            "verified_findings": state["verified_findings"],
            "unresolved": state["unresolved"],
            "previous_answer": state["best_answer"],
        },
        "required_output": _required_output(route),
        "completion_checks": _completion_checks(route),
        "forbidden": [
            "사용자 목표나 고정 조건을 임의로 변경하기",
            "확인하지 않은 실행·검색·파일 변경을 완료했다고 주장하기",
            "현재 objective 대신 전체 시스템 계획을 다시 설명하기",
            "같은 행동을 표현만 바꿔 반복하기",
        ],
        "output_contract": {
            "answer_first": True,
            "result_marker_start": START_MARKER,
            "result_marker_end": END_MARKER,
        },
    }
    return {
        "packet": packet,
        "execution_prompt": build_execution_prompt(packet),
        "status": "pending",
        "answer": "",
        "result": None,
        "warnings": [],
    }


def _session_dir(output_root: Path, session_id: str) -> Path:
    return output_root.expanduser().resolve() / _safe_session_id(session_id)


def _write_state(session_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _validate_state(state)
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / STATE_FILENAME).write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    current = state.get("current_action")
    current_path = session_dir / "current_action.json"
    prompt_path = session_dir / "current_action_prompt.txt"
    if isinstance(current, dict):
        current_path.write_text(
            json.dumps(current["packet"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        prompt_path.write_text(current["execution_prompt"], encoding="utf-8")
    else:
        current_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)
    if state["status"] in {"completed", "partial", "blocked"}:
        (session_dir / "result.md").write_text(
            state["final_answer"] or state["best_answer"] or "완성된 결과가 없습니다.",
            encoding="utf-8",
        )


def _validate_state(state: Mapping[str, Any]) -> None:
    required = {
        "version",
        "session_id",
        "created_at",
        "updated_at",
        "request",
        "context",
        "goal",
        "status",
        "budget",
        "verified_findings",
        "unresolved",
        "actions",
        "current_action",
        "awaiting_user_question",
        "best_answer",
        "final_answer",
        "limitations",
    }
    if set(state) != required:
        raise ControllerSessionError("Controller session 최상위 필드가 올바르지 않습니다.")
    if state["version"] != 1:
        raise ControllerSessionError("Controller session version은 1이어야 합니다.")
    _safe_session_id(str(state["session_id"]))
    _text(state["request"], "request")
    if state["status"] not in SESSION_STATUSES:
        raise ControllerSessionError("Controller session status가 올바르지 않습니다.")
    budget = state["budget"]
    if not isinstance(budget, dict):
        raise ControllerSessionError("Controller session budget이 없습니다.")
    if budget.get("max_actions") != MAX_ACTIONS or budget.get("max_method_changes") != MAX_METHOD_CHANGES:
        raise ControllerSessionError("Controller session budget 상수가 올바르지 않습니다.")
    used_actions = budget.get("used_actions")
    used_changes = budget.get("used_method_changes")
    if not isinstance(used_actions, int) or not 0 <= used_actions <= MAX_ACTIONS:
        raise ControllerSessionError("used_actions가 올바르지 않습니다.")
    if not isinstance(used_changes, int) or not 0 <= used_changes <= MAX_METHOD_CHANGES:
        raise ControllerSessionError("used_method_changes가 올바르지 않습니다.")
    actions = state["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        raise ControllerSessionError("Controller session actions가 올바르지 않습니다.")
    received = sum(1 for item in actions if item.get("status") == "received")
    if received != used_actions:
        raise ControllerSessionError("used_actions와 수신된 action 수가 일치하지 않습니다.")
    if state["status"] == "awaiting_execution" and not isinstance(state["current_action"], dict):
        raise ControllerSessionError("실행 대기 상태에는 current_action이 필요합니다.")
    if state["status"] != "awaiting_execution" and state["current_action"] is not None:
        raise ControllerSessionError("실행 대기 외 상태에는 current_action이 없어야 합니다.")
    if state["status"] == "awaiting_user_input" and not state["awaiting_user_question"]:
        raise ControllerSessionError("사용자 입력 대기 상태에는 질문이 필요합니다.")


def create_session(
    request: str,
    *,
    context: str = "",
    route_hint: str = "",
    output_root: Path,
    session_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    cleaned_request = _text(request, "사용자 요청")
    route = infer_route(cleaned_request, route_hint)
    chosen_id = session_id or (
        "manual-controller-"
        + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    session_dir = _session_dir(output_root, chosen_id)
    if session_dir.exists():
        raise ControllerSessionError(f"이미 존재하는 session_id입니다: {chosen_id}")
    created = _now()
    state: dict[str, Any] = {
        "version": 1,
        "session_id": chosen_id,
        "created_at": created,
        "updated_at": created,
        "request": cleaned_request,
        "context": str(context or "").strip(),
        "goal": _goal(cleaned_request, str(context or ""), route),
        "status": "awaiting_execution",
        "budget": {
            "max_actions": MAX_ACTIONS,
            "used_actions": 0,
            "max_method_changes": MAX_METHOD_CHANGES,
            "used_method_changes": 0,
        },
        "verified_findings": [],
        "unresolved": [],
        "actions": [],
        "current_action": None,
        "awaiting_user_question": None,
        "best_answer": "",
        "final_answer": "",
        "limitations": [],
    }
    action = _build_action(
        state,
        route=route,
        objective=_initial_objective(route, cleaned_request),
        reason="사용자 요청에 필요한 가장 작은 충분 초기 경로로 선택했습니다.",
        changed_dimension="none",
    )
    state["actions"].append(action)
    state["current_action"] = action
    _write_state(session_dir, state)
    return session_dir, state


def load_session(session_dir: Path) -> dict[str, Any]:
    path = session_dir.expanduser().resolve() / STATE_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"Controller session을 찾을 수 없습니다: {session_dir.name}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControllerSessionError("Controller session JSON이 손상됐습니다.") from exc
    if not isinstance(state, dict):
        raise ControllerSessionError("Controller session은 JSON 객체여야 합니다.")
    _validate_state(state)
    return state


def _strip_fence(value: str) -> str:
    return re.sub(r"\s*```$", "", re.sub(r"^```(?:json)?\s*", "", value.strip(), flags=re.I), flags=re.I).strip()


def _normalize_result(value: Any, packet: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, ["Action Result가 JSON 객체가 아닙니다."]
    warnings: list[str] = []
    result = dict(value)
    required = {
        "version",
        "session_id",
        "action_id",
        "route",
        "status",
        "completion",
        "evidence",
        "artifacts",
        "limitations",
        "continuation",
    }
    if set(result) != required:
        warnings.append("Action Result 필드가 계약과 정확히 일치하지 않습니다.")
    if result.get("version") != 1:
        warnings.append("지원하는 Action Result version이 아닙니다.")
    identity_mismatch = False
    if result.get("session_id") != packet["session_id"]:
        warnings.append("session_id가 현재 Controller session과 다릅니다.")
        identity_mismatch = True
    if result.get("action_id") != packet["action_id"]:
        warnings.append("action_id가 현재 action과 다릅니다.")
        identity_mismatch = True
    route = str(result.get("route") or "").upper()
    if route not in ROUTE_SET:
        warnings.append("route가 올바르지 않습니다.")
        route = packet["route"]
    if route != packet["route"]:
        warnings.append("Controller가 선택한 route와 다른 방법을 실행했습니다.")
        identity_mismatch = True
    result["route"] = route
    status = result.get("status")
    if status not in RESULT_STATUSES:
        warnings.append("status가 올바르지 않아 partial로 처리합니다.")
        status = "partial"
    completion = result.get("completion")
    if not isinstance(completion, dict):
        completion = {"met": False, "missing": ["완료 검증 정보 없음"]}
        warnings.append("completion 정보가 없습니다.")
    met = completion.get("met") is True
    missing = _unique_strings(completion.get("missing"))
    if status == "completed" and (not met or missing or identity_mismatch):
        warnings.append("완료 조건 또는 action identity가 맞지 않아 partial로 처리합니다.")
        status = "partial"
        met = False
        if identity_mismatch and "Controller가 지정한 action을 실행하지 않음" not in missing:
            missing.append("Controller가 지정한 action을 실행하지 않음")
    if status != "completed" and met:
        warnings.append("status와 completion.met이 충돌해 completion.met=false로 처리합니다.")
        met = False
    result["status"] = status
    result["completion"] = {"met": met, "missing": missing}
    result["evidence"] = [item for item in result.get("evidence", []) if isinstance(item, dict)]
    result["artifacts"] = [item for item in result.get("artifacts", []) if isinstance(item, dict)]
    result["limitations"] = _unique_strings(result.get("limitations"))
    continuation = result.get("continuation")
    if not isinstance(continuation, dict):
        continuation = {}
    suggested = continuation.get("suggested_route")
    if suggested is not None:
        suggested = str(suggested).upper()
        if suggested not in ROUTE_SET:
            warnings.append("continuation.suggested_route가 올바르지 않아 무시합니다.")
            suggested = None
    dimension = continuation.get("changed_dimension")
    if dimension not in CHANGED_DIMENSIONS:
        dimension = "none"
    result["continuation"] = {
        "objective": str(continuation.get("objective") or "").strip(),
        "suggested_route": suggested,
        "changed_dimension": dimension,
        "question": str(continuation.get("question") or "").strip(),
    }
    return result, warnings


def parse_action_result(
    raw_answer: str,
    *,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    raw = _text(raw_answer, "ChatGPT 답변")
    start = raw.rfind(START_MARKER)
    end = raw.rfind(END_MARKER)
    if start >= 0 and end > start:
        answer = raw[:start].strip()
        json_text = _strip_fence(raw[start + len(START_MARKER) : end])
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            return {
                "answer": answer or raw,
                "result": None,
                "warnings": [f"Action Result JSON을 읽지 못했습니다: {exc}"],
            }
        result, warnings = _normalize_result(parsed, packet)
        return {"answer": answer or raw, "result": result, "warnings": warnings}

    fenced = list(re.finditer(r"```json\s*([\s\S]*?)```", raw, re.I))
    for match in reversed(fenced):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        result, warnings = _normalize_result(parsed, packet)
        if result is not None and result.get("action_id") == packet["action_id"]:
            return {
                "answer": (raw[: match.start()] + raw[match.end() :]).strip() or raw,
                "result": result,
                "warnings": ["마커 없이 Action Result JSON을 찾아 가져왔습니다.", *warnings],
            }
    return {
        "answer": raw,
        "result": None,
        "warnings": ["Action Result가 없어 이 실행을 검증할 수 없습니다."],
    }


def _merge_evidence(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = [dict(item) for item in existing]
    seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in output}
    for item in incoming:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            output.append(dict(item))
            seen.add(key)
    return output


def _has_side_effects(result: Mapping[str, Any]) -> bool:
    return any(
        str(item.get("action") or "").lower() in {"created", "modified", "deleted"}
        for item in result.get("artifacts", [])
        if isinstance(item, dict)
    )


def _route_for_gap(
    missing: list[str],
    current_route: str,
    suggested_route: str | None,
) -> str:
    text = " ".join(missing).lower()
    if re.search(r"최신|현재|출처|근거|검색|웹|가격|재고|확인 시점|공식", text):
        return "RESEARCH"
    if re.search(r"기존|재사용|자산|도구|템플릿|스크립트 존재", text):
        return "REUSE"
    if re.search(r"코드|버그|테스트|패치|파일 수정|자동화", text):
        return "CODE"
    if re.search(r"프롬프트|지시문", text):
        return "PROMPT"
    if re.search(r"여러 단계|여러 파일|장기 상태|프로젝트", text):
        return "PROJECT"
    if suggested_route in ROUTE_SET:
        return str(suggested_route)
    return current_route


def _gap_objective(result: Mapping[str, Any], missing: list[str], route: str) -> str:
    suggested = str(result.get("continuation", {}).get("objective") or "").strip()
    if suggested:
        return suggested
    if missing:
        return f"남은 완료 조건을 해결한다: {missing[0]}"
    return f"{route} 경로에서 아직 검증되지 않은 완료 조건을 확인하고 최종 결과를 완성한다."


def _normalized_objective(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _same_route_dimension(route: str, proposed: str) -> str:
    if proposed in CHANGED_DIMENSIONS - {"none", "route"}:
        return proposed
    if route == "RESEARCH":
        return "information_source"
    if route in {"REUSE", "CODE"}:
        return "tool"
    return "interaction"


def _finish(state: dict[str, Any], status: str, answer: str, limitation: str | None = None) -> None:
    state["status"] = status
    state["current_action"] = None
    state["awaiting_user_question"] = None
    state["final_answer"] = answer or state["best_answer"]
    if limitation:
        state["limitations"] = _unique_strings([*state["limitations"], limitation])


def submit_action_result(session_dir: Path, raw_answer: str) -> dict[str, Any]:
    state = load_session(session_dir)
    if state["status"] != "awaiting_execution" or not isinstance(state["current_action"], dict):
        raise ControllerSessionError("현재 실행 결과를 받을 상태가 아닙니다.")
    current = state["current_action"]
    packet = current["packet"]
    imported = parse_action_result(raw_answer, packet=packet)
    answer = str(imported["answer"] or "").strip()
    result = imported["result"]
    current["status"] = "received"
    current["answer"] = answer
    current["result"] = result
    current["warnings"] = _unique_strings(imported["warnings"])
    for index, action in enumerate(state["actions"]):
        if action["packet"]["action_id"] == packet["action_id"]:
            state["actions"][index] = current
            break
    state["budget"]["used_actions"] += 1
    state["current_action"] = None

    if answer and (not state["best_answer"] or result and result.get("status") in {"completed", "partial"}):
        state["best_answer"] = answer
    state["limitations"] = _unique_strings([*state["limitations"], *current["warnings"]])

    if result is None:
        _finish(
            state,
            "partial",
            state["best_answer"],
            "구조화된 Action Result가 없어 Controller가 다음 행동을 안전하게 결정할 수 없습니다.",
        )
        _write_state(session_dir, state)
        return state

    state["verified_findings"] = _merge_evidence(
        state["verified_findings"], result["evidence"]
    )
    state["limitations"] = _unique_strings([*state["limitations"], *result["limitations"]])
    missing = _unique_strings(result["completion"]["missing"])
    state["unresolved"] = missing

    if result["status"] == "completed" and result["completion"]["met"] and answer:
        _finish(state, "completed", answer)
        _write_state(session_dir, state)
        return state

    if result["status"] == "needs_user_input":
        question = result["continuation"]["question"]
        if question:
            state["status"] = "awaiting_user_input"
            state["awaiting_user_question"] = question
            _write_state(session_dir, state)
            return state
        state["limitations"] = _unique_strings(
            [*state["limitations"], "사용자 입력이 필요하다고 했지만 질문이 없습니다."]
        )

    if result["status"] == "blocked":
        _finish(state, "blocked", state["best_answer"] or answer)
        _write_state(session_dir, state)
        return state

    if _has_side_effects(result):
        _finish(
            state,
            "partial",
            state["best_answer"] or answer,
            "실제 파일 부작용이 보고되어 자동으로 다음 방법을 실행하지 않았습니다.",
        )
        _write_state(session_dir, state)
        return state

    if state["budget"]["used_actions"] >= MAX_ACTIONS:
        _finish(
            state,
            "partial",
            state["best_answer"] or answer,
            "허용된 네 번의 AI action을 모두 사용했습니다.",
        )
        _write_state(session_dir, state)
        return state

    current_route = packet["route"]
    next_route = _route_for_gap(
        missing,
        current_route,
        result["continuation"]["suggested_route"],
    )
    changed_dimension = _same_route_dimension(
        current_route,
        result["continuation"]["changed_dimension"],
    )
    reason = "관찰된 미완료 조건을 새 증거 또는 다른 실행 방식으로 해소합니다."
    if next_route != current_route:
        if state["budget"]["used_method_changes"] >= MAX_METHOD_CHANGES:
            _finish(
                state,
                "partial",
                state["best_answer"] or answer,
                "이미 허용된 한 번의 material method change를 사용했습니다.",
            )
            _write_state(session_dir, state)
            return state
        state["budget"]["used_method_changes"] += 1
        changed_dimension = "route"
        reason = f"{current_route} 결과의 결손을 해소하기 위해 {next_route}로 한 번 방법을 변경합니다."

    objective = _gap_objective(result, missing, next_route)
    previous_objectives = {
        _normalized_objective(action["packet"]["objective"])
        for action in state["actions"]
    }
    if _normalized_objective(objective) in previous_objectives:
        _finish(
            state,
            "partial",
            state["best_answer"] or answer,
            "다음 action이 이미 실행한 objective를 반복하므로 중단했습니다.",
        )
        _write_state(session_dir, state)
        return state

    next_action = _build_action(
        state,
        route=next_route,
        objective=objective,
        reason=reason,
        changed_dimension=changed_dimension,
    )
    state["actions"].append(next_action)
    state["current_action"] = next_action
    state["status"] = "awaiting_execution"
    _write_state(session_dir, state)
    return state


def submit_user_input(session_dir: Path, answer: str) -> dict[str, Any]:
    state = load_session(session_dir)
    if state["status"] != "awaiting_user_input" or not state["awaiting_user_question"]:
        raise ControllerSessionError("현재 사용자 답변을 받을 상태가 아닙니다.")
    clean_answer = _text(answer, "사용자 답변")
    question = state["awaiting_user_question"]
    state["goal"]["fixed_constraints"] = _unique_strings(
        [
            *state["goal"]["fixed_constraints"],
            f"사용자 확인: {question} → {clean_answer}",
        ]
    )
    state["context"] = (
        state["context"].rstrip()
        + ("\n\n" if state["context"].strip() else "")
        + f"[사용자 확인]\n질문: {question}\n답변: {clean_answer}"
    )
    state["awaiting_user_question"] = None
    if state["budget"]["used_actions"] >= MAX_ACTIONS:
        _finish(
            state,
            "partial",
            state["best_answer"],
            "사용자 답변은 받았지만 AI action 한도가 남아 있지 않습니다.",
        )
        _write_state(session_dir, state)
        return state
    last_route = state["actions"][-1]["packet"]["route"]
    next_action = _build_action(
        state,
        route=last_route,
        objective="사용자 답변을 반영해 남은 완료 조건을 해소하고 최종 결과를 완성한다.",
        reason="결론을 바꾸는 누락 정보를 사용자가 직접 확인했습니다.",
        changed_dimension="interaction",
    )
    state["actions"].append(next_action)
    state["current_action"] = next_action
    state["status"] = "awaiting_execution"
    _write_state(session_dir, state)
    return state


def public_session(state: Mapping[str, Any]) -> dict[str, Any]:
    current = state.get("current_action")
    current_public = None
    if isinstance(current, dict):
        current_public = {
            "packet": current["packet"],
            "execution_prompt": current["execution_prompt"],
        }
    action_summaries = []
    for action in state["actions"]:
        packet = action["packet"]
        action_summaries.append(
            {
                "action_id": packet["action_id"],
                "action_number": packet["action_number"],
                "route": packet["route"],
                "objective": packet["objective"],
                "changed_dimension": packet["changed_dimension"],
                "status": action["status"],
                "result_status": action["result"].get("status") if isinstance(action.get("result"), dict) else None,
                "warnings": action.get("warnings", []),
            }
        )
    payload = {
        "version": state["version"],
        "session_id": state["session_id"],
        "created_at": state["created_at"],
        "updated_at": state["updated_at"],
        "request": state["request"],
        "goal": state["goal"],
        "status": state["status"],
        "budget": state["budget"],
        "verified_findings": state["verified_findings"],
        "unresolved": state["unresolved"],
        "actions": action_summaries,
        "current_action": current_public,
        "awaiting_user_question": state["awaiting_user_question"],
        "best_answer": state["best_answer"],
        "final_answer": state["final_answer"],
        "limitations": state["limitations"],
    }
    if state["status"] in {"completed", "partial", "blocked"}:
        last_route = state["actions"][-1]["packet"]["route"]
        payload["display_data"] = {
            "run_id": state["session_id"],
            "route": f"MANUAL CONTROLLER · {last_route}",
            "execution_status": state["status"],
            "result_markdown": state["final_answer"] or state["best_answer"],
            "evidence": [
                {
                    "source": item.get("source") or item.get("url") or "ChatGPT 수동 action",
                    "finding": item.get("finding") or item.get("summary") or json.dumps(item, ensure_ascii=False),
                }
                for item in state["verified_findings"]
            ],
            "artifacts": [],
            "limitations": state["limitations"],
            "workspace_receipt": None,
            "workspace_rollback": None,
        }
    return payload
