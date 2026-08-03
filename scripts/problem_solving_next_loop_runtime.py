#!/usr/bin/env python3
"""Candidate-aware runtime wrapper for the PSOS next-loop experiment."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import problem_solving_candidate_update_runtime as CANDIDATE_UPDATE
import problem_solving_candidate_working_set as WORKING
import problem_solving_next_loop_experiment as LEGACY
import problem_solving_os as OS


DEFAULT_OUTPUT_ROOT = LEGACY.DEFAULT_OUTPUT_ROOT
STATE_FILENAME = LEGACY.STATE_FILENAME
NextLoopError = LEGACY.NextLoopError


def _enforce_verified_completion(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    if result.get("state") != "completed":
        return run_dir, result
    latest = result.get("latest_correction")
    action = latest.get("planned_action") if isinstance(latest, Mapping) else None
    if action != "VERIFY_COMPLETION":
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
    resolved, enriched = CANDIDATE_UPDATE.enrich_dynamic_candidate_state(
        run_dir,
        state,
        engine=engine,
        policy=policy,
    )
    return _enforce_verified_completion(resolved, enriched, engine=engine)


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
