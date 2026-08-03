#!/usr/bin/env python3
"""Candidate-aware runtime wrapper for the PSOS next-loop experiment."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import problem_solving_candidate_update_runtime as CANDIDATE_UPDATE
import problem_solving_next_loop_experiment as LEGACY
import problem_solving_os as OS


DEFAULT_OUTPUT_ROOT = LEGACY.DEFAULT_OUTPUT_ROOT
STATE_FILENAME = LEGACY.STATE_FILENAME
NextLoopError = LEGACY.NextLoopError


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
    return CANDIDATE_UPDATE.enrich_dynamic_candidate_state(
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
    return CANDIDATE_UPDATE.enrich_dynamic_candidate_state(
        resolved,
        state,
        engine=engine,
        policy=policy,
    )


def __getattr__(name: str) -> Any:
    return getattr(LEGACY, name)
