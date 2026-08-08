#!/usr/bin/env python3
"""Connect source scouting, candidate correction, and the bounded dynamic loop."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_candidate_working_set as WORKING
import problem_solving_dynamic_loop_experiment as DYNAMIC
import problem_solving_os as OS
import problem_solving_source_scout_experiment as SCOUT


ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "next-loop-experiments"
CORRECTION_SCHEMA = ROOT / "schemas" / "problem-solving-candidate-correction.schema.json"
STATE_FILENAME = "next-loop-state.json"
MAX_REQUEST_CHARS = 10_000


class NextLoopError(ValueError):
    """Raised when the next-loop cannot safely continue."""


def _clean_request(request: str) -> str:
    cleaned = request.strip()
    if not cleaned or len(cleaned) > MAX_REQUEST_CHARS:
        raise NextLoopError("요청은 1~10,000자여야 합니다.")
    return cleaned


def _run_id(value: str | None) -> str:
    chosen = value or f"next-{OS.make_run_id().removeprefix('psos-')}"
    if re.fullmatch(r"[A-Za-z0-9._-]+", chosen) is None:
        raise NextLoopError("run ID 형식이 올바르지 않습니다.")
    return chosen


def _engine_trace(state: Mapping[str, Any], engine: OS.ProblemSolvingEngine) -> list[dict[str, Any]]:
    prior = state.get("engine_trace", [])
    current = engine.trace()
    return [*prior, *current] if prior else current


def _working_markdown(working_set: Mapping[str, Any]) -> str:
    candidates = working_set["candidates"]
    kept = [item for item in candidates if item["status"] != "excluded"]
    lines = [
        "# 후보 작업대",
        "",
        f"- 상태: **{working_set['state']}**",
        f"- 조사 전략: {working_set['source_plan']['strategy']}",
        f"- 남은 후보: {len(kept)}개 / 전체 {len(candidates)}개",
        "",
    ]
    if kept:
        lines.extend(["| ID | 후보 | 정보원 | 상태 |", "|---|---|---|---|"])
        for item in kept:
            name = item["name"].replace("|", "/")
            lines.append(
                f"| {item['id']} | [{name}]({item['source_url']}) | "
                f"{item['source_family']} | {item['status']} |"
            )
    else:
        lines.append("현재 조건에서 남은 후보가 없습니다.")
    excluded = [item for item in candidates if item["status"] == "excluded"]
    if excluded:
        lines.extend(["", "## 제외된 후보", ""])
        lines.extend(
            f"- {item['id']} {item['name']}: {item['exclusion_reason']}" for item in excluded
        )
    lines.extend(
        [
            "",
            "짧게 교정할 수 있습니다. 예: `candidate-002 제외`, `전부 비쌈`, "
            "`100g당 1000원 이하 더 찾아`, `candidate-001 현재 판매 여부 확인`.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _save_state(run_dir: Path, state: dict[str, Any], engine: OS.ProblemSolvingEngine) -> None:
    state["engine_trace"] = _engine_trace(state, engine)
    OS.write_json(run_dir / STATE_FILENAME, state)
    if state["state"] == "awaiting_correction":
        result = _working_markdown(state["candidate_working_set"])
        (run_dir / "result.md").write_text(result, encoding="utf-8")
    elif state["state"] == "awaiting_information":
        questions = state.get("pending_questions", [])
        lines = ["## 진행 전에 필요한 질문", ""]
        for index, question in enumerate(questions, 1):
            lines.append(f"{index}. {question['text']}")
        (run_dir / "result.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def correction_prompt(text: str, working_set: Mapping[str, Any]) -> str:
    visible_candidates = [
        {
            "id": item["id"],
            "name": item["name"],
            "status": item["status"],
            "source_family": item["source_family"],
            "attributes": item["attributes"],
        }
        for item in working_set["candidates"]
    ]
    return f"""사용자의 짧은 후보 교정을 구조화하세요. 실행하거나 답변하지 마세요.

[교정 원문]
{text}

[현재 조건]
{json.dumps(working_set['constraints'], ensure_ascii=False, indent=2)}

[현재 후보]
{json.dumps(visible_candidates, ensure_ascii=False, indent=2)}

규칙:
- 사용자가 명시한 변화만 추출합니다.
- 후보를 지칭하면 반드시 위 candidate id를 사용합니다.
- 가격·수량 등 비교 가능한 조건은 constraint_updates에 key/operator/value로 둡니다.
- 단순 제외는 exclude_candidate, 범주 추가는 scope_expand, 더 찾기는 request_more입니다.
- 특정 후보 사실 확인은 request_verification, 현재 후보로 결론을 원하면 accept_candidates입니다.
- 불명확한 수치나 속성을 임의로 만들지 않습니다.
- interpretation은 교정을 한 문장으로 요약합니다.
"""


def _dynamic_context(state: Mapping[str, Any]) -> str:
    base = str(state.get("context", "")).strip()
    working = state["candidate_working_set"]
    compact = {
        "constraints": working["constraints"],
        "source_plan": working["source_plan"],
        "kept_candidates": WORKING.kept_candidates(working),
        "latest_correction": state.get("latest_correction"),
    }
    addition = "[현재 후보 작업대]\n" + json.dumps(compact, ensure_ascii=False, indent=2)
    return f"{base}\n\n{addition}".strip()


def _sync_dynamic_outcome(
    run_dir: Path,
    state: dict[str, Any],
    dynamic_state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    state["dynamic_state"] = copy.deepcopy(dict(dynamic_state))
    state["pending_questions"] = list(dynamic_state.get("pending_questions", []))
    dynamic_status = dynamic_state.get("state")
    working = state["candidate_working_set"]
    if dynamic_status == "awaiting_user":
        state["state"] = "awaiting_information"
    elif dynamic_status == "completed":
        state["state"] = "completed"
        working["state"] = "completed"
        working["next_action"] = None
    elif dynamic_status == "partial":
        state["state"] = "partial"
        working["state"] = "partial"
    else:
        state["state"] = "running"
    state["candidate_working_set"] = WORKING.validate_working_set(working)
    _save_state(run_dir, state, engine)
    return run_dir, state


def _start_dynamic(
    run_dir: Path,
    state: dict[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None,
    answers: Mapping[str, str] | None,
    max_changes: int,
) -> tuple[Path, dict[str, Any]]:
    if max_changes not in {0, 1}:
        raise NextLoopError("최대 방법 변경 횟수는 0 또는 1이어야 합니다.")
    model_policy = policy or OS.load_model_policy()
    context = _dynamic_context(state)
    scan = DYNAMIC.validate_scan(WORKING.source_scout_to_dynamic_scan(state["source_scout"]))
    gate = DYNAMIC.validate_questions(
        DYNAMIC._invoke(
            engine,
            run_dir,
            name="next-question-gate",
            phase="next-question-gate",
            route=None,
            profile=model_policy["router_fallback"],
            schema=DYNAMIC.QUESTION_SCHEMA,
            prompt=DYNAMIC.question_prompt(state["request"], state["framing"], scan, context),
        )
    )
    collected_answers = {
        str(key): str(value).strip()
        for key, value in (answers or {}).items()
        if str(value).strip()
    }
    missing = [item for item in gate["questions"] if item["id"] not in collected_answers]
    dynamic_state: dict[str, Any] = {
        "version": 1,
        "run_id": state["run_id"],
        "state": "running",
        "request": state["request"],
        "context": context,
        "framing": state["framing"],
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
        dynamic_state["state"] = "awaiting_user"
        dynamic_state["pending_questions"] = missing
        DYNAMIC._save_state(run_dir, dynamic_state, engine)
        return _sync_dynamic_outcome(run_dir, state, dynamic_state, engine=engine)
    _unused, dynamic_state = DYNAMIC._execute_action_loop(
        run_dir,
        dynamic_state,
        engine=engine,
        model_policy=model_policy,
        max_changes=max_changes,
    )
    return _sync_dynamic_outcome(run_dir, state, dynamic_state, engine=engine)


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
    cleaned = _clean_request(request)
    chosen_run_id = _run_id(run_id)
    run_dir = output_root.expanduser().resolve() / chosen_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.txt").write_text(cleaned + "\n", encoding="utf-8")
    if context.strip():
        (run_dir / "context.txt").write_text(context.strip() + "\n", encoding="utf-8")

    _scout_dir, source_scout = SCOUT.run_source_scout(
        cleaned,
        engine=engine,
        output_root=run_dir,
        run_id="source-scout",
        context=context,
        max_searches=max_searches,
        policy=policy,
    )
    model_policy = policy or OS.load_model_policy()
    frame = DYNAMIC.validate_framing(
        DYNAMIC._invoke(
            engine,
            run_dir,
            name="next-framing",
            phase="next-framing",
            route=None,
            profile=model_policy["router_fallback"],
            schema=DYNAMIC.FRAMING_SCHEMA,
            prompt=DYNAMIC.framing_prompt(cleaned, context),
        )
    )
    working = WORKING.new_working_set(
        run_id=chosen_run_id,
        request=cleaned,
        goal=frame["goal_hypothesis"],
        constraints={"explicit_constraints": frame["explicit_constraints"]},
        source_scout_state=source_scout,
        unresolved_requirements=[
            item["question_area"] for item in frame["unknowns"] if not item["externally_discoverable"]
        ],
    )
    state: dict[str, Any] = {
        "version": 1,
        "run_id": chosen_run_id,
        "state": "awaiting_correction" if working["candidates"] else "running",
        "request": cleaned,
        "context": context.strip(),
        "framing": frame,
        "source_scout": source_scout,
        "candidate_working_set": working,
        "pending_questions": [],
        "dynamic_state": None,
        "latest_correction": None,
        "engine_trace": [],
    }
    if pause_for_correction and working["candidates"]:
        _save_state(run_dir, state, engine)
        return run_dir, state
    return _start_dynamic(
        run_dir,
        state,
        engine=engine,
        policy=model_policy,
        answers=None,
        max_changes=max_changes,
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
    resolved = run_dir.expanduser().resolve()
    state_path = resolved / STATE_FILENAME
    if not state_path.is_file():
        raise NextLoopError(f"재개할 상태 파일이 없습니다: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))

    if state.get("state") == "awaiting_information":
        _unused, dynamic_state = DYNAMIC.resume_dynamic_loop(
            resolved,
            engine=engine,
            answers=answers,
            policy=policy,
            max_changes=max_changes,
        )
        return _sync_dynamic_outcome(resolved, state, dynamic_state, engine=engine)
    if state.get("state") != "awaiting_correction":
        raise NextLoopError("사용자 교정을 기다리는 실행만 교정으로 재개할 수 있습니다.")
    if correction is not None and correction_text is not None:
        raise NextLoopError("correction과 correction_text는 동시에 지정할 수 없습니다.")
    if correction is None and correction_text is None:
        raise NextLoopError("awaiting_correction 상태에는 교정이 필요합니다.")

    if correction is not None:
        planned = WORKING.validate_correction(dict(correction))
    else:
        text = str(correction_text).strip()
        if not text:
            raise NextLoopError("correction_text가 비어 있습니다.")
        model_policy = policy or OS.load_model_policy()
        raw = DYNAMIC._invoke(
            engine,
            resolved,
            name=f"next-correction-{state['candidate_working_set']['revision'] + 1}",
            phase="next-correction",
            route=None,
            profile=model_policy["router_fallback"],
            schema=CORRECTION_SCHEMA,
            prompt=correction_prompt(text, state["candidate_working_set"]),
        )
        planned = WORKING.correction_from_model_output(
            raw,
            working_set=state["candidate_working_set"],
            correction_id=f"correction-{state['candidate_working_set']['revision'] + 1:03d}",
            original_text=text,
        )

    working = WORKING.apply_correction(state["candidate_working_set"], planned)
    state["candidate_working_set"] = working
    state["latest_correction"] = planned
    action = planned["planned_action"]
    if action == "RERANK":
        state["state"] = "awaiting_correction"
        _save_state(resolved, state, engine)
        return resolved, state
    if action == "FILTER":
        filtered, stats = WORKING.apply_known_constraint_filter(
            working,
            planned["constraint_updates"],
            reason=planned["text"],
        )
        state["candidate_working_set"] = filtered
        if stats["evaluated"] > 0 and WORKING.kept_candidates(filtered):
            filtered["state"] = "awaiting_correction"
            filtered["next_action"] = None
            state["candidate_working_set"] = WORKING.validate_working_set(filtered)
            state["state"] = "awaiting_correction"
            _save_state(resolved, state, engine)
            return resolved, state
        state["candidate_working_set"]["state"] = "researching"
        state["candidate_working_set"]["next_action"] = "PARTIAL_RESEARCH"
    state["state"] = "running"
    return _start_dynamic(
        resolved,
        state,
        engine=engine,
        policy=policy,
        answers=answers,
        max_changes=max_changes,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--context-file", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--correction-file", type=Path)
    parser.add_argument("--correction")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = OS.CodexEngine(ROOT, enable_search=True)
    try:
        if args.resume is not None:
            if bool(args.correction_file) == bool(args.correction):
                raise NextLoopError("재개에는 --correction-file 또는 --correction 중 하나가 필요합니다.")
            structured = (
                json.loads(args.correction_file.read_text(encoding="utf-8"))
                if args.correction_file is not None
                else None
            )
            run_dir, state = resume_next_loop(
                args.resume,
                engine=engine,
                correction=structured,
                correction_text=args.correction,
            )
        else:
            if bool(args.request) == bool(args.request_file):
                raise NextLoopError("--request 또는 --request-file 중 하나만 지정하세요.")
            request = args.request or args.request_file.read_text(encoding="utf-8")
            context = args.context_file.read_text(encoding="utf-8") if args.context_file else ""
            run_dir, state = run_next_loop(
                request,
                engine=engine,
                output_root=args.output_root,
                run_id=args.run_id,
                context=context,
            )
        print(f"next-loop run: {run_dir}")
        print(f"state: {state['state']}")
        return 0
    except (NextLoopError, WORKING.CandidateWorkingSetError, OSError, json.JSONDecodeError) as exc:
        print(f"next-loop 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
