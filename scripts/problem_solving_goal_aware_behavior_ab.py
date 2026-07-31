#!/usr/bin/env python3
"""Compare a neutral assistant with a goal-aware, proactive, independent policy."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import statistics
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OS_PATH = ROOT / "scripts" / "problem_solving_os.py"
POLICY_PATH = ROOT / "configs" / "psos-goal-aware-assistant-policy.md"
CASES_PATH = ROOT / "tests" / "fixtures" / "goal-aware-assistant-cases.json"
ANSWER_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json"
ASSESSMENT_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-goal-aware-assessment.schema.json"
DEFAULT_OUTPUT_ROOT = ROOT / "runtime-results" / "goal-aware-behavior-ab"
VARIANTS = ("baseline", "goal_aware")
SCORE_FIELDS = (
    "goal_fit",
    "clarification_calibration",
    "initiative",
    "independent_judgment",
    "evidence_priority",
    "scope_control",
    "tone",
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = _load_module("psos_for_goal_aware_behavior_ab", OS_PATH)


class GoalAwareBehaviorABError(ValueError):
    """Raised when the controlled behavior comparison is invalid."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoalAwareBehaviorABError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise GoalAwareBehaviorABError(f"{label}은 JSON 객체여야 합니다.")
    return value


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return path


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoalAwareBehaviorABError(f"{label}이 비어 있습니다.")
    return value.strip()


def load_policy(path: Path = POLICY_PATH) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GoalAwareBehaviorABError(f"정책을 읽을 수 없습니다: {exc}") from exc
    if not value:
        raise GoalAwareBehaviorABError("후보 정책이 비어 있습니다.")
    return value


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    payload = _read_json(path, path.name)
    if set(payload) != {"version", "cases"} or payload["version"] != 1:
        raise GoalAwareBehaviorABError("사례 fixture 최상위 필드가 올바르지 않습니다.")
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise GoalAwareBehaviorABError("실험 사례가 없습니다.")
    expected = {
        "id",
        "title",
        "domain",
        "guard_case",
        "context_markdown",
        "turns",
        "criteria",
        "critical_failures",
    }
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, dict) or set(raw) != expected:
            raise GoalAwareBehaviorABError("사례 필드가 올바르지 않습니다.")
        case_id = _require_string(raw["id"], "case.id")
        if case_id in seen:
            raise GoalAwareBehaviorABError(f"중복 case id: {case_id}")
        seen.add(case_id)
        _require_string(raw["title"], f"{case_id}.title")
        _require_string(raw["domain"], f"{case_id}.domain")
        _require_string(raw["context_markdown"], f"{case_id}.context_markdown")
        if not isinstance(raw["guard_case"], bool):
            raise GoalAwareBehaviorABError(f"{case_id}.guard_case가 bool이 아닙니다.")
        turns = raw["turns"]
        if not isinstance(turns, list) or not turns:
            raise GoalAwareBehaviorABError(f"{case_id}.turns가 비어 있습니다.")
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict) or set(turn) != {"user_message"}:
                raise GoalAwareBehaviorABError(f"{case_id}.turns[{index}] 필드가 올바르지 않습니다.")
            _require_string(turn["user_message"], f"{case_id}.turns[{index}].user_message")
        for key in ("criteria", "critical_failures"):
            values = raw[key]
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(item, str) or not item.strip() for item in values)
            ):
                raise GoalAwareBehaviorABError(f"{case_id}.{key}가 올바르지 않습니다.")
        validated.append(raw)
    return validated


def _validate_answer(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"version", "answer_markdown"}:
        raise GoalAwareBehaviorABError("답변 필드가 schema와 일치하지 않습니다.")
    if payload["version"] != 1:
        raise GoalAwareBehaviorABError("지원하지 않는 답변 버전입니다.")
    _require_string(payload["answer_markdown"], "answer_markdown")
    return dict(payload)


def _validate_assessment(payload: Any, case_id: str) -> dict[str, Any]:
    expected = {"version", "case_id", "candidates", "preferred_candidate_ids", "conclusion"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise GoalAwareBehaviorABError("평가 필드가 schema와 일치하지 않습니다.")
    if payload["version"] != 1 or payload["case_id"] != case_id:
        raise GoalAwareBehaviorABError("평가 버전 또는 case_id가 일치하지 않습니다.")
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise GoalAwareBehaviorABError("평가 후보 수가 올바르지 않습니다.")
    ids: list[str] = []
    candidate_expected = {
        "candidate_id",
        *SCORE_FIELDS,
        "critical_failures",
        "finding",
    }
    for item in candidates:
        if not isinstance(item, dict) or set(item) != candidate_expected:
            raise GoalAwareBehaviorABError("후보 평가 필드가 올바르지 않습니다.")
        candidate_id = item["candidate_id"]
        if candidate_id not in {"A", "B"}:
            raise GoalAwareBehaviorABError("candidate_id는 A 또는 B여야 합니다.")
        ids.append(candidate_id)
        for key in SCORE_FIELDS:
            if not isinstance(item[key], int) or not 1 <= item[key] <= 5:
                raise GoalAwareBehaviorABError(f"{key} 점수가 1~5 범위가 아닙니다.")
        if not isinstance(item["critical_failures"], list) or any(
            not isinstance(value, str) or not value.strip()
            for value in item["critical_failures"]
        ):
            raise GoalAwareBehaviorABError("critical_failures가 올바르지 않습니다.")
        _require_string(item["finding"], "candidate.finding")
    if sorted(ids) != ["A", "B"]:
        raise GoalAwareBehaviorABError("후보 A와 B가 정확히 한 번씩 필요합니다.")
    preferred = payload["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or not 1 <= len(preferred) <= 2
        or len(set(preferred)) != len(preferred)
        or any(value not in {"A", "B"} for value in preferred)
    ):
        raise GoalAwareBehaviorABError("선호 후보가 올바르지 않습니다.")
    _require_string(payload["conclusion"], "assessment.conclusion")
    return dict(payload)


def _candidate_mapping(case_id: str) -> dict[str, str]:
    reverse = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:8], 16) % 2
    variants = list(reversed(VARIANTS)) if reverse else list(VARIANTS)
    return {"A": variants[0], "B": variants[1]}


def _render_history(history: Sequence[Mapping[str, str]]) -> str:
    if not history:
        return "(이전 대화 없음)"
    return "\n\n".join(
        f"[{item['role']}]\n{item['content']}" for item in history
    )


def build_turn_prompt(
    case: Mapping[str, Any],
    user_message: str,
    history: Sequence[Mapping[str, str]],
    policy: str | None,
) -> str:
    policy_block = (
        f"\n[추가 행동 원칙]\n{policy.strip()}\n" if policy else ""
    )
    return f"""당신은 현재 사용자 요청에 답하는 AI다.
{policy_block}
[통제 규칙]
- 아래 상황 자료 밖의 사실, 가격, 후기, 차트 신호를 만들어내지 않는다.
- 필요한 질문을 하는 것 자체도 하나의 유효한 답변이다.
- 추가 행동 원칙이나 A/B 실험을 언급하지 않는다.
- 사용자에게 실제로 보낼 답변만 answer_markdown에 넣는다.

[상황 자료]
{case['context_markdown']}

[이전 대화]
{_render_history(history)}

[현재 사용자 메시지]
{user_message}
"""


def _render_transcript(history: Sequence[Mapping[str, str]]) -> str:
    return "\n\n".join(
        f"**{item['role']}**\n\n{item['content']}" for item in history
    )


def _blind_candidates(
    mapping: Mapping[str, str],
    transcripts: Mapping[str, str],
) -> str:
    return "\n\n---\n\n".join(
        f"## 후보 {candidate_id}\n\n{transcripts[variant]}"
        for candidate_id, variant in mapping.items()
    )


def build_judge_prompt(
    case: Mapping[str, Any],
    mapping: Mapping[str, str],
    transcripts: Mapping[str, str],
) -> str:
    return f"""당신은 범용 AI 행동 정책의 블라인드 평가자다.

두 후보는 같은 상황과 사용자 메시지를 처리했다. 내부 정책 이름은 공개되지 않는다.
후보가 실제로 한 행동만 평가하고, 없는 장점은 추측하지 않는다.

[점수 기준: 모두 1 매우 나쁨 ~ 5 매우 좋음]
- goal_fit: 사용자가 실제로 얻으려는 결과에 맞는가
- clarification_calibration: 필요할 때만 핵심 질문을 하고, 충분할 때는 진행하는가
- initiative: 유용한 다음 행동·자료·방법을 스스로 선택하되 불필요한 절차를 만들지 않는가
- independent_judgment: 사용자 의견에 휩쓸리지 않고 근거로 판단하는가
- evidence_priority: 사용자에게 중요한 체감과 제공 근거를 적절히 우선하는가
- scope_control: 예상 밖의 관점은 쓸모 있을 때만 쓰고 문제를 과도하게 키우지 않는가
- tone: 정중하고 자연스러우며 사용자를 불필요하게 평가하지 않는가

critical_failures가 하나라도 있으면 점수 합보다 우선해 불리하게 본다.
짧다는 이유만으로 선호하지 않고, 반대로 길고 전문적이라는 이유로 높게 평가하지 않는다.

[사례]
{case['title']}

[상황 자료]
{case['context_markdown']}

[평가 기준]
{json.dumps(case['criteria'], ensure_ascii=False, indent=2)}

[치명적 실패]
{json.dumps(case['critical_failures'], ensure_ascii=False, indent=2)}

{_blind_candidates(mapping, transcripts)}
"""


def build_manual_review(
    case: Mapping[str, Any],
    mapping: Mapping[str, str],
    transcripts: Mapping[str, str],
) -> str:
    return f"""# 블라인드 검토: {case['title']}

아래 두 후보 중 실제로 더 도움이 되는 쪽을 고른다. 후보의 내부 정책 이름은 숨겨져 있다.

## 확인할 것

{chr(10).join(f'- {item}' for item in case['criteria'])}

## 치명적 실패

{chr(10).join(f'- {item}' for item in case['critical_failures'])}

{_blind_candidates(mapping, transcripts)}

## 기록

- 선호 후보: A / B / 동률
- 치명적 실패:
- 가장 큰 차이:
- 길이나 말투만 좋아진 것인지, 실제 행동이 달라진 것인지:
"""


def _metrics(history: Sequence[Mapping[str, str]]) -> dict[str, int]:
    assistant = [item["content"] for item in history if item["role"] == "assistant"]
    final = assistant[-1] if assistant else ""
    return {
        "assistant_turns": len(assistant),
        "total_characters": sum(len(value) for value in assistant),
        "final_characters": len(final),
        "question_marks": sum(value.count("?") for value in assistant),
    }


def _default_profile() -> Any:
    original = OS.load_model_policy()["routes"]["DIRECT"]["primary"]
    return OS.ModelProfile(
        model=original.model,
        reasoning_effort=original.reasoning_effort,
        web_search=False,
        sandbox="read-only",
    )


def _aggregate(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    assessed = [case for case in cases if isinstance(case.get("assessment"), dict)]
    if not assessed:
        return None
    preferred = {variant: 0 for variant in VARIANTS}
    score_values = {
        variant: {field: [] for field in SCORE_FIELDS} for variant in VARIANTS
    }
    critical = {variant: 0 for variant in VARIANTS}
    guard_critical = {variant: 0 for variant in VARIANTS}
    lengths = {variant: [] for variant in VARIANTS}
    for case in assessed:
        mapping = case["candidate_mapping"]
        for variant in VARIANTS:
            lengths[variant].append(case["variants"][variant]["metrics"]["total_characters"])
        for candidate_id in case["assessment"]["preferred_candidate_ids"]:
            preferred[mapping[candidate_id]] += 1
        for item in case["assessment"]["candidates"]:
            variant = mapping[item["candidate_id"]]
            for field in SCORE_FIELDS:
                score_values[variant][field].append(item[field])
            count = len(item["critical_failures"])
            critical[variant] += count
            if case["guard_case"]:
                guard_critical[variant] += count
    averages = {
        variant: {
            field: round(statistics.mean(values), 3)
            for field, values in fields.items()
        }
        for variant, fields in score_values.items()
    }
    medians = {
        variant: float(statistics.median(values)) for variant, values in lengths.items()
    }
    key_fields = ("clarification_calibration", "initiative", "independent_judgment")
    behavior_delta = statistics.mean(
        averages["goal_aware"][field] - averages["baseline"][field]
        for field in key_fields
    )
    length_ratio = (
        medians["goal_aware"] / medians["baseline"]
        if medians["baseline"]
        else None
    )
    thresholds = {
        "goal_aware_preferred_in_at_least_6_of_8": preferred["goal_aware"] >= 6,
        "no_goal_aware_critical_failure_in_guard_cases": guard_critical["goal_aware"] == 0,
        "key_behavior_average_delta_at_least_0_5": behavior_delta >= 0.5,
        "median_length_ratio_at_most_1_35": length_ratio is not None and length_ratio <= 1.35,
    }
    return {
        "assessed_cases": len(assessed),
        "preferred_case_counts": preferred,
        "score_averages": averages,
        "critical_failure_counts": critical,
        "guard_critical_failure_counts": guard_critical,
        "median_total_characters": medians,
        "key_behavior_average_delta": round(behavior_delta, 3),
        "goal_aware_length_ratio": round(length_ratio, 3) if length_ratio is not None else None,
        "preregistered_thresholds": thresholds,
        "provisional_pass": all(thresholds.values()),
    }


def _render_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# Goal-aware assistant behavior A/B",
        "",
        "| 사례 | 선호 경로 | baseline 길이 | goal-aware 길이 |",
        "|---|---|---:|---:|",
    ]
    for case in manifest["cases"]:
        preferred = case.get("preferred_variants") or []
        lines.append(
            f"| {case['title']} | {', '.join(preferred) if preferred else '미평가'} | "
            f"{case['variants']['baseline']['metrics']['total_characters']} | "
            f"{case['variants']['goal_aware']['metrics']['total_characters']} |"
        )
    aggregate = manifest.get("aggregate")
    if isinstance(aggregate, dict):
        lines.extend(
            [
                "",
                "## 사전 등록 기준",
                "",
            ]
        )
        for key, passed in aggregate["preregistered_thresholds"].items():
            lines.append(f"- {'통과' if passed else '실패'}: {key}")
        lines.extend(
            [
                "",
                f"자동 평가의 잠정 종합 판정: {'통과' if aggregate['provisional_pass'] else '실패'}",
                "",
                "자동 평가자는 보조 수단이다. 최종 판단은 각 사례의 blind_review.md를 사람이 정책 이름 없이 비교한 결과를 우선한다.",
            ]
        )
    lines.extend(
        [
            "",
            "## 해석 경계",
            "",
            "이 실험은 고정된 가상 자료에서 질문 판단, 주도성, 독립 판단, 실제 경험 우선, 과잉 개입 방지를 비교한다. 라이브 웹 조사 정확성, 실제 투자 수익, 장기 개인화는 검증하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def run_comparison(
    *,
    cases_path: Path = CASES_PATH,
    policy_path: Path = POLICY_PATH,
    selected_case_ids: Sequence[str] | None = None,
    output_dir: Path | None = None,
    judge: bool = True,
    timeout_seconds: int = 600,
    engine: Any | None = None,
    profile_override: Any | None = None,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    policy = load_policy(policy_path)
    if selected_case_ids:
        requested = set(selected_case_ids)
        cases = [case for case in cases if case["id"] in requested]
        missing = sorted(requested - {case["id"] for case in cases})
        if missing:
            raise GoalAwareBehaviorABError("알 수 없는 case id: " + ", ".join(missing))
    if not cases:
        raise GoalAwareBehaviorABError("실행할 사례가 없습니다.")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = (output_dir or (DEFAULT_OUTPUT_ROOT / stamp)).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    profile = profile_override or _default_profile()
    if profile.web_search or profile.sandbox != "read-only":
        raise GoalAwareBehaviorABError("실험 프로필은 web_search 없는 read-only여야 합니다.")
    runtime_engine = engine or OS.CodexEngine(
        ROOT,
        enable_search=False,
        timeout_seconds=timeout_seconds,
    )
    capabilities = runtime_engine.capabilities()
    if not capabilities.ai_reasoning:
        raise GoalAwareBehaviorABError(
            capabilities.detail or "실험 모델을 실행할 capability가 없습니다."
        )

    manifest_cases: list[dict[str, Any]] = []
    for case in cases:
        case_dir = root / case["id"]
        _write_json(case_dir / "case.json", case)
        variant_data: dict[str, Any] = {}
        transcripts: dict[str, str] = {}
        for variant in VARIANTS:
            history: list[dict[str, str]] = []
            variant_policy = policy if variant == "goal_aware" else None
            for index, turn in enumerate(case["turns"], start=1):
                user_message = turn["user_message"].strip()
                prompt = build_turn_prompt(case, user_message, history, variant_policy)
                _write_text(
                    case_dir / variant / f"turn_{index:02d}_prompt.md",
                    prompt,
                )
                invocation = OS.InvocationSpec(
                    name=f"goal-aware-ab-{case['id']}-{variant}-turn-{index}",
                    phase="goal_aware_answer",
                    route=None,
                    profile=profile,
                    schema_path=ANSWER_SCHEMA_PATH,
                )
                payload = _validate_answer(
                    runtime_engine.execute(prompt, case_dir, invocation)
                )
                answer = payload["answer_markdown"].strip()
                _write_json(
                    case_dir / variant / f"turn_{index:02d}_answer.json",
                    payload,
                )
                _write_text(
                    case_dir / variant / f"turn_{index:02d}_answer.md",
                    answer,
                )
                history.extend(
                    [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": answer},
                    ]
                )
            transcript = _render_transcript(history)
            transcript_path = _write_text(
                case_dir / variant / "transcript.md",
                transcript,
            )
            transcripts[variant] = transcript
            variant_data[variant] = {
                "transcript_path": transcript_path.relative_to(root).as_posix(),
                "metrics": _metrics(history),
            }

        mapping = _candidate_mapping(case["id"])
        blind_review = build_manual_review(case, mapping, transcripts)
        blind_review_path = _write_text(case_dir / "blind_review.md", blind_review)
        assessment: dict[str, Any] | None = None
        preferred_variants: list[str] = []
        if judge:
            judge_text = build_judge_prompt(case, mapping, transcripts)
            _write_text(case_dir / "blind_assessment_prompt.md", judge_text)
            invocation = OS.InvocationSpec(
                name=f"goal-aware-ab-assess-{case['id']}",
                phase="assessment",
                route=None,
                profile=profile,
                schema_path=ASSESSMENT_SCHEMA_PATH,
            )
            assessment = _validate_assessment(
                runtime_engine.execute(judge_text, case_dir, invocation),
                case["id"],
            )
            _write_json(case_dir / "blind_assessment.json", assessment)
            preferred_variants = [
                mapping[candidate_id]
                for candidate_id in assessment["preferred_candidate_ids"]
            ]
        manifest_cases.append(
            {
                "id": case["id"],
                "title": case["title"],
                "domain": case["domain"],
                "guard_case": case["guard_case"],
                "candidate_mapping": mapping,
                "variants": variant_data,
                "blind_review_path": blind_review_path.relative_to(root).as_posix(),
                "assessment": assessment,
                "preferred_variants": preferred_variants,
            }
        )

    aggregate = _aggregate(manifest_cases)
    manifest = {
        "version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "profile": asdict(profile),
        "policy_path": str(policy_path.expanduser().resolve()),
        "cases_path": str(cases_path.expanduser().resolve()),
        "judge": judge,
        "cases": manifest_cases,
        "aggregate": aggregate,
        "preregistration": {
            "primary": "사람이 blind_review.md를 보고 정책 이름 없이 비교",
            "secondary": "동일 모델의 schema 기반 블라인드 평가",
            "repeat": "최종 채택 전 독립 실행 3회에서 같은 방향이 반복되는지 확인",
        },
    }
    manifest_path = _write_json(root / "manifest.json", manifest)
    report_path = _write_text(root / "report.md", _render_report(manifest))
    return {
        "version": 1,
        "output_dir": str(root),
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "case_ids": [case["id"] for case in manifest_cases],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        result = run_comparison(
            cases_path=args.cases,
            policy_path=args.policy,
            selected_case_ids=args.case or None,
            output_dir=args.output_dir,
            judge=not args.no_judge,
            timeout_seconds=args.timeout_seconds,
        )
    except (GoalAwareBehaviorABError, OS.ProblemSolvingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result["report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
