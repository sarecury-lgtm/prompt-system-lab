#!/usr/bin/env python3
"""Run automatic PSOS requests through the same finalizing Job Packet contract as manual ChatGPT."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"
START_MARKER = "<!-- PSOS_RESULT_ENVELOPE_START -->"
END_MARKER = "<!-- PSOS_RESULT_ENVELOPE_END -->"
ROUTES = {"DIRECT", "RESEARCH", "DECISION", "CANDIDATE", "PROMPT", "WRITE"}

Runner = Callable[
    [str, bool, str, bool, list[str], dict[str, Any] | None],
    dict[str, Any],
]


ROUTE_PROCEDURES: dict[str, list[str]] = {
    "DIRECT": [
        "현재 대화와 제공 자료만으로 요청을 직접 해결한다.",
        "불필요한 중간 절차 없이 사용자가 바로 쓸 수 있는 결과를 완성한다.",
        "결론을 바꾸는 정보가 부족할 때만 질문한다.",
    ],
    "RESEARCH": [
        "최신 정보가 판단을 바꾸는 항목을 먼저 식별한다.",
        "웹 검색을 실제로 수행하고 변동 가능한 사실에 출처와 확인 시점을 연결한다.",
        "자료를 나열하지 말고 확인한 사실을 사용자의 질문에 대한 결론으로 연결한다.",
        "자료가 충돌하면 어떤 근거를 더 신뢰했는지 밝힌다.",
    ],
    "DECISION": [
        "특정된 대상과 사용자가 고민하는 행동을 정확히 식별한다.",
        "최신 정보, 제공 자료, 가장 큰 반대 근거와 실패 위험을 함께 확인한다.",
        "후보 목록이나 중간 작업대에서 멈추지 않고 요청에 맞는 행동 하나를 선택한다.",
        "판단이 바뀌는 조건과 실행 시 무효화 조건을 제시한다.",
    ],
    "CANDIDATE": [
        "정보원 페이지가 아니라 사용자가 실제로 선택하거나 행동할 수 있는 대상을 후보로 만든다.",
        "접근 불가, 조건 불일치, 검증 부족, 과도한 급등과 치명적 위험이 있는 후보를 내부에서 제거한다.",
        "남은 후보를 같은 기준으로 비교하고 필요한 항목을 추가 조사한다.",
        "검증된 소수 후보와 최종 1순위를 제시하거나 통과한 후보가 없다고 분명히 결론낸다.",
        "후보 작업대에서 멈추거나 사용자의 추가 교정을 기다리지 않는다.",
    ],
    "PROMPT": [
        "다른 AI가 실제 작업을 바로 수행할 수 있도록 목표, 고정 조건, 절차와 완료 조건을 통합한다.",
        "같은 의미를 반복하지 않고 복사해 바로 사용할 최종 프롬프트 하나를 완성한다.",
    ],
    "WRITE": [
        "사용자가 제공한 파일과 허용 범위를 기준으로 변경 목표를 식별한다.",
        "기존 기능을 보존하면서 필요한 변경만 설계하고 검증한다.",
        "적용 여부와 테스트 결과를 정직하게 구분한다.",
    ],
}

ROUTE_GATES: dict[str, list[str]] = {
    "DIRECT": [
        "질문에 직접 답했는가",
        "사용자의 표현과 고정 조건을 다른 문제로 바꾸지 않았는가",
        "설명만 있고 실제 결과가 없는 상태로 끝나지 않았는가",
    ],
    "RESEARCH": [
        "변동 가능한 핵심 주장에 출처와 확인 시점이 있는가",
        "출처가 실제 결론을 뒷받침하는가",
        "조사 목록이 아니라 사용자가 판단할 결론이 있는가",
    ],
    "DECISION": [
        "매수·대기·회피 또는 구매·보류처럼 행동 결론이 하나로 정해졌는가",
        "가장 큰 반대 근거와 하방 위험을 반영했는가",
        "판단이 바뀌는 조건이 구체적인가",
    ],
    "CANDIDATE": [
        "후보가 정보원이 아니라 실제 선택 대상인가",
        "모든 최종 후보가 최소 검증 기준과 사용자 조건을 통과했는가",
        "동일 기준 비교와 최종 순위 또는 무승자 결론이 있는가",
    ],
    "PROMPT": [
        "다른 AI가 추가 해석 없이 바로 실행할 수 있는가",
        "목표·고정 조건·절차·완료 조건이 보존됐는가",
    ],
    "WRITE": [
        "변경 대상과 범위가 구체적인가",
        "기존 기능 보존과 검증 절차가 포함됐는가",
    ],
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def infer_route(request: str, route_hint: str = "") -> str:
    hint = str(route_hint or "").strip().upper()
    if hint in ROUTES:
        return hint

    text = str(request or "").strip()
    write_target = re.search(
        r"(코드|파일|폴더|웹페이지|웹사이트|앱|프로젝트|저장소|레포|repository|html|css|javascript|typescript|python|스크립트)",
        text,
        re.I,
    )
    write_action = re.search(r"(만들|구현|수정|고쳐|추가|삭제|리팩터|저장|적용|배포|완성)", text, re.I)
    if write_target and write_action:
        return "WRITE"

    if re.search(r"(프롬프트|prompt)", text, re.I) and re.search(
        r"(만들|작성|설계|생성|짜|다듬|개선|최적화)", text, re.I
    ):
        return "PROMPT"

    decision_action = re.search(
        r"(살까|매수|진입|매도|팔까|대기|회피|보유|손절|구매할까|사도 될까|해야 할까|어떻게 해야)",
        text,
        re.I,
    )
    broad_search = re.search(r"(추천|후보|여러|몇 개|찾아|골라|비교|가장 좋은|1위)", text, re.I)
    if decision_action and not broad_search:
        return "DECISION"
    if broad_search:
        return "CANDIDATE"

    if re.search(
        r"(최신|오늘|현재|지금|가격|뉴스|법|규정|일정|패치|버전|검색|조사|찾아|확인|검증|판매 중|재고|실적)",
        text,
        re.I,
    ):
        return "RESEARCH"
    return "DIRECT"


def completion_rule(route: str) -> str:
    return {
        "DECISION": "사용자가 지금 취할 행동 하나, 그 근거와 가장 큰 위험, 판단이 바뀌는 조건이 제시되면 완료다.",
        "CANDIDATE": "검증 기준을 통과한 실제 후보만 비교되고 최종 1순위 또는 통과 후보 없음이 명확하면 완료다.",
        "RESEARCH": "최신 근거와 확인 시점이 결론에 연결되고 사용자가 바로 판단할 답이 제시되면 완료다.",
        "PROMPT": "다른 AI가 바로 실행할 수 있는 최종 프롬프트 하나가 완성되면 완료다.",
        "WRITE": "요청한 변경이 허용 범위에서 적용되고 검증 결과가 보고되면 완료다.",
    }.get(route, "사용자의 질문에 직접 답하고 바로 사용할 결과가 제시되면 완료다.")


def build_job_packet(request: str, *, route_hint: str = "", job_id: str = "") -> dict[str, Any]:
    clean_request = str(request or "").strip()
    if not clean_request:
        raise ValueError("사용자 요청이 비어 있습니다.")
    route = infer_route(clean_request, route_hint)
    return {
        "version": 1,
        "job_id": job_id or f"automatic-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "created_at": utc_now(),
        "execution_provider": "codex-automatic",
        "route_hint": route,
        "user_request": clean_request,
        "goal_ledger_task": {
            "derive": [
                "parent_goal",
                "current_goal",
                "fixed_constraints",
                "current_position",
                "completion_condition",
                "important_uncertainties",
            ],
            "preserve": [
                "사용자가 직접 명시한 목표와 조건",
                "대상, 주체, 시간 범위와 행동 주체",
                "현재 대화와 첨부 자료에서 이미 확인된 사실",
            ],
            "ask_only_when": "누락 정보가 결론을 크게 바꾸고 합리적인 기본값으로 진행할 수 없을 때만 질문한다.",
        },
        "execution_contract": {
            "procedure": [
                "사용자 요청에서 Goal Ledger를 내부적으로 구성한다.",
                "요청에 필요한 해결 경로와 도구를 선택한다.",
                *ROUTE_PROCEDURES[route],
                "완료 조건과 품질 게이트를 기준으로 결과를 자체 점검한다.",
                "사용자 답변을 먼저 제시하고 Result Envelope를 마지막에 반환한다.",
            ],
            "quality_gates": [
                "사용자 요청을 다른 문제로 바꾸지 않는다.",
                "검증하지 않은 사실을 확정적으로 만들지 않는다.",
                "중간 계획이나 후보 작업대가 아니라 실제 결과까지 완성한다.",
                *ROUTE_GATES[route],
            ],
            "completion_rule": completion_rule(route),
            "failure_rule": "완료 조건을 충족하지 못하면 가능한 결과와 부족한 항목을 분리해 partial 또는 blocked로 기록한다.",
        },
        "output_contract": {
            "answer_first": True,
            "envelope_required": True,
            "start_marker": START_MARKER,
            "end_marker": END_MARKER,
        },
    }


def envelope_example(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "job_id": packet["job_id"],
        "status": "completed",
        "route": packet["route_hint"],
        "goal": {
            "parent": "",
            "current": "",
            "constraints": [],
            "completion_condition": "",
        },
        "decision": {
            "conclusion": "",
            "action": "",
            "confidence": "medium",
            "change_conditions": [],
        },
        "completion": {"met": True, "missing": []},
        "evidence": [],
        "candidates": [],
        "artifacts": [],
        "continuation": {
            "preserve": [],
            "excluded_candidate_ids": [],
            "unresolved": [],
        },
    }


def build_execution_prompt(packet: Mapping[str, Any]) -> str:
    return (
        "당신은 아래 PSOS Job Packet을 실제로 실행하는 문제 해결 엔진이다. "
        "패킷을 설명하거나 평가하는 데서 멈추지 말고 사용자 요청을 끝까지 해결하라.\n\n"
        "[실행 규칙]\n"
        "1. goal_ledger_task에 따라 목표, 고정 조건, 현재 위치, 완료 조건과 불확실성을 내부적으로 정리한다.\n"
        "2. 내부 단계별 사고 과정은 노출하지 않는다.\n"
        "3. execution_contract의 절차와 품질 게이트를 적용해 실제 조사·분석·판단·작성 작업을 수행한다.\n"
        "4. 최신 정보가 필요하면 웹 검색을 실제로 사용하고 변동 가능한 핵심 사실에 출처와 확인 시점을 연결한다.\n"
        "5. 후보 작업대, 조사 계획, 추가 질문 목록에서 멈추지 말고 완료 조건까지 진행한다.\n"
        "6. 답변 첫 부분에는 사용자가 읽을 최종 결과만 쓴다. 결론을 앞에 두고 근거, 위험과 다음 행동을 필요한 만큼 붙인다.\n"
        "7. 마지막에는 지정된 두 마커 사이에 JSON Result Envelope 하나를 넣는다. 마커 뒤에는 아무것도 쓰지 않는다.\n\n"
        f"[PSOS Job Packet]\n{json.dumps(packet, ensure_ascii=False, indent=2)}\n\n"
        "[Result Envelope 형식 예시]\n"
        f"{START_MARKER}\n```json\n"
        f"{json.dumps(envelope_example(packet), ensure_ascii=False, indent=2)}\n"
        f"```\n{END_MARKER}"
    )


def _json_between_markers(text: str) -> tuple[str, dict[str, Any] | None, list[str]]:
    raw = str(text or "")
    start = raw.rfind(START_MARKER)
    end = raw.rfind(END_MARKER)
    if start < 0 or end < start:
        return raw.strip(), None, ["Result Envelope가 없어 자동 상태 검증을 생략했습니다."]

    answer = raw[:start].rstrip()
    envelope_text = raw[start + len(START_MARKER) : end].strip()
    envelope_text = re.sub(r"^```(?:json)?\s*", "", envelope_text, flags=re.I)
    envelope_text = re.sub(r"\s*```$", "", envelope_text)
    try:
        envelope = json.loads(envelope_text)
    except json.JSONDecodeError:
        return answer, None, ["Result Envelope JSON을 읽지 못해 답변만 표시합니다."]
    if not isinstance(envelope, dict):
        return answer, None, ["Result Envelope가 JSON 객체가 아니어서 답변만 표시합니다."]
    return answer, envelope, []


def _public_evidence(items: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return output
    for item in items:
        if not isinstance(item, Mapping):
            continue
        source = str(item.get("source") or item.get("url") or "").strip()
        finding = str(item.get("finding") or item.get("claim") or item.get("summary") or "").strip()
        if source or finding:
            output.append({"source": source or "PSOS Job Packet", "finding": finding or "근거 확인"})
    return output


def _public_artifacts(items: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return output
    for item in items:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path") or "").strip()
        if path:
            output.append({"path": path, "action": str(item.get("action") or item.get("kind") or "reported")})
    return output


def run_job_packet_request(
    request: str,
    search_enabled: bool,
    run_id: str,
    workspace_write: bool,
    _allowed_write_paths: list[str],
    _approval: dict[str, Any] | None,
    *,
    quality_runner: Runner | None = None,
    runs_root: Path = RUNS_ROOT,
) -> dict[str, Any]:
    if workspace_write:
        raise ValueError("Job Packet 최종 실행은 읽기 전용입니다. 파일 변경은 기존 승인 경로를 사용하세요.")
    if quality_runner is None:
        import problem_solving_quality_web as quality_web

        quality_runner = quality_web.run_quality_request

    packet = build_job_packet(request, job_id=run_id)
    route = str(packet["route_hint"])
    prompt = build_execution_prompt(packet)
    force_search = route in {"RESEARCH", "DECISION", "CANDIDATE"}
    result = quality_runner(prompt, bool(search_enabled or force_search), run_id, False, [], None)
    answer, envelope, warnings = _json_between_markers(str(result.get("result_markdown") or ""))

    run_dir = runs_root / run_id
    if run_dir.is_dir():
        (run_dir / "automatic_job_packet.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (run_dir / "automatic_job_packet_prompt.txt").write_text(prompt + "\n", encoding="utf-8")
        (run_dir / "automatic_original_request.txt").write_text(request.strip() + "\n", encoding="utf-8")

    evidence = list(result.get("evidence") or [])
    artifacts = list(result.get("artifacts") or [])
    limitations = list(result.get("limitations") or [])
    if envelope:
        evidence = _public_evidence(envelope.get("evidence")) or evidence
        artifacts.extend(_public_artifacts(envelope.get("artifacts")))
        completion = envelope.get("completion")
        if isinstance(completion, Mapping):
            limitations.extend(str(item) for item in completion.get("missing", []) if str(item).strip())
        continuation = envelope.get("continuation")
        if isinstance(continuation, Mapping):
            limitations.extend(str(item) for item in continuation.get("unresolved", []) if str(item).strip())
    limitations.extend(warnings)
    artifacts.extend(
        [
            {"path": "automatic_job_packet.json", "action": "job_packet"},
            {"path": "automatic_job_packet_prompt.txt", "action": "executor_input"},
            {"path": "automatic_original_request.txt", "action": "original_request"},
        ]
    )

    status = str(envelope.get("status")) if isinstance(envelope, Mapping) else str(result.get("execution_status") or "completed")
    return {
        **result,
        "route": f"JOB_PACKET · {route}",
        "execution_status": status,
        "result_markdown": answer or str(result.get("result_markdown") or "").strip(),
        "evidence": evidence,
        "artifacts": artifacts,
        "limitations": list(dict.fromkeys(item for item in limitations if str(item).strip())),
    }


def install(web: Any) -> None:
    """Add execution_mode=job_packet to the existing combined web job manager."""

    manager_class = web.CombinedJobManager
    if getattr(manager_class, "_job_packet_installed", False):
        return

    original_init = manager_class.__init__
    original_submit = manager_class.submit
    original_active_run_ids = manager_class.active_run_ids
    original_shutdown = manager_class.shutdown

    def patched_init(self: Any, *args: Any, job_packet_runner: Runner = run_job_packet_request, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self._job_packet = web.base_web.JobManager(runner=job_packet_runner)

    def patched_submit(
        self: Any,
        request: str,
        search_enabled: bool,
        *,
        workspace_write: bool = False,
        allowed_write_paths: list[str] | None = None,
        approval: dict[str, Any] | None = None,
        execution_mode: str = "quality",
    ) -> dict[str, Any]:
        if execution_mode == "job_packet":
            if workspace_write:
                raise ValueError("Job Packet 최종 실행에서는 파일 변경을 사용할 수 없습니다.")
            route = infer_route(request)
            use_search = bool(search_enabled or route in {"RESEARCH", "DECISION", "CANDIDATE"})
            return self._remember(self._job_packet.submit(request, use_search), self._job_packet)
        return original_submit(
            self,
            request,
            search_enabled,
            workspace_write=workspace_write,
            allowed_write_paths=allowed_write_paths,
            approval=approval,
            execution_mode=execution_mode,
        )

    def patched_active_run_ids(self: Any) -> set[str]:
        return original_active_run_ids(self) | self._job_packet.active_run_ids()

    def patched_shutdown(self: Any) -> None:
        self._job_packet.shutdown()
        original_shutdown(self)

    manager_class.__init__ = patched_init
    manager_class.submit = patched_submit
    manager_class.active_run_ids = patched_active_run_ids
    manager_class.shutdown = patched_shutdown
    manager_class._job_packet_installed = True
