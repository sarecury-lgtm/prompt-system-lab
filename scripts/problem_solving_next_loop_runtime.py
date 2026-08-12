#!/usr/bin/env python3
"""Candidate-aware runtime wrapper for the PSOS next-loop experiment."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import problem_solving_candidate_update_runtime as CANDIDATE_UPDATE
import problem_solving_candidate_working_set as WORKING
import problem_solving_next_loop_experiment as LEGACY
import problem_solving_os as OS


DEFAULT_OUTPUT_ROOT = LEGACY.DEFAULT_OUTPUT_ROOT
STATE_FILENAME = LEGACY.STATE_FILENAME
NextLoopError = LEGACY.NextLoopError


def _latest_action(state: Mapping[str, Any]) -> str | None:
    latest = state.get("latest_correction")
    return latest.get("planned_action") if isinstance(latest, Mapping) else None


def _dynamic_execution_exists(state: Mapping[str, Any]) -> bool:
    dynamic = state.get("dynamic_state")
    return isinstance(dynamic, Mapping) and isinstance(
        dynamic.get("final_execution"), Mapping
    )


def _enrich_filter_escalation(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None,
) -> tuple[Path, dict[str, Any]]:
    """Merge research that began as FILTER but escalated because attributes were unknown."""

    if state.get("state") not in {"completed", "partial"}:
        return run_dir, copy.deepcopy(dict(state))
    if not _dynamic_execution_exists(state):
        return CANDIDATE_UPDATE._downgrade_update_failure(
            run_dir,
            state,
            engine=engine,
            error=CANDIDATE_UPDATE.CandidateUpdateError(
                "조건 필터의 부분 재조사 결과가 없습니다."
            ),
        )
    try:
        model_policy = policy or OS.load_model_policy()
        raw = CANDIDATE_UPDATE.DYNAMIC._invoke(
            engine,
            run_dir,
            name=f"next-candidate-update-{state['candidate_working_set']['revision']}",
            phase="next-candidate-update",
            route=None,
            profile=model_policy["router_fallback"],
            schema=CANDIDATE_UPDATE.SCHEMA_PATH,
            prompt=CANDIDATE_UPDATE.candidate_update_prompt(state),
        )
        update = CANDIDATE_UPDATE.validate_candidate_update(
            raw,
            working_set=state["candidate_working_set"],
        )
        if not update["updates"]:
            raise CANDIDATE_UPDATE.CandidateUpdateError(
                "조건 필터의 부분 재조사에서 후보 변화가 확인되지 않았습니다."
            )
        return CANDIDATE_UPDATE.apply_update_to_state(
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


def _reapply_changed_constraints(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    """Apply user constraint changes again after research supplies missing attributes."""

    result = copy.deepcopy(dict(state))
    latest = result.get("latest_correction")
    if not isinstance(latest, Mapping) or latest.get("type") != "constraint_change":
        return run_dir, result
    updates = latest.get("constraint_updates")
    if not isinstance(updates, Mapping) or not updates:
        return run_dir, result
    working = result.get("candidate_working_set")
    if not isinstance(working, Mapping):
        return run_dir, result

    filtered, stats = WORKING.apply_known_constraint_filter(
        working,
        updates,
        reason=str(latest.get("text") or "사용자 조건 변경"),
    )
    if stats["evaluated"] == 0:
        return run_dir, result

    if result.get("state") == "completed":
        result["state"] = "awaiting_correction"
    filtered["state"] = result.get("state", "awaiting_correction")
    filtered["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(filtered)

    history = result.get("candidate_update_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "revision": filtered["revision"],
            "action": "REAPPLY_FILTER",
            "stats": stats,
            "recommendation": result["state"],
            "reason": "부분 재조사로 채워진 속성에 사용자 조건을 다시 적용했습니다.",
        }
    )
    result["candidate_update_history"] = history
    CANDIDATE_UPDATE._persist_state(
        run_dir,
        result,
        engine=engine,
        note=(
            "부분 재조사로 확인된 후보 속성에 사용자 조건을 다시 적용했습니다. "
            f"평가 {stats['evaluated']}개, 제외 {stats['excluded']}개, "
            f"유지 {stats['kept']}개, 추가 확인 {stats['unknown']}개."
        ),
    )
    return run_dir, result


def _enforce_verified_completion(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    if result.get("state") != "completed":
        return run_dir, result
    if _latest_action(result) != "VERIFY_COMPLETION":
        return run_dir, result
    working = result.get("candidate_working_set")
    if not isinstance(working, Mapping):
        return run_dir, result
    kept = WORKING.kept_candidates(working)
    verified = [
        candidate
        for candidate in kept
        if candidate["status"] == "kept"
        and candidate["verification_status"] in {"partially_verified", "verified"}
    ]
    if verified:
        return run_dir, result
    mutable = copy.deepcopy(dict(working))
    mutable["state"] = "awaiting_correction"
    mutable["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(mutable)
    result["state"] = "awaiting_correction"
    CANDIDATE_UPDATE._persist_state(
        run_dir,
        result,
        engine=engine,
        note="최종 완료로 올릴 검증된 유지 후보가 아직 없습니다.",
    )
    return run_dir, result


def _enrich_and_guard(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None,
) -> tuple[Path, dict[str, Any]]:
    if _latest_action(state) == "FILTER" and _dynamic_execution_exists(state):
        resolved, enriched = _enrich_filter_escalation(
            run_dir,
            state,
            engine=engine,
            policy=policy,
        )
    else:
        resolved, enriched = CANDIDATE_UPDATE.enrich_dynamic_candidate_state(
            run_dir,
            state,
            engine=engine,
            policy=policy,
        )
    resolved, filtered = _reapply_changed_constraints(
        resolved,
        enriched,
        engine=engine,
    )
    return _enforce_verified_completion(resolved, filtered, engine=engine)


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
    run_dir, state = LEGACY.run_next_loop(
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
    return _enrich_and_guard(
        run_dir,
        state,
        engine=engine,
        policy=policy,
    )


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
    resolved, state = LEGACY.resume_next_loop(
        run_dir,
        engine=engine,
        correction=correction,
        correction_text=correction_text,
        answers=answers,
        policy=policy,
        max_changes=max_changes,
    )
    return _enrich_and_guard(
        resolved,
        state,
        engine=engine,
        policy=policy,
    )


def __getattr__(name: str) -> Any:
    return getattr(LEGACY, name)
