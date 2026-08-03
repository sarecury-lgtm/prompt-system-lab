#!/usr/bin/env python3
"""PSOS next-loop runtime that exposes decision candidates, not source pages."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import problem_solving_candidate_update_runtime as CANDIDATE_UPDATE
import problem_solving_candidate_working_set as WORKING
import problem_solving_next_loop_runtime as BASE
import problem_solving_os as OS


DEFAULT_OUTPUT_ROOT = BASE.DEFAULT_OUTPUT_ROOT
STATE_FILENAME = BASE.STATE_FILENAME
NextLoopError = BASE.NextLoopError


def _is_source_lead(candidate: Mapping[str, Any]) -> bool:
    evidence = candidate.get("evidence")
    return (
        candidate.get("verification_status") == "unverified"
        and not candidate.get("attributes")
        and isinstance(evidence, list)
        and bool(evidence)
        and all(item.get("kind") == "source-scout-lead" for item in evidence if isinstance(item, Mapping))
    )


def needs_decision_materialization(state: Mapping[str, Any]) -> bool:
    if state.get("state") != "awaiting_correction":
        return False
    working = state.get("candidate_working_set")
    if not isinstance(working, Mapping):
        return False
    candidates = working.get("candidates")
    return isinstance(candidates, list) and bool(candidates) and all(
        isinstance(item, Mapping) and _is_source_lead(item) for item in candidates
    )


def decision_materialization_prompt(state: Mapping[str, Any]) -> str:
    return f"""정보원 정찰 결과를 사용자가 실제로 비교할 선택 후보로 변환하세요.

[사용자 요청]
{state['request']}

[목표와 조건]
{json.dumps({
    'goal': state['candidate_working_set']['goal'],
    'constraints': state['candidate_working_set']['constraints'],
    'unresolved_requirements': state['candidate_working_set']['unresolved_requirements'],
}, ensure_ascii=False, indent=2)}

[정보원 정찰 결과]
{json.dumps(state['source_scout'], ensure_ascii=False, indent=2)}

중요한 구분:
- 기사, Reddit 글, 캘린더, 검색 페이지, 마켓 목록은 정보원이지 선택 후보가 아닙니다.
- 사용자가 투자 종목을 찾으면 실제 회사·ticker가 후보입니다.
- 상품을 찾으면 실제 판매 상품이 후보입니다.
- 여행·식당·서비스를 찾으면 실제 장소·업체·서비스가 후보입니다.
- 정보원 하나에 여러 실제 후보가 있으면 각각 별도 후보로 만듭니다.

규칙:
1. 정찰 결과가 직접 이름 붙이거나 뒷받침하는 실제 선택 대상만 updates에 넣습니다.
2. 모든 항목은 새 후보이므로 candidate_id는 빈 문자열입니다.
3. source_url은 해당 후보를 뒷받침하는 실제 정보원 URL을 사용합니다.
4. attributes에는 정찰 결과에서 실제로 확인된 값만 넣습니다.
5. 확인되지 않은 기대수익률·가격·성능을 만들지 않습니다.
6. 기사나 캘린더 자체를 후보로 반환하지 않습니다.
7. 실제 후보를 만들 근거가 부족하면 updates=[]로 두고 그 이유와 남은 조사 요구를 적습니다.
8. 실제 후보가 하나라도 있으면 completion_recommendation은 awaiting_correction입니다.
9. 후보는 최대 12개로 압축합니다.
"""


def _empty_working_set(working_set: Mapping[str, Any]) -> dict[str, Any]:
    empty = copy.deepcopy(dict(working_set))
    empty["candidates"] = []
    empty["state"] = "collecting"
    empty["next_action"] = None
    return WORKING.validate_working_set(empty)


def apply_materialized_update(
    run_dir: Path,
    state: Mapping[str, Any],
    update: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    empty = _empty_working_set(result["candidate_working_set"])
    materialized, stats = CANDIDATE_UPDATE.merge_candidate_update(empty, update)
    kept = WORKING.kept_candidates(materialized)

    if not kept:
        result["state"] = "partial"
        materialized["state"] = "partial"
        note = "정보원은 찾았지만 사용자가 비교할 실제 후보로 변환할 근거가 부족했습니다."
    else:
        result["state"] = "awaiting_correction"
        materialized["state"] = "awaiting_correction"
        note = (
            f"정찰 정보원을 숨기고 실제 선택 후보 {len(kept)}개를 작업대에 올렸습니다."
        )
    materialized["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(materialized)
    history = result.get("candidate_update_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "revision": materialized["revision"],
            "action": "INITIAL_MATERIALIZATION",
            "stats": stats,
            "recommendation": result["state"],
            "reason": update["reason"],
        }
    )
    result["candidate_update_history"] = history
    CANDIDATE_UPDATE._persist_state(
        run_dir,
        result,
        engine=engine,
        note=note,
    )
    return run_dir, result


def materialize_decision_candidates(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if not needs_decision_materialization(state):
        return run_dir, copy.deepcopy(dict(state))
    try:
        model_policy = policy or OS.load_model_policy()
        empty = _empty_working_set(state["candidate_working_set"])
        raw = CANDIDATE_UPDATE.DYNAMIC._invoke(
            engine,
            run_dir,
            name="next-initial-candidate-materialization",
            phase="next-initial-candidate-materialization",
            route=None,
            profile=model_policy["router_fallback"],
            schema=CANDIDATE_UPDATE.SCHEMA_PATH,
            prompt=decision_materialization_prompt(state),
        )
        update = CANDIDATE_UPDATE.validate_candidate_update(
            raw,
            working_set=empty,
        )
        return apply_materialized_update(
            run_dir,
            state,
            update,
            engine=engine,
        )
    except (
        CANDIDATE_UPDATE.CandidateUpdateError,
        WORKING.CandidateWorkingSetError,
        OS.ProblemSolvingError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        return CANDIDATE_UPDATE._downgrade_update_failure(
            run_dir,
            state,
            engine=engine,
            error=exc,
        )


def run_next_loop(
    request: str,
    *,
    engine: OS.ProblemSolvingEngine,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
    context: str = "",
    max_searches: int = 4,
    max_changes: int = 1,
    pause_for_correction: bool = True,
    policy: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    run_dir, state = BASE.run_next_loop(
        request,
        engine=engine,
        output_root=output_root,
        run_id=run_id,
        context=context,
        max_searches=max_searches,
        max_changes=max_changes,
        pause_for_correction=pause_for_correction,
        policy=policy,
    )
    if pause_for_correction:
        return materialize_decision_candidates(
            run_dir,
            state,
            engine=engine,
            policy=policy,
        )
    return run_dir, state


def resume_next_loop(
    run_dir: Path,
    *,
    engine: OS.ProblemSolvingEngine,
    correction: Mapping[str, Any] | None = None,
    correction_text: str | None = None,
    answers: Mapping[str, str] | None = None,
    policy: dict[str, Any] | None = None,
    max_changes: int = 1,
) -> tuple[Path, dict[str, Any]]:
    return BASE.resume_next_loop(
        run_dir,
        engine=engine,
        correction=correction,
        correction_text=correction_text,
        answers=answers,
        policy=policy,
        max_changes=max_changes,
    )


def __getattr__(name: str) -> Any:
    return getattr(BASE, name)
