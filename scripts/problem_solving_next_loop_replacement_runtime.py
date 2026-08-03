#!/usr/bin/env python3
"""Guard candidate replacement corrections and empty next-loop dead ends."""

from __future__ import annotations

import copy
import json
import re
import threading
from pathlib import Path
from typing import Any, Mapping

import problem_solving_candidate_update_runtime as CANDIDATE_UPDATE
import problem_solving_candidate_working_set as WORKING
import problem_solving_next_loop_materialized_runtime as BASE
import problem_solving_os as OS


DEFAULT_OUTPUT_ROOT = BASE.DEFAULT_OUTPUT_ROOT
STATE_FILENAME = BASE.STATE_FILENAME
NextLoopError = BASE.NextLoopError
REPLACEMENT_MARKER = "[후보 교체]"
_PATCH_LOCK = threading.RLock()

_REMOVE_PATTERN = re.compile(
    r"(?:제외|제거|빼|없애|후보에서\s*내려|후보로\s*보지\s*마)",
    re.IGNORECASE,
)
_GENERATE_PATTERN = re.compile(
    r"(?:새(?:로운)?\s*(?:후보|candidate)|실제\s*(?:종목|상품|장소|업체|서비스|후보)|"
    r"후보\s*(?:\d+\s*[~～-]\s*\d+|몇|여러)?\s*(?:개)?\s*(?:뽑|찾|추리|만들|교체)|"
    r"대신\s*(?:뽑|찾|추리|만들)|교체)",
    re.IGNORECASE,
)
_SOURCE_PATTERN = re.compile(
    r"(?:기사|뉴스|reddit|레딧|캘린더|달력|검색\s*결과|목록|자료|정보원|페이지|"
    r"forbes|kiplinger|tradingview|nasdaq)",
    re.IGNORECASE,
)
_ALL_PATTERN = re.compile(r"(?:전부|모두|전체|기존\s*후보)", re.IGNORECASE)


def replacement_requested(text: str, working_set: Mapping[str, Any]) -> bool:
    """Return True only for explicit remove-and-regenerate corrections."""

    cleaned = str(text or "").strip()
    if not cleaned:
        return False
    if not (_REMOVE_PATTERN.search(cleaned) and _GENERATE_PATTERN.search(cleaned)):
        return False
    candidates = working_set.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return False
    return bool(_SOURCE_PATTERN.search(cleaned) or _ALL_PATTERN.search(cleaned))


def _source_like(candidate: Mapping[str, Any]) -> bool:
    if BASE._is_source_lead(candidate):
        return True
    name = str(candidate.get("name") or "")
    return bool(_SOURCE_PATTERN.search(name))


def replacement_target_ids(
    text: str,
    working_set: Mapping[str, Any],
) -> list[str]:
    candidates = [
        item
        for item in working_set.get("candidates", [])
        if isinstance(item, Mapping) and item.get("status") != "excluded"
    ]
    source_ids = [str(item.get("id")) for item in candidates if _source_like(item)]
    if source_ids:
        return source_ids
    if _ALL_PATTERN.search(text):
        return [str(item.get("id")) for item in candidates]
    return []


def build_replacement_correction(
    state: Mapping[str, Any],
    text: str,
) -> dict[str, Any]:
    working = WORKING.validate_working_set(dict(state["candidate_working_set"]))
    targets = replacement_target_ids(text, working)
    if not targets:
        raise NextLoopError("교체할 기존 후보를 찾지 못했습니다.")
    revision = working["revision"] + 1
    return WORKING.plan_correction(
        correction_id=f"correction-{revision:03d}",
        text=f"{REPLACEMENT_MARKER} {text.strip()}",
        correction_type="request_more",
        target_candidate_ids=targets,
        scope_terms=[
            "기존 정보원 후보를 제외하고 사용자 요청에 맞는 실제 선택 후보를 새로 생성",
            text.strip(),
        ],
    )


def _apply_replacement_correction(
    original: Any,
    working_set: Mapping[str, Any],
    correction: Mapping[str, Any],
) -> dict[str, Any]:
    result = original(working_set, correction)
    text = str(correction.get("text") or "")
    if not text.startswith(REPLACEMENT_MARKER):
        return result
    targets = set(correction.get("target_candidate_ids") or [])
    for candidate in result["candidates"]:
        if candidate["id"] in targets and candidate["status"] != "excluded":
            candidate["status"] = "excluded"
            candidate["exclusion_reason"] = (
                "정보원 자체가 아니라 실제 선택 대상을 새 후보로 만들기 위해 교체"
            )
    result["state"] = "researching"
    result["next_action"] = "PARTIAL_RESEARCH"
    return WORKING.validate_working_set(result)


def _resume_with_apply_patch(
    run_dir: Path,
    *,
    engine: OS.ProblemSolvingEngine,
    correction: Mapping[str, Any],
    answers: Mapping[str, str] | None,
    policy: dict[str, Any] | None,
    max_changes: int,
) -> tuple[Path, dict[str, Any]]:
    with _PATCH_LOCK:
        original = WORKING.apply_correction

        def patched(
            working_set: Mapping[str, Any],
            planned: Mapping[str, Any],
        ) -> dict[str, Any]:
            return _apply_replacement_correction(
                original,
                working_set,
                planned,
            )

        WORKING.apply_correction = patched
        try:
            return BASE.resume_next_loop(
                run_dir,
                engine=engine,
                correction=correction,
                answers=answers,
                policy=policy,
                max_changes=max_changes,
            )
        finally:
            WORKING.apply_correction = original


def _guard_empty_awaiting(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    if result.get("state") != "awaiting_correction":
        return run_dir, result
    working = result.get("candidate_working_set")
    if not isinstance(working, Mapping) or WORKING.kept_candidates(working):
        return run_dir, result

    mutable = copy.deepcopy(dict(working))
    mutable["state"] = "partial"
    mutable["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(mutable)
    result["state"] = "partial"
    CANDIDATE_UPDATE._persist_state(run_dir, result, engine=engine)
    note = (
        "새 후보를 만들지 못한 상태에서 교정 대기로 멈추지 않도록 미완료로 종료했습니다. "
        "기존 후보 제외는 반영됐지만 대체 후보 생성 근거가 부족합니다."
    )
    markdown = BASE._working_markdown(result["candidate_working_set"])
    (run_dir / "result.md").write_text(
        markdown.rstrip() + f"\n\n## 중단 이유\n\n{note}\n",
        encoding="utf-8",
    )
    return run_dir, result


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
    return _guard_empty_awaiting(run_dir, state, engine=engine)


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
    resolved = run_dir.expanduser().resolve()
    if correction is None and correction_text is not None:
        state_path = resolved / STATE_FILENAME
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            working = state.get("candidate_working_set")
            if isinstance(working, Mapping) and replacement_requested(
                correction_text,
                working,
            ):
                planned = build_replacement_correction(state, correction_text)
                run_dir, result = _resume_with_apply_patch(
                    resolved,
                    engine=engine,
                    correction=planned,
                    answers=answers,
                    policy=policy,
                    max_changes=max_changes,
                )
                return _guard_empty_awaiting(run_dir, result, engine=engine)

    run_dir, result = BASE.resume_next_loop(
        resolved,
        engine=engine,
        correction=correction,
        correction_text=correction_text,
        answers=answers,
        policy=policy,
        max_changes=max_changes,
    )
    return _guard_empty_awaiting(run_dir, result, engine=engine)


def __getattr__(name: str) -> Any:
    return getattr(BASE, name)
