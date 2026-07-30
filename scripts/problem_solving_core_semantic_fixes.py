#!/usr/bin/env python3
"""Apply semantic correctness fixes to the transitional PSOS runtime.

The canonical runtime is intentionally left import-compatible while draft branches
exercise these stricter semantics. The patch is idempotent and changes only
router/execution validation, prompt-output isolation, router guidance, and HYBRID
result merging.
"""

from __future__ import annotations

import copy
from typing import Any


_ARTIFACT_ACTIONS = {"inspected", "generated_in_result", "created", "modified", "proposed"}
_EVIDENCE_KINDS = {"local", "web", "provided_context", "command_output"}
_PIPELINE_MARKERS = (
    "이 단계에서는",
    "라우팅 완료",
    "외곽 실행",
    "실행기로 전달",
    "다음 단계로 전달",
    "결과를 만들지",
)
_PROMPT_OUTPUT_START = "<!-- PSOS_PROMPT_START -->"
_PROMPT_OUTPUT_END = "<!-- PSOS_PROMPT_END -->"


def _nonempty(value: Any, field: str, error_type: type[Exception]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{field}가 비어 있습니다.")
    return value.strip()


def _string_list(
    value: Any,
    field: str,
    error_type: type[Exception],
    *,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise error_type(f"{field}는 문자열 배열이어야 합니다.")
    normalized: list[str] = []
    for item in value:
        text = _nonempty(item, field, error_type)
        if text not in normalized:
            normalized.append(text)
    if not allow_empty and not normalized:
        raise error_type(f"{field}는 비어 있을 수 없습니다.")
    return normalized


def _extract_prompt_output(value: Any, error_type: type[Exception]) -> str:
    raw = _nonempty(value, "execution.result_markdown", error_type)
    if raw.count(_PROMPT_OUTPUT_START) != 1 or raw.count(_PROMPT_OUTPUT_END) != 1:
        raise error_type(
            "PROMPT 완료 결과는 지정된 시작·종료 표식 사이에 최종 프롬프트 하나만 넣어야 합니다."
        )
    start_index = raw.index(_PROMPT_OUTPUT_START)
    end_index = raw.index(_PROMPT_OUTPUT_END)
    if end_index <= start_index:
        raise error_type("PROMPT 결과 표식의 순서가 올바르지 않습니다.")

    before = raw[:start_index].strip()
    prompt = raw[start_index + len(_PROMPT_OUTPUT_START) : end_index].strip()
    after = raw[end_index + len(_PROMPT_OUTPUT_END) :].strip()
    if before or after:
        raise error_type(
            "PROMPT 결과에는 최종 프롬프트 밖의 피드백·평가·개선점·선택 기록을 붙일 수 없습니다."
        )
    if not prompt:
        raise error_type("PROMPT 결과의 최종 프롬프트가 비어 있습니다.")
    return prompt


def _validate_route_output(os_module: Any, payload: Any) -> dict[str, Any]:
    error = os_module.ProblemSolvingError
    value = copy.deepcopy(payload)
    if not isinstance(value, dict) or set(value) != {"goal_ledger", "route"}:
        raise error("라우터 결과 최상위 필드가 스키마와 일치하지 않습니다.")
    ledger = value["goal_ledger"]
    route = value["route"]
    if not isinstance(ledger, dict) or set(ledger) != os_module.LEDGER_FIELDS:
        raise error("Goal Ledger 필드가 스키마와 일치하지 않습니다.")
    if not isinstance(route, dict) or set(route) != {
        "selected_route",
        "primary_route",
        "secondary_route",
        "route_reason",
    }:
        raise error("route 필드가 스키마와 일치하지 않습니다.")

    selected = route["selected_route"]
    if selected not in os_module.ROUTES:
        raise error(f"지원하지 않는 경로입니다: {selected}")
    primary = route["primary_route"]
    secondary = route["secondary_route"]
    if selected == "HYBRID":
        if primary not in os_module.SINGLE_ROUTES or secondary not in os_module.SINGLE_ROUTES:
            raise error("HYBRID는 주/보조 경로가 각각 하나 필요합니다.")
        if primary == secondary:
            raise error("HYBRID 주 경로와 보조 경로는 달라야 합니다.")
    elif primary is not None or secondary is not None:
        raise error("단일 경로의 primary_route와 secondary_route는 모두 null이어야 합니다.")

    if ledger["selected_route"] != selected or ledger["secondary_route"] != secondary:
        raise error("Goal Ledger와 route 선택이 일치하지 않습니다.")
    route_reason = _nonempty(route["route_reason"], "route.route_reason", error)
    _nonempty(ledger["route_reason"], "Goal Ledger route_reason", error)

    for field in (
        "parent_goal",
        "current_goal_hypothesis",
        "current_position",
        "current_step",
        "why_this_step_matters",
        "completion_condition",
    ):
        ledger[field] = _nonempty(ledger[field], f"Goal Ledger {field}", error)
    # route가 경로 선택의 정식 기록이다. Goal Ledger의 중복 필드는 표현 차이 때문에
    # 전체 실행을 막지 않고 동일한 기준값으로 정규화한다.
    ledger["route_reason"] = route_reason
    route["route_reason"] = route_reason
    ledger["fixed_constraints"] = _string_list(
        ledger["fixed_constraints"],
        "fixed_constraints",
        error,
        allow_empty=True,
    )
    uncertainties = _string_list(
        ledger["important_uncertainties"],
        "important_uncertainties",
        error,
        allow_empty=True,
    )
    if len(uncertainties) > 3:
        raise error("important_uncertainties는 최대 3개입니다.")
    ledger["important_uncertainties"] = uncertainties

    user_constraints = " ".join(ledger["fixed_constraints"])
    completion_contract = " ".join(
        [ledger["current_step"], ledger["completion_condition"]]
    )
    if any(marker in user_constraints for marker in _PIPELINE_MARKERS):
        raise error("라우터 내부 규칙이 사용자 고정 조건을 오염시켰습니다.")
    if any(marker in completion_contract for marker in _PIPELINE_MARKERS):
        raise error("라우팅 완료를 사용자 결과 완료 조건으로 바꿨습니다.")
    return value


def _validate_execution_consistency(
    os_module: Any,
    original: Any,
    payload: Any,
    route: str,
    profile: Any,
    capabilities: Any,
) -> dict[str, Any]:
    execution = original(payload, route, profile, capabilities)
    error = os_module.ProblemSolvingError

    if route == "PROMPT" and execution["status"] == "completed":
        execution["result_markdown"] = _extract_prompt_output(
            execution["result_markdown"],
            error,
        )

    needed = execution["needed_capability"]
    handoff = execution["handoff"]
    if needed is not None:
        needed = _nonempty(needed, "execution.needed_capability", error)
        execution["needed_capability"] = needed
    if handoff is not None:
        handoff = _nonempty(handoff, "execution.handoff", error)
        execution["handoff"] = handoff

    status = execution["status"]
    if status == "completed" and (needed is not None or handoff is not None):
        raise error("completed 결과에는 needed_capability나 handoff를 둘 수 없습니다.")
    if status == "blocked_by_capability" and (needed is None or handoff is None):
        raise error("blocked_by_capability에는 필요한 capability와 실행 가능한 handoff가 모두 필요합니다.")
    if status == "handoff" and handoff is None:
        raise error("handoff 상태에는 실제 다음 행동이 필요합니다.")
    if status == "partial" and needed is not None and handoff is None:
        raise error("partial 결과가 capability 부족을 기록하면 실행 가능한 handoff도 필요합니다.")

    for artifact in execution["artifacts"]:
        for field in ("path", "verification"):
            artifact[field] = _nonempty(
                artifact.get(field), f"artifact.{field}", error
            )
        if artifact.get("action") not in _ARTIFACT_ACTIONS:
            raise error("지원하지 않는 artifact.action입니다.")
    for evidence in execution["evidence"]:
        for field in ("source", "finding"):
            evidence[field] = _nonempty(
                evidence.get(field), f"evidence.{field}", error
            )
        if evidence.get("kind") not in _EVIDENCE_KINDS:
            raise error("지원하지 않는 evidence.kind입니다.")
    return execution


def _merge_executions(
    original: Any,
    primary_route: str,
    primary: dict[str, Any],
    secondary_route: str,
    secondary: dict[str, Any],
) -> dict[str, Any]:
    merged = original(primary_route, primary, secondary_route, secondary)
    merged["limitations"] = list(
        dict.fromkeys([*primary.get("limitations", []), *secondary.get("limitations", [])])
    )
    if primary.get("status") != "completed":
        merged["summary"] = " ".join(
            item
            for item in (primary.get("summary", ""), secondary.get("summary", ""))
            if item
        )
    if primary.get("needed_capability") and not merged.get("needed_capability"):
        merged["needed_capability"] = primary["needed_capability"]
    if primary.get("handoff") and not merged.get("handoff"):
        merged["handoff"] = primary["handoff"]
    return merged


def apply(os_module: Any) -> Any:
    """Patch one loaded ``problem_solving_os`` module exactly once."""

    if getattr(os_module, "_semantic_fixes_applied", False):
        return os_module

    original_build_router_prompt = os_module.build_router_prompt
    original_build_execution_prompt = os_module.build_execution_prompt
    original_validate_execution = os_module.validate_execution_output
    original_merge = os_module.merge_executions

    def build_router_prompt(*args: Any, **kwargs: Any) -> str:
        base = original_build_router_prompt(*args, **kwargs).rstrip()
        return base + """

[의미 일관성 규칙]
10. 사용자가 별도 고정 조건을 말하지 않았다면 fixed_constraints는 빈 배열로 둔다.
    일반적인 품질 원칙이나 파이프라인 규칙을 사용자 제약처럼 만들어 넣지 않는다.
11. 첨부 이미지·제공 문맥 자체를 분석하는 요청은 최신 외부 사실이 필요하지 않다면
    RESEARCH로 키우지 않는다.
12. HYBRID의 primary_route는 먼저 만들어야 하는 선행 결과이고 secondary_route는 그 결과를
    입력으로 받아 최종 사용자 산출물을 만드는 경로다. 단순히 두 경로가 관련 있다는 이유로
    HYBRID를 선택하거나 순서를 뒤집지 않는다.
13. Goal Ledger와 route의 route_reason은 가능하면 같은 짧은 문장으로 쓴다.
"""

    def build_execution_prompt(*args: Any, **kwargs: Any) -> str:
        route = kwargs.get("route")
        if route is None and args:
            route = args[0]
        base = original_build_execution_prompt(*args, **kwargs).rstrip()
        if route != "PROMPT":
            return base
        return base + f"""

[PROMPT 결과 전용 계약]
1. 내부에서 초안을 점검하고 필요하면 수정하되, 그 검토 과정은 출력하지 않는다.
2. execution.result_markdown에는 아래 시작·종료 표식 사이에 완성된 프롬프트 하나만 넣는다.
3. 표식 앞뒤에는 평가, 피드백, 개선점, 선택 기록, 사용법 설명, 요약을 붙이지 않는다.
4. 사용자가 명시적으로 프롬프트 평가를 요청하지 않았다면, 제공된 초안은 최종 프롬프트를
   만드는 재료로 사용하고 별도의 비평 대상으로 다루지 않는다.

{_PROMPT_OUTPUT_START}
[완성된 프롬프트 하나]
{_PROMPT_OUTPUT_END}
"""

    def validate_execution_output(
        payload: Any,
        route: str,
        profile: Any,
        capabilities: Any,
    ) -> dict[str, Any]:
        return _validate_execution_consistency(
            os_module,
            original_validate_execution,
            payload,
            route,
            profile,
            capabilities,
        )

    def merge_executions(
        primary_route: str,
        primary: dict[str, Any],
        secondary_route: str,
        secondary: dict[str, Any],
    ) -> dict[str, Any]:
        return _merge_executions(
            original_merge,
            primary_route,
            primary,
            secondary_route,
            secondary,
        )

    os_module.build_router_prompt = build_router_prompt
    os_module.build_execution_prompt = build_execution_prompt
    os_module.validate_route_output = lambda payload: _validate_route_output(os_module, payload)
    os_module.validate_execution_output = validate_execution_output
    os_module.merge_executions = merge_executions
    os_module._semantic_fixes_applied = True
    return os_module
