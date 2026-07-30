#!/usr/bin/env python3
"""Route-preserving revision support for the PSOS manual bridge."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import problem_solving_manual as manual
import problem_solving_os as problem_os

REVISION_MODES = {"preserve_route", "reroute"}


def normalize_revision_mode(value: str | None) -> str:
    if value is None:
        return "preserve_route"
    if not isinstance(value, str):
        raise manual.ManualBridgeError("수정 방식이 올바르지 않습니다.")
    mode = value.strip().lower()
    if mode not in REVISION_MODES:
        raise manual.ManualBridgeError(
            "수정 방식은 preserve_route 또는 reroute 중 하나여야 합니다."
        )
    return mode


def copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def revised_route_payload(
    parent_payload: dict[str, Any],
    feedback: str,
) -> dict[str, Any]:
    payload = copy_json(parent_payload)
    route = payload["route"]
    ledger = payload["goal_ledger"]
    selected = route["selected_route"]
    reason = (
        f"기존 산출물 유형과 목적은 유지되므로 {selected} 경로에서 "
        "사용자 피드백을 직접 적용하는 것이 가장 작은 충분 수정이다."
    )
    constraint = "수정 피드백을 모두 반영한다: " + feedback[:3000]
    constraints = list(ledger.get("fixed_constraints") or [])
    if constraint not in constraints:
        constraints.append(constraint)
    ledger.update(
        {
            "current_goal_hypothesis": (
                "직전 결과를 같은 산출물 유형으로 유지하면서 사용자의 구체적인 "
                "수정 피드백을 반영한 전체본을 만든다."
            ),
            "fixed_constraints": constraints,
            "current_position": "완료된 결과와 구체적인 수정 피드백이 제공된 상태",
            "route_reason": reason,
            "current_step": (
                "직전 결과에서 피드백이 지적한 부분을 직접 교체·추가·삭제하고 "
                "수정된 전체 결과를 만든다."
            ),
            "why_this_step_matters": (
                "새 작업으로 다시 해석하면 이미 맞았던 구조까지 흔들릴 수 있으므로 "
                "기존 결과를 기준으로 필요한 부분만 정확히 고쳐야 한다."
            ),
            "completion_condition": (
                "피드백의 각 지적 사항이 실제 결과에 반영되고 수정된 전체본이 "
                "바로 사용할 수 있는 형태로 완성된다."
            ),
        }
    )
    route["route_reason"] = reason
    return problem_os.validate_route_output(payload)


def revision_context(
    parent_run_id: str,
    ledger_text: str,
    result: str,
    feedback: str,
    *,
    preserve_route: bool,
) -> str:
    mode_text = (
        "기존 경로를 유지하고 결과만 직접 수정한다."
        if preserve_route
        else "목표와 경로부터 다시 판단한다."
    )
    return f"""# 완료 결과 수정

이 실행은 기존 결과를 덮어쓰지 않는 revision run이다.
수정 방식: {mode_text}

## 원본 run
{parent_run_id}

## 직전 Goal Ledger
{ledger_text[:60_000]}

## 직전 결과
{result[:120_000]}

## 사용자의 정정 및 피드백
{feedback}

## 수정 원칙
- 원래 상위 목적과 이미 잘 된 부분은 보존한다.
- 사용자의 이번 피드백을 직전 결과보다 우선한다.
- 피드백을 요약하거나 평가만 하지 말고 실제 결과를 직접 수정한다.
- 교체 요청은 기존 문장을 교체하고, 추가 요청은 실제 규칙이나 항목으로 넣고, 삭제 요청은 결과에서 제거한다.
- 서로 충돌하지 않는 지적은 빠짐없이 모두 반영한다.
- 사용자에게는 수정된 전체 결과를 제공한다. 변경 제안이나 작업 예고만 반환하지 않는다.
- 피드백이 산출물 유형 자체를 바꾸는 경우에만 목표 재판단 방식을 사용한다.
"""


class ManualBridge(manual.ManualBridge):
    """Manual bridge with route-preserving and rerouted revision modes."""

    def revise(
        self,
        parent_run_id: str,
        feedback: str,
        research_mode: str | None = None,
        revision_mode: str | None = None,
    ) -> dict[str, Any]:
        feedback = feedback.strip()
        if not feedback:
            raise manual.ManualBridgeError(
                "무엇이 아쉬웠는지 또는 어떻게 바꿀지 적어 주세요."
            )
        if len(feedback) > manual.MAX_REQUEST_CHARS:
            raise manual.ManualBridgeError("수정 요청은 10,000자 이하여야 합니다.")
        mode_kind = normalize_revision_mode(revision_mode)
        if mode_kind == "reroute":
            session = super().revise(parent_run_id, feedback, research_mode)
            run_dir = self.run_dir(session["run_id"])
            state = manual.read_state(run_dir)
            state["revision_mode"] = mode_kind
            manual.write_json(
                run_dir / "revision.json",
                {
                    "parent_run_id": parent_run_id,
                    "feedback": feedback,
                    "research_mode": state.get("research_mode", "none"),
                    "revision_mode": mode_kind,
                    "created_at": state["created_at"],
                },
            )
            self.save(run_dir, state)
            return manual.public_state(state, run_dir)

        with self.lock:
            parent_dir = self.run_dir(parent_run_id)
            if not parent_dir.is_dir():
                raise manual.ManualBridgeError("수정할 원본 run을 찾을 수 없습니다.")
            parent = manual.read_state(parent_dir)
            if parent.get("state") != "completed":
                raise manual.ManualBridgeError("완료된 결과만 수정할 수 있습니다.")
            parent_payload = parent.get("route_payload")
            if not isinstance(parent_payload, dict):
                raise manual.ManualBridgeError(
                    "원본 run의 경로 정보를 찾을 수 없어 같은 경로 수정을 시작할 수 없습니다."
                )
            inherited_mode = parent.get(
                "research_mode",
                "standard" if parent.get("search_enabled") else "none",
            )
            research = manual.normalize_research_mode(
                parent.get("search_enabled", False),
                research_mode if research_mode is not None else inherited_mode,
            )
            request = parent.get("original_request") or parent["request"]
            try:
                ledger_text = (parent_dir / "goal_ledger.json").read_text(
                    encoding="utf-8"
                )
            except OSError:
                ledger_text = json.dumps(
                    parent_payload.get("goal_ledger", {}),
                    ensure_ascii=False,
                    indent=2,
                )
            try:
                result = (parent_dir / "result.md").read_text(encoding="utf-8")
            except OSError as exc:
                raise manual.ManualBridgeError(
                    f"직전 결과를 읽을 수 없습니다: {exc}"
                ) from exc

            run_id = problem_os.make_run_id()
            run_dir = self.run_dir(run_id)
            if run_dir.exists():
                raise manual.ManualBridgeError(f"이미 존재하는 run-id입니다: {run_id}")
            run_dir.mkdir(parents=True)
            (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
            context = revision_context(
                parent_run_id,
                ledger_text,
                result,
                feedback,
                preserve_route=True,
            )
            context_path = run_dir / "revision-context.md"
            context_path.write_text(context, encoding="utf-8")
            policy = problem_os.load_model_policy(self.policy_path)
            now = manual.utc_now()
            route_payload = revised_route_payload(parent_payload, feedback)
            state = {
                "version": 1,
                "run_id": run_id,
                "request": request,
                "original_request": request,
                "search_enabled": research != "none",
                "research_mode": research,
                "parent_run_id": parent_run_id,
                "revision_feedback": feedback,
                "revision_mode": mode_kind,
                "revision_context_path": str(context_path),
                "state": "created",
                "created_at": now,
                "updated_at": now,
                "route_payload": route_payload,
                "primary_execution": None,
                "prompt_compiler": None,
                "deep_research_reports": {},
                "stage": None,
                "history": [],
                "error": None,
                "model_policy": problem_os.public_model_policy(policy),
            }
            manual.write_json(
                run_dir / "revision.json",
                {
                    "parent_run_id": parent_run_id,
                    "feedback": feedback,
                    "research_mode": research,
                    "revision_mode": mode_kind,
                    "created_at": now,
                },
            )
            manual.write_json(
                run_dir / "goal_ledger.json",
                route_payload["goal_ledger"],
            )
            selected = route_payload["route"]["selected_route"]
            route = (
                route_payload["route"]["primary_route"]
                if selected == "HYBRID"
                else selected
            )
            self.prepare_executor(run_dir, state, route, "primary")
            self.save(run_dir, state)
            return manual.public_state(state, run_dir)

    def execution_prompt(
        self,
        run_dir: Path,
        state: dict[str, Any],
        route: str,
        primary: dict[str, Any] | None = None,
    ) -> str:
        base = super().execution_prompt(run_dir, state, route, primary)
        if state.get("revision_mode") != "preserve_route":
            return base
        context_path = state.get("revision_context_path")
        if not isinstance(context_path, str):
            return base
        try:
            context = Path(context_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise manual.ManualBridgeError(
                f"수정 문맥을 읽을 수 없습니다: {exc}"
            ) from exc
        return f"""{base.rstrip()}

[현재 단계: 같은 경로에서 완료 결과 직접 수정]
아래 직전 결과를 초안으로 사용한다.
사용자 피드백을 검토한 보고서가 아니라, 피드백이 실제로 적용된 수정 전체본을 만든다.
피드백에서 지적하지 않은 유효한 구조와 목적은 보존한다.
PROMPT 경로라면 수정된 최종 프롬프트 전체를 result_markdown에 넣는다.

{context}
"""

    def model_plan(
        self,
        state: dict[str, Any],
        routes: list[str],
    ) -> list[dict[str, Any]]:
        plan = super().model_plan(state, routes)
        if state.get("revision_mode") != "preserve_route":
            return plan
        selected = state["route_payload"]["route"]["selected_route"]
        return [
            {
                "stage": "revision_route_reuse",
                "route": selected,
                "model": "none",
                "reasoning_effort": "none",
                "web_search": False,
                "sandbox": "read-only",
                "transport": "local_parent_route_reuse",
            },
            *plan[1:],
        ]

    def finalize(
        self,
        run_dir: Path,
        state: dict[str, Any],
        execution: dict[str, Any],
    ) -> None:
        super().finalize(run_dir, state, execution)
        revision_mode = state.get("revision_mode")
        if not revision_mode:
            return
        route_path = run_dir / "route.json"
        record = json.loads(route_path.read_text(encoding="utf-8"))
        record.setdefault("run", {})["revision_mode"] = revision_mode
        record.setdefault("manual_bridge", {})["revision_mode"] = revision_mode
        manual.write_json(route_path, record)
