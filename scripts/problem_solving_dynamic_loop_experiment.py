#!/usr/bin/env python3
"""Test a bounded dynamic next-action loop against the existing PSOS runtime."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as OS
import problem_solving_os_quality_runtime as QUALITY


# [CLAUDE_CONTEXT]
# Purpose: Prove whether independent terrain discovery plus bounded action changes
# improves outcomes before this behavior is integrated into the main PSOS UI.
# Key decisions: the open scan never sees the framer output; questions must map to
# observable consequences; only one material action change is allowed by default.

ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "dynamic-loop-experiments"
SCHEMA_DIR = ROOT / "schemas"
FRAMING_SCHEMA = SCHEMA_DIR / "problem-solving-dynamic-framing.schema.json"
SCAN_SCHEMA = SCHEMA_DIR / "problem-solving-dynamic-open-scan.schema.json"
QUESTION_SCHEMA = SCHEMA_DIR / "problem-solving-dynamic-question-gate.schema.json"
ACTION_SCHEMA = SCHEMA_DIR / "problem-solving-dynamic-action-plan.schema.json"
ASSESSMENT_SCHEMA = SCHEMA_DIR / "problem-solving-dynamic-assessment.schema.json"
MAX_REQUEST_CHARS = 10_000
MAX_QUESTIONS = 3
ROUTES = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT"}

AnswerProvider = Callable[[list[dict[str, Any]]], dict[str, str]]


class DynamicLoopError(ValueError):
    """Raised when a dynamic-loop stage violates its compact contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DynamicLoopError(f"{label}이 비어 있습니다.")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise DynamicLoopError(f"{label}이 문자열 배열이 아닙니다.")
    return [item.strip() for item in value]


def _object(payload: Any, top_key: str, fields: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {top_key}:
        raise DynamicLoopError(f"{top_key} 단계의 최상위 형식이 올바르지 않습니다.")
    value = payload[top_key]
    if not isinstance(value, dict) or set(value) != fields:
        raise DynamicLoopError(f"{top_key} 단계의 필드가 올바르지 않습니다.")
    return value


def validate_framing(payload: Any) -> dict[str, Any]:
    value = _object(
        payload,
        "framing",
        {"goal_hypothesis", "explicit_constraints", "unknowns", "external_landscape_matters"},
    )
    _text(value["goal_hypothesis"], "goal_hypothesis")
    _string_list(value["explicit_constraints"], "explicit_constraints")
    if not isinstance(value["external_landscape_matters"], bool):
        raise DynamicLoopError("external_landscape_matters는 boolean이어야 합니다.")
    if not isinstance(value["unknowns"], list):
        raise DynamicLoopError("unknowns가 배열이 아닙니다.")
    for item in value["unknowns"]:
        if not isinstance(item, dict) or set(item) != {
            "question_area",
            "why_it_may_change_outcome",
            "externally_discoverable",
        }:
            raise DynamicLoopError("unknowns 항목 형식이 올바르지 않습니다.")
        _text(item["question_area"], "unknown.question_area")
        _text(item["why_it_may_change_outcome"], "unknown.why_it_may_change_outcome")
        if not isinstance(item["externally_discoverable"], bool):
            raise DynamicLoopError("unknown.externally_discoverable은 boolean이어야 합니다.")
    return value


def validate_scan(payload: Any) -> dict[str, Any]:
    value = _object(
        payload,
        "scan",
        {"terrain_summary", "vocabulary", "adjacent_possibilities", "observations", "source_gaps"},
    )
    _text(value["terrain_summary"], "terrain_summary")
    _string_list(value["vocabulary"], "vocabulary")
    _string_list(value["source_gaps"], "source_gaps")
    limits = {
        "vocabulary": 12,
        "adjacent_possibilities": 6,
        "observations": 8,
        "source_gaps": 5,
    }
    for label, maximum in limits.items():
        if len(value[label]) > maximum:
            raise DynamicLoopError(f"{label}는 최대 {maximum}개여야 합니다.")
    for label, required in (
        ("adjacent_possibilities", {"name", "relation", "source"}),
        (
            "observations",
            {"finding", "source", "decision_relevance", "evidence_strength"},
        ),
    ):
        if not isinstance(value[label], list):
            raise DynamicLoopError(f"{label}가 배열이 아닙니다.")
        for item in value[label]:
            if not isinstance(item, dict) or set(item) != required:
                raise DynamicLoopError(f"{label} 항목 형식이 올바르지 않습니다.")
            for key, item_value in item.items():
                _text(item_value, f"{label}.{key}")
    return value


def validate_questions(payload: Any, *, top_key: str = "question_gate") -> dict[str, Any]:
    value = _object(payload, top_key, {"questions", "can_proceed_without_answers", "reason"})
    if not isinstance(value["questions"], list) or len(value["questions"]) > MAX_QUESTIONS:
        raise DynamicLoopError("질문은 최대 3개여야 합니다.")
    seen: set[str] = set()
    required = {"id", "text", "why_changes_decision", "observable_consequence", "options"}
    for item in value["questions"]:
        if not isinstance(item, dict) or set(item) != required:
            raise DynamicLoopError("질문 항목 형식이 올바르지 않습니다.")
        identifier = _text(item["id"], "question.id")
        if identifier in seen:
            raise DynamicLoopError("질문 ID가 중복되었습니다.")
        seen.add(identifier)
        for key in ("text", "why_changes_decision", "observable_consequence"):
            _text(item[key], f"question.{key}")
        _string_list(item["options"], "question.options")
    if not isinstance(value["can_proceed_without_answers"], bool):
        raise DynamicLoopError("can_proceed_without_answers는 boolean이어야 합니다.")
    _text(value["reason"], "question_gate.reason")
    return value


def validate_plan(payload: Any, *, has_previous: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    value = _object(
        payload,
        "plan",
        {"candidate_actions", "selected_action_id", "selection_reason", "difference_from_previous"},
    )
    actions = value["candidate_actions"]
    if not isinstance(actions, list) or not 2 <= len(actions) <= 4:
        raise DynamicLoopError("후보 행동은 2~4개여야 합니다.")
    required = {"id", "description", "method", "route", "information_target", "expected_value", "cost"}
    by_id: dict[str, dict[str, Any]] = {}
    for action in actions:
        if not isinstance(action, dict) or set(action) != required:
            raise DynamicLoopError("후보 행동 형식이 올바르지 않습니다.")
        identifier = _text(action["id"], "action.id")
        if identifier in by_id:
            raise DynamicLoopError("행동 ID가 중복되었습니다.")
        for key in required - {"id", "route"}:
            _text(action[key], f"action.{key}")
        if action["route"] not in ROUTES:
            raise DynamicLoopError("지원하지 않는 행동 route입니다.")
        by_id[identifier] = action
    selected_id = _text(value["selected_action_id"], "selected_action_id")
    if selected_id not in by_id:
        raise DynamicLoopError("선택된 행동이 후보 목록에 없습니다.")
    _text(value["selection_reason"], "selection_reason")
    difference = value["difference_from_previous"]
    if has_previous:
        _text(difference, "difference_from_previous")
    elif difference is not None:
        raise DynamicLoopError("첫 행동의 difference_from_previous는 null이어야 합니다.")
    return value, by_id[selected_id]


def validate_assessment(payload: Any) -> dict[str, Any]:
    fields = {
        "verdict",
        "reason",
        "meaningful_information",
        "discarded_information",
        "missing_information",
        "questions",
        "required_change",
    }
    value = _object(payload, "assessment", fields)
    if value["verdict"] not in {"STOP", "CHANGE", "ASK"}:
        raise DynamicLoopError("지원하지 않는 평가 verdict입니다.")
    _text(value["reason"], "assessment.reason")
    _string_list(value["missing_information"], "assessment.missing_information")
    if not isinstance(value["meaningful_information"], list):
        raise DynamicLoopError("meaningful_information이 배열이 아닙니다.")
    meaningful_fields = {"claim", "source", "decision_effect", "semantic_scope", "reliability"}
    for item in value["meaningful_information"]:
        if not isinstance(item, dict) or set(item) != meaningful_fields:
            raise DynamicLoopError("meaningful_information 항목 형식이 올바르지 않습니다.")
        for key, item_value in item.items():
            _text(item_value, f"meaningful_information.{key}")
    if not isinstance(value["discarded_information"], list):
        raise DynamicLoopError("discarded_information이 배열이 아닙니다.")
    for item in value["discarded_information"]:
        if not isinstance(item, dict) or set(item) != {"claim", "why_not_meaningful"}:
            raise DynamicLoopError("discarded_information 항목 형식이 올바르지 않습니다.")
        _text(item["claim"], "discarded.claim")
        _text(item["why_not_meaningful"], "discarded.why")
    questions_payload = {
        "question_gate": {
            "questions": value["questions"],
            "can_proceed_without_answers": False,
            "reason": value["reason"],
        }
    }
    validate_questions(questions_payload)
    change = value["required_change"]
    if change is not None:
        if not isinstance(change, dict) or set(change) != {"dimension", "instruction"}:
            raise DynamicLoopError("required_change 형식이 올바르지 않습니다.")
        if change["dimension"] not in {"source", "tool", "target", "method", "verification"}:
            raise DynamicLoopError("required_change.dimension이 올바르지 않습니다.")
        _text(change["instruction"], "required_change.instruction")
    if value["verdict"] == "CHANGE" and change is None:
        raise DynamicLoopError("CHANGE 평가에는 required_change가 필요합니다.")
    if value["verdict"] == "ASK" and not value["questions"]:
        raise DynamicLoopError("ASK 평가에는 질문이 필요합니다.")
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _invoke(
    engine: OS.ProblemSolvingEngine,
    run_dir: Path,
    *,
    name: str,
    phase: str,
    route: str | None,
    profile: OS.ModelProfile,
    schema: Path,
    prompt: str,
) -> dict[str, Any]:
    invocation = OS.InvocationSpec(
        name=name,
        phase=phase,
        route=route,
        profile=profile,
        schema_path=schema,
    )
    return engine.execute(prompt, run_dir, invocation)


def framing_prompt(request: str, context: str = "") -> str:
    return f"""사용자 요청의 본질을 임시로 파악하세요. 이것은 확정 해석이 아닙니다.

[원문]
{request}

[관련 대화 맥락]
{context or "(제공되지 않음)"}

규칙:
- 사용자가 명시한 조건과 AI가 추정한 선호를 분리합니다.
- 아직 모르는 내용을 임의의 취향으로 채우지 않습니다.
- 검색어, 상품 범주, 해결 절차나 최종 답을 만들지 않습니다.
- 현재 외부 선택지·사례·시장·도구를 알아야 결과가 좋아지는지만 external_landscape_matters로 표시합니다.
- unknown마다 외부 조사로 알 수 있는지 구분합니다.
"""


def scan_prompt(request: str) -> str:
    return f"""다른 AI의 목적 해석을 보지 않은 상태에서 사용자 원문 주변의 현실 지형을 넓게 탐색하세요.

[원문]
{request}

이 단계는 추천이나 결론을 쓰지 않습니다. 최대 6회의 넓은 검색으로:
- 실제 사람들이 쓰는 표현과 명칭
- 인접 선택지, 대체재, 다른 해결 경로
- 반복되는 현실 신호와 예상 밖의 가능성
- 후속 조사에 쓸 수 있는 직접 출처
를 찾습니다.

사용자 문구를 정확히 포함하는 결과만 찾지 마세요. 같은 목적을 다른 방식으로 만족하는 가능성을 포함하세요. 다만 관계를 설명할 수 없는 무관한 항목은 넣지 마세요. 출처 없는 일반 지식은 direct로 표시하지 마세요.

상한:
- vocabulary 12개
- adjacent_possibilities 6개
- observations 8개
- source_gaps 5개

지형을 드러내는 데 충분하면 즉시 멈추세요. 후보나 행동을 구분하지 못하는 일반 학술 배경, 모든 리뷰의 공통 불만, 장황한 시장 설명은 수집하지 마세요.
"""


def question_prompt(
    request: str,
    framing: Mapping[str, Any],
    scan: Mapping[str, Any],
    context: str = "",
) -> str:
    return f"""본격 실행 전에 사용자에게 질문할 가치가 있는지 판단하세요.

[원문]
{request}

[관련 대화 맥락]
{context or "(제공되지 않음)"}

[임시 본질 파악]
{_json(framing)}

[독립 열린 탐색]
{_json(scan)}

질문은 다음을 모두 만족할 때만 만드세요.
1. 답에 따라 검색 범위, 행동 또는 최종 선택이 실제로 달라진다.
2. 답을 관찰 가능한 조건이나 실행으로 연결할 수 있다.
3. 웹이나 제공 자료에서 직접 알아낼 수 없다.

잡내나 식감처럼 중요하지만 후보별로 신뢰성 있게 관찰할 수 없는 속성은, 답을 들어도 행동이 달라지지 않는다면 묻지 마세요. 질문은 최대 3개입니다. 질문 없이도 좋은 첫 행동이 가능하면 can_proceed_without_answers를 true로 두세요.

질문이 여러 개라면 다음 영향 순서로 우선합니다.
1. 사용 목적이나 사용 상황처럼 해결 대상의 종류 자체를 바꾸는 질문
2. 열린 탐색에서 발견된 인접 선택지를 허용할지 결정하는 질문
3. 예산·시간·수량 같은 실제 제약 질문

여러 취향을 하나의 강제 선택 프로필로 묶지 마세요. 배송지·계정·결제 같은 세부 사항은 대부분의 후보를 처음부터 제거하는 경우가 아니라면 최종 검증까지 미루세요.
"""


def action_prompt(
    request: str,
    framing: Mapping[str, Any],
    scan: Mapping[str, Any],
    answers: Mapping[str, str],
    history: list[Mapping[str, Any]],
    required_change: Mapping[str, Any] | None,
    context: str = "",
) -> str:
    return f"""현재 가장 정보 가치가 높은 다음 행동 하나를 선택하세요.

[사용자 원문]
{request}

[관련 대화 맥락]
{context or "(제공되지 않음)"}

[임시 본질 파악]
{_json(framing)}

[독립 열린 탐색]
{_json(scan)}

[사용자 답변]
{_json(answers)}

[이전 행동 기록]
{_json(history)}

[반드시 바꿔야 할 점]
{_json(required_change)}

규칙:
- 2~4개의 실질적으로 다른 행동 후보를 제안하고 하나만 선택합니다.
- 긴 전체 계획이 아니라 지금 실제로 실행할 한 행동이어야 합니다.
- 열린 탐색에서 발견된 가능성을 활용하되 특정 범주를 미리 정답으로 만들지 않습니다.
- 사용자의 답을 기다리는 것이 최선이면 이 단계가 아니라 질문 게이트에서 처리됐어야 합니다.
- 이전 행동이 있다면 source, tool, target, method, verification 중 평가자가 요구한 차원을 실제로 바꾸고 difference_from_previous에 설명합니다.
- CODE와 PROJECT도 이 실험에서는 파일을 바꾸지 않고 필요한 도구·설계·프로토타입을 결과 안에서만 제안합니다.
"""


def executor_prompt(
    request: str,
    framing: Mapping[str, Any],
    scan: Mapping[str, Any],
    answers: Mapping[str, str],
    action: Mapping[str, Any],
    history: list[Mapping[str, Any]],
    context: str = "",
) -> str:
    return f"""선택된 다음 행동을 지금 실제로 수행하세요. 계획을 다시 쓰지 마세요.

[사용자 원문]
{request}

[관련 대화 맥락]
{context or "(제공되지 않음)"}

[임시 본질 파악]
{_json(framing)}

[열린 탐색 원재료]
{_json(scan)}

[사용자 답변]
{_json(answers)}

[선택된 행동]
{_json(action)}

[이전 시도에서 얻은 정보]
{_json(history)}

규칙:
- 선택된 행동의 정보 목표를 달성합니다.
- 사실이라고 전부 판단에 넣지 않습니다. 중요하고, 관찰 가능하며, 후보나 행동을 구분하는 정보만 사용합니다.
- 인증이나 속성의 의미 범위를 넘겨 해석하지 않습니다. 예: 안전 인증은 맛의 증거가 아닙니다.
- 알 수 없는 속성을 장황한 추론으로 채우지 않습니다.
- 외부 사실을 조사했다면 직접 URL과 확인한 내용을 evidence에 연결합니다.
- 이 실험은 읽기 전용입니다. 파일 변경을 주장하지 마세요.
- 지금 확보한 정보로 사용자에게 직접 쓸 수 있는 답이 가능하면 result_markdown에 제시합니다. 아직 원재료만 확보했다면 무엇을 알았고 무엇이 남았는지 분명히 씁니다.
"""


def assessment_prompt(
    request: str,
    framing: Mapping[str, Any],
    answers: Mapping[str, str],
    action: Mapping[str, Any],
    execution: Mapping[str, Any],
    context: str = "",
) -> str:
    return f"""계획자의 자기설명을 승인하지 말고 실제 실행 결과만 보고 다음 상태를 판정하세요.

[사용자 원문]
{request}

[관련 대화 맥락]
{context or "(제공되지 않음)"}

[임시 목표와 명시 조건]
{_json(framing)}

[사용자 답변]
{_json(answers)}

[실행한 행동]
{_json(action)}

[실제 실행 결과]
{_json(execution)}

판정:
- STOP: 사용자가 바로 쓸 수 있는 결과가 있고 핵심 주장이 충분히 근거와 연결됨
- CHANGE: 아직 부족하며 source, tool, target, method, verification 중 하나를 실제로 바꾼 행동이 가치 있음
- ASK: 외부 조사보다 사용자 답 하나가 다음 결과를 크게 바꿈

정보는 중요성, 관찰 가능성, 구분력을 모두 가질 때 meaningful_information에 넣으세요. 사실이지만 판단을 바꾸지 않거나 의미 범위를 넘긴 정보는 discarded_information에 넣으세요. CHANGE라면 바꿀 차원과 구체적인 지시를 하나만 제시하세요.
"""


def empty_scan() -> dict[str, Any]:
    return {
        "terrain_summary": "현재 요청은 외부 지형 탐색 없이도 첫 행동을 선택할 수 있다.",
        "vocabulary": [],
        "adjacent_possibilities": [],
        "observations": [],
        "source_gaps": [],
    }


def _question_markdown(questions: list[Mapping[str, Any]]) -> str:
    lines = ["## 진행 전에 필요한 질문", ""]
    for index, question in enumerate(questions, 1):
        lines.append(f"{index}. {question['text']}")
        if question["options"]:
            lines.append("   - " + " / ".join(question["options"]))
    return "\n".join(lines).rstrip() + "\n"


def _save_state(run_dir: Path, state: dict[str, Any], engine: OS.ProblemSolvingEngine) -> None:
    prior_trace = state.get("engine_trace", [])
    current_trace = engine.trace()
    state["engine_trace"] = [*prior_trace, *current_trace] if prior_trace else current_trace
    OS.write_json(run_dir / "dynamic-state.json", state)
    final_execution = state.get("final_execution")
    result = (
        final_execution.get("result_markdown")
        if isinstance(final_execution, dict)
        else None
    )
    if state["state"] == "awaiting_user":
        result = _question_markdown(state["pending_questions"])
    elif state["state"] == "partial":
        assessment = state.get("final_assessment") or {}
        reason = assessment.get("reason", "완료 검증을 통과하지 못했습니다.")
        last_result = result if isinstance(result, str) and result.strip() else "(마지막 실행 결과 없음)"
        result = (
            "## 미완료 — 완료 검증 미통과\n\n"
            f"{reason}\n\n"
            "### 마지막 실행 결과 (최종 추천으로 사용하지 말 것)\n\n"
            f"{last_result}"
        )
    elif not isinstance(result, str) or not result.strip():
        result = state.get("final_assessment", {}).get("reason", "동적 실행 결과가 없습니다.")
    (run_dir / "result.md").write_text(str(result).rstrip() + "\n", encoding="utf-8")


def _execute_action_loop(
    run_dir: Path,
    state: dict[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    model_policy: dict[str, Any],
    max_changes: int,
) -> tuple[Path, dict[str, Any]]:
    cleaned = state["request"]
    frame = state["framing"]
    scan = state["open_scan"]
    context = str(state.get("context", ""))
    collected_answers = state["answers"]
    attempts = state["attempts"]
    reasoning_profile = model_policy["router_fallback"]
    capabilities = engine.capabilities()
    if not capabilities.ai_reasoning:
        raise DynamicLoopError(capabilities.detail or "AI 실행 capability가 없습니다.")

    history_for_model: list[dict[str, Any]] = []
    for attempt in attempts:
        assessment = attempt["assessment"]
        history_for_model.append(
            {
                "selected_action": attempt["selected_action"],
                "meaningful_information": assessment["meaningful_information"],
                "discarded_information": assessment["discarded_information"],
                "missing_information": assessment["missing_information"],
                "required_change": assessment["required_change"],
            }
        )

    changes_used = int(state.get("changes_used", 0))
    required_change: dict[str, Any] | None = None
    if attempts and attempts[-1]["assessment"]["verdict"] == "CHANGE":
        required_change = attempts[-1]["assessment"]["required_change"]
    previous_fingerprint: str | None = None
    if attempts:
        previous_action = attempts[-1]["selected_action"]
        previous_fingerprint = re.sub(
            r"\W+",
            " ",
            f"{previous_action['route']} {previous_action['method']} {previous_action['description']}".lower(),
        ).strip()

    while True:
        attempt_index = len(attempts)
        plan, action = validate_plan(
            _invoke(
                engine,
                run_dir,
                name=f"dynamic-action-{attempt_index + 1}",
                phase="dynamic-action",
                route=None,
                profile=reasoning_profile,
                schema=ACTION_SCHEMA,
                prompt=action_prompt(
                    cleaned,
                    frame,
                    scan,
                    collected_answers,
                    history_for_model,
                    required_change,
                    context,
                ),
            ),
            has_previous=bool(attempts),
        )
        fingerprint = re.sub(
            r"\W+",
            " ",
            f"{action['route']} {action['method']} {action['description']}".lower(),
        ).strip()
        if required_change is not None and fingerprint == previous_fingerprint:
            raise DynamicLoopError("CHANGE 이후 이전과 동일한 행동을 다시 선택했습니다.")
        previous_fingerprint = fingerprint

        route = action["route"]
        base_profile = model_policy["routes"][route]["primary"]
        profile = replace(base_profile, sandbox="read-only")
        raw_execution = _invoke(
            engine,
            run_dir,
            name=f"dynamic-executor-{attempt_index + 1}",
            phase="dynamic-executor",
            route=route,
            profile=profile,
            schema=OS.EXECUTION_SCHEMA_PATH,
            prompt=executor_prompt(
                cleaned,
                frame,
                scan,
                collected_answers,
                action,
                history_for_model,
                context,
            ),
        )
        execution = OS.validate_execution_output(raw_execution, route, profile, capabilities)
        assessment = validate_assessment(
            _invoke(
                engine,
                run_dir,
                name=f"dynamic-assessment-{attempt_index + 1}",
                phase="dynamic-assessment",
                route=None,
                profile=reasoning_profile,
                schema=ASSESSMENT_SCHEMA,
                prompt=assessment_prompt(
                    cleaned,
                    frame,
                    collected_answers,
                    action,
                    execution,
                    context,
                ),
            )
        )
        attempt = {
            "index": attempt_index + 1,
            "plan": plan,
            "selected_action": action,
            "execution": execution,
            "assessment": assessment,
        }
        attempts.append(attempt)
        state["final_execution"] = execution
        state["final_assessment"] = assessment
        state["pending_questions"] = []

        if assessment["verdict"] == "STOP":
            state["state"] = "completed"
            break
        if assessment["verdict"] == "ASK":
            state["state"] = "awaiting_user"
            state["pending_questions"] = assessment["questions"]
            break
        if changes_used >= max_changes:
            state["state"] = "partial"
            execution["status"] = "partial"
            limitation = "동적 루프의 허용된 방법 변경 횟수를 모두 사용함: " + assessment["reason"]
            if limitation not in execution["limitations"]:
                execution["limitations"].append(limitation)
            break

        changes_used += 1
        state["changes_used"] = changes_used
        required_change = assessment["required_change"]
        history_for_model.append(
            {
                "selected_action": action,
                "meaningful_information": assessment["meaningful_information"],
                "discarded_information": assessment["discarded_information"],
                "missing_information": assessment["missing_information"],
                "required_change": required_change,
            }
        )

    _save_state(run_dir, state, engine)
    return run_dir, state


def run_dynamic_loop(
    request: str,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None = None,
    answers: Mapping[str, str] | None = None,
    answer_provider: AnswerProvider | None = None,
    max_changes: int = 1,
    run_id: str | None = None,
    context: str = "",
) -> tuple[Path, dict[str, Any]]:
    cleaned = request.strip()
    if not cleaned or len(cleaned) > MAX_REQUEST_CHARS:
        raise DynamicLoopError("요청은 1~10,000자여야 합니다.")
    if max_changes not in {0, 1}:
        raise DynamicLoopError("최대 방법 변경 횟수는 0 또는 1이어야 합니다.")
    chosen_run_id = run_id or f"dynamic-{OS.make_run_id().removeprefix('psos-')}"
    if re.fullmatch(r"[A-Za-z0-9._-]+", chosen_run_id) is None:
        raise DynamicLoopError("run ID 형식이 올바르지 않습니다.")
    run_dir = output_root.expanduser().resolve() / chosen_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.txt").write_text(cleaned + "\n", encoding="utf-8")

    model_policy = policy or OS.load_model_policy()
    reasoning_profile = model_policy["router_fallback"]
    capabilities = engine.capabilities()
    if not capabilities.ai_reasoning:
        raise DynamicLoopError(capabilities.detail or "AI 실행 capability가 없습니다.")

    frame = validate_framing(
        _invoke(
            engine,
            run_dir,
            name="dynamic-framing",
            phase="dynamic-framing",
            route=None,
            profile=reasoning_profile,
            schema=FRAMING_SCHEMA,
            prompt=framing_prompt(cleaned, context),
        )
    )

    if frame["external_landscape_matters"]:
        research_profile = replace(
            model_policy["routes"]["RESEARCH"]["primary"],
            reasoning_effort="low",
        )
        scan = validate_scan(
            _invoke(
                engine,
                run_dir,
                name="dynamic-open-scan",
                phase="dynamic-open-scan",
                route="RESEARCH",
                profile=research_profile,
                schema=SCAN_SCHEMA,
                prompt=scan_prompt(cleaned),
            )
        )
    else:
        scan = empty_scan()

    gate = validate_questions(
        _invoke(
            engine,
            run_dir,
            name="dynamic-question-gate",
            phase="dynamic-question-gate",
            route=None,
            profile=reasoning_profile,
            schema=QUESTION_SCHEMA,
            prompt=question_prompt(cleaned, frame, scan, context),
        )
    )
    collected_answers = {
        str(key): str(value).strip()
        for key, value in (answers or {}).items()
        if str(value).strip()
    }
    missing = [item for item in gate["questions"] if item["id"] not in collected_answers]
    if missing and answer_provider is not None:
        provided = answer_provider(missing)
        for key, value in provided.items():
            if str(value).strip():
                collected_answers[str(key)] = str(value).strip()
        missing = [item for item in gate["questions"] if item["id"] not in collected_answers]

    state: dict[str, Any] = {
        "version": 1,
        "run_id": chosen_run_id,
        "state": "running",
        "request": cleaned,
        "context": context.strip(),
        "framing": frame,
        "open_scan": scan,
        "question_gate": gate,
        "answers": collected_answers,
        "attempts": [],
        "changes_used": 0,
        "pending_questions": [],
        "final_execution": None,
        "final_assessment": None,
        "engine_trace": [],
    }
    if missing and not gate["can_proceed_without_answers"]:
        state["state"] = "awaiting_user"
        state["pending_questions"] = missing
        _save_state(run_dir, state, engine)
        return run_dir, state
    return _execute_action_loop(
        run_dir,
        state,
        engine=engine,
        model_policy=model_policy,
        max_changes=max_changes,
    )


def resume_dynamic_loop(
    run_dir: Path,
    *,
    engine: OS.ProblemSolvingEngine,
    answers: Mapping[str, str] | None = None,
    answer_provider: AnswerProvider | None = None,
    policy: dict[str, Any] | None = None,
    max_changes: int = 1,
) -> tuple[Path, dict[str, Any]]:
    resolved = run_dir.expanduser().resolve()
    state_path = resolved / "dynamic-state.json"
    if not state_path.is_file():
        raise DynamicLoopError(f"재개할 상태 파일이 없습니다: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("state") != "awaiting_user":
        raise DynamicLoopError("사용자 답변을 기다리는 실행만 재개할 수 있습니다.")
    if max_changes not in {0, 1}:
        raise DynamicLoopError("최대 방법 변경 횟수는 0 또는 1이어야 합니다.")

    collected_answers = {
        str(key): str(value).strip()
        for key, value in state.get("answers", {}).items()
        if str(value).strip()
    }
    for key, value in (answers or {}).items():
        if str(value).strip():
            collected_answers[str(key)] = str(value).strip()
    missing = [
        item
        for item in state.get("pending_questions", [])
        if item["id"] not in collected_answers
    ]
    if missing and answer_provider is not None:
        provided = answer_provider(missing)
        for key, value in provided.items():
            if str(value).strip():
                collected_answers[str(key)] = str(value).strip()
        missing = [item for item in missing if item["id"] not in collected_answers]
    if missing:
        state["answers"] = collected_answers
        state["pending_questions"] = missing
        _save_state(resolved, state, engine)
        return resolved, state

    state["answers"] = collected_answers
    state["pending_questions"] = []
    state["state"] = "running"
    model_policy = policy or OS.load_model_policy()
    return _execute_action_loop(
        resolved,
        state,
        engine=engine,
        model_policy=model_policy,
        max_changes=max_changes,
    )


def console_answer_provider(questions: list[dict[str, Any]]) -> dict[str, str]:
    answers: dict[str, str] = {}
    print("\n실행 전에 답이 필요한 질문입니다.")
    for question in questions:
        print(f"\n- {question['text']}")
        if question["options"]:
            print("  선택 예: " + " / ".join(question["options"]))
        value = input("  답: ").strip()
        if value:
            answers[question["id"]] = value
    return answers


def load_answers(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DynamicLoopError("답변 JSON은 question ID와 답변의 객체여야 합니다.")
    return {str(key): str(value) for key, value in payload.items()}


def write_blind_comparison(
    output_root: Path,
    request: str,
    baseline_dir: Path,
    dynamic_dir: Path,
) -> Path:
    comparison_dir = output_root / f"comparison-{OS.make_run_id().removeprefix('psos-')}"
    comparison_dir.mkdir(parents=True, exist_ok=False)
    baseline = (baseline_dir / "result.md").read_text(encoding="utf-8")
    dynamic = (dynamic_dir / "result.md").read_text(encoding="utf-8")
    if secrets.randbelow(2) == 0:
        mapping = {"A": "baseline", "B": "dynamic"}
        contents = {"A": baseline, "B": dynamic}
    else:
        mapping = {"A": "dynamic", "B": "baseline"}
        contents = {"A": dynamic, "B": baseline}
    for label, content in contents.items():
        (comparison_dir / f"result-{label}.md").write_text(content.rstrip() + "\n", encoding="utf-8")
    OS.write_json(
        comparison_dir / "comparison.json",
        {
            "version": 1,
            "request": request,
            "result_a": "result-A.md",
            "result_b": "result-B.md",
            "baseline_run": str(baseline_dir),
            "dynamic_run": str(dynamic_dir),
        },
    )
    OS.write_json(comparison_dir / "blind-map.json", mapping)
    return comparison_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--request-file", type=Path)
    source.add_argument("--resume-run", type=Path)
    parser.add_argument("--context-file", type=Path)
    parser.add_argument("--answers-json", type=Path)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--max-changes", type=int, choices=(0, 1), default=1)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--compare-baseline", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    request = None
    if args.request is not None:
        request = args.request
    elif args.request_file is not None:
        request = args.request_file.expanduser().read_text(encoding="utf-8")
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    provider = None
    if not args.non_interactive and sys.stdin.isatty():
        provider = console_answer_provider
    engine = OS.CodexEngine(ROOT, enable_search=True)
    try:
        supplied_answers = load_answers(args.answers_json)
        if args.resume_run is not None:
            if args.run_id is not None:
                raise DynamicLoopError("재개할 때는 --run-id를 사용할 수 없습니다.")
            if args.context_file is not None:
                raise DynamicLoopError("재개할 때는 저장된 맥락을 사용하므로 --context-file을 사용할 수 없습니다.")
            dynamic_dir, state = resume_dynamic_loop(
                args.resume_run,
                engine=engine,
                answers=supplied_answers,
                answer_provider=provider,
                max_changes=args.max_changes,
            )
            request = state["request"]
        else:
            dynamic_dir, state = run_dynamic_loop(
                request,
                output_root=output_root,
                engine=engine,
                answers=supplied_answers,
                answer_provider=provider,
                max_changes=args.max_changes,
                run_id=args.run_id,
                context=(
                    args.context_file.expanduser().read_text(encoding="utf-8")
                    if args.context_file is not None
                    else ""
                ),
            )
        print(f"동적 실험 run: {dynamic_dir}")
        print(f"상태: {state['state']}")
        if state["state"] == "awaiting_user":
            print(_question_markdown(state["pending_questions"]))
            return 0
        if args.compare_baseline:
            if request is None:
                raise DynamicLoopError("비교할 원 요청을 찾을 수 없습니다.")
            baseline_engine = OS.CodexEngine(ROOT, enable_search=True)
            baseline_dir, _baseline = QUALITY.run_request(
                request,
                output_root=output_root / "baseline-runs",
                engine=baseline_engine,
            )
            comparison_dir = write_blind_comparison(
                output_root,
                request,
                baseline_dir,
                dynamic_dir,
            )
            print(f"블라인드 비교: {comparison_dir}")
        return 0
    except (DynamicLoopError, OS.ProblemSolvingError, OSError, json.JSONDecodeError) as exc:
        print(f"동적 실험 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
