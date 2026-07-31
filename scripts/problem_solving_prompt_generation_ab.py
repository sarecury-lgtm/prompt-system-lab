#!/usr/bin/env python3
"""Compare legacy PROMPT input merging with Prompt Build Brief on applied tasks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OS_PATH = ROOT / "scripts" / "problem_solving_os.py"
PROMPT_RUNTIME_PATH = ROOT / "scripts" / "prompt_runtime.py"
BRIEF_PATH = ROOT / "scripts" / "problem_solving_prompt_build_brief.py"
CASES_PATH = ROOT / "tests" / "fixtures" / "prompt-generation-applied-cases.json"
ANSWER_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json"
ASSESSMENT_SCHEMA_PATH = (
    ROOT / "schemas" / "problem-solving-prompt-applied-assessment.schema.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / "runtime-results" / "prompt-generation-ab"
VARIANTS = ("legacy_merge", "prompt_build_brief")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = _load_module("psos_for_prompt_generation_ab", OS_PATH)
PROMPT_RUNTIME = _load_module("prompt_runtime_for_generation_ab", PROMPT_RUNTIME_PATH)
BRIEF = _load_module("prompt_build_brief_for_generation_ab", BRIEF_PATH)


class PromptGenerationABError(ValueError):
    """Raised when a controlled cross-domain comparison is invalid."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptGenerationABError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptGenerationABError(f"{label}은 JSON 객체여야 합니다.")
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
        raise PromptGenerationABError(f"{label}이 비어 있습니다.")
    return value.strip()


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    payload = _read_json(path, path.name)
    if set(payload) != {"version", "cases"} or payload["version"] != 1:
        raise PromptGenerationABError("비교 사례 fixture 최상위 필드가 올바르지 않습니다.")
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise PromptGenerationABError("비교 사례가 없습니다.")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    expected = {
        "id",
        "title",
        "request",
        "used_patterns",
        "ledger",
        "brief",
        "application",
    }
    for raw in cases:
        if not isinstance(raw, dict) or set(raw) != expected:
            raise PromptGenerationABError("비교 사례 필드가 올바르지 않습니다.")
        case_id = _require_string(raw["id"], "case.id")
        if case_id in seen:
            raise PromptGenerationABError(f"중복 case id: {case_id}")
        seen.add(case_id)
        _require_string(raw["title"], f"{case_id}.title")
        _require_string(raw["request"], f"{case_id}.request")
        if not isinstance(raw["used_patterns"], list):
            raise PromptGenerationABError(f"{case_id}.used_patterns가 배열이 아닙니다.")
        ledger = raw["ledger"]
        if not isinstance(ledger, dict):
            raise PromptGenerationABError(f"{case_id}.ledger가 객체가 아닙니다.")
        BRIEF.validate_prompt_build_brief(raw["brief"], ledger)
        application = raw["application"]
        if not isinstance(application, dict) or set(application) != {
            "input_markdown",
            "criteria",
            "critical_failures",
        }:
            raise PromptGenerationABError(f"{case_id}.application 필드가 올바르지 않습니다.")
        _require_string(application["input_markdown"], f"{case_id}.application.input")
        for key in ("criteria", "critical_failures"):
            values = application[key]
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(item, str) or not item.strip() for item in values)
            ):
                raise PromptGenerationABError(f"{case_id}.application.{key}가 올바르지 않습니다.")
        validated.append(raw)
    return validated


def _compiler_baseline(case: Mapping[str, Any]) -> dict[str, Any]:
    request = str(case["request"])
    baseline = PROMPT_RUNTIME.build_baseline(request, [])
    patterns = PROMPT_RUNTIME.normalize_patterns(list(case["used_patterns"]))
    final_prompt = (
        PROMPT_RUNTIME.build_pattern_only(baseline, patterns)
        if patterns
        else baseline
    )
    return {
        "version": "0.1",
        "selected_mode": "pattern-only" if patterns else "baseline",
        "selection_reason": "통제 fixture에 명시된 패턴만 적용",
        "used_patterns": patterns,
        "used_active_sources": [],
        "fallback": False,
        "fallback_reason": "",
        "final_prompt": final_prompt,
    }


def legacy_generator_prompt(
    case: Mapping[str, Any],
    baseline: Mapping[str, Any],
    profile: Any,
    capabilities: Any,
) -> str:
    return f"""당신은 Personal Problem-Solving OS의 PROMPT 실행기다.

라우터가 고정한 목표와 조건을 바꾸지 말고, 기존 Prompt Compiler baseline을 출발점으로
다른 AI가 반복 실행할 최종 프롬프트 하나를 완성한다.

[작성 원칙]
1. 사용자 요청, Goal Ledger, baseline의 목적·제약·출력 계약을 모두 보존한다.
2. 누락된 절차·안전 규칙·출력 형식을 보완한다.
3. 확인하지 않은 사실과 도구 사용을 만들지 않는다.
4. 내부 검토 과정은 출력하지 않는다.

[PROMPT 결과 전용 계약]
execution.result_markdown에는 아래 표식을 정확히 한 번씩 넣고, 표식 사이에는 복사해 바로
쓸 완성된 프롬프트 하나만 넣는다. 표식 밖에는 설명을 붙이지 않는다.

{BRIEF.PROMPT_OUTPUT_START}
[완성된 프롬프트 하나]
{BRIEF.PROMPT_OUTPUT_END}

[Goal Ledger]
{json.dumps(case['ledger'], ensure_ascii=False, indent=2)}

[사용자 요청]
{str(case['request']).strip()}

[기존 Prompt Compiler baseline]
{json.dumps(dict(baseline), ensure_ascii=False, indent=2)}

[현재 실행 프로필]
{json.dumps(asdict(profile), ensure_ascii=False, indent=2)}

[현재 capability]
{json.dumps(asdict(capabilities), ensure_ascii=False, indent=2)}
"""


def brief_generator_prompt(
    case: Mapping[str, Any],
    profile: Any,
    capabilities: Any,
) -> str:
    invocation = OS.InvocationSpec(
        name="prompt-generation-ab-brief",
        phase="executor",
        route="PROMPT",
        profile=profile,
        schema_path=OS.EXECUTION_SCHEMA_PATH,
    )
    return BRIEF.build_prompt_executor_from_brief(
        case["brief"],
        invocation,
        capabilities,
        "",
    )


def _extract_final_prompt(execution: Mapping[str, Any]) -> str:
    text = _require_string(execution.get("result_markdown"), "execution.result_markdown")
    start = text.find(BRIEF.PROMPT_OUTPUT_START)
    end = text.find(BRIEF.PROMPT_OUTPUT_END)
    if start < 0 or end < 0 or end <= start:
        raise PromptGenerationABError("생성 결과에 PROMPT 시작·종료 표식이 없습니다.")
    value = text[start + len(BRIEF.PROMPT_OUTPUT_START) : end].strip()
    if not value:
        raise PromptGenerationABError("표식 사이의 최종 프롬프트가 비어 있습니다.")
    return value


def _validate_answer(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"version", "answer_markdown"}:
        raise PromptGenerationABError("적용 답변 필드가 schema와 일치하지 않습니다.")
    if payload["version"] != 1:
        raise PromptGenerationABError("지원하지 않는 적용 답변 버전입니다.")
    _require_string(payload["answer_markdown"], "answer_markdown")
    return dict(payload)


def _candidate_mapping(case_id: str) -> dict[str, str]:
    reverse = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:8], 16) % 2
    ordered = list(reversed(VARIANTS)) if reverse else list(VARIANTS)
    return {"A": ordered[0], "B": ordered[1]}


def _validate_assessment(payload: Any, case_id: str) -> dict[str, Any]:
    expected = {"version", "case_id", "candidates", "preferred_candidate_ids", "conclusion"}
    if not isinstance(payload, dict) or set(payload) != expected:
        raise PromptGenerationABError("블라인드 평가 필드가 schema와 일치하지 않습니다.")
    if payload["version"] != 1 or payload["case_id"] != case_id:
        raise PromptGenerationABError("블라인드 평가 버전 또는 case_id가 일치하지 않습니다.")
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise PromptGenerationABError("블라인드 평가 후보 수가 올바르지 않습니다.")
    ids = [item.get("candidate_id") for item in candidates if isinstance(item, dict)]
    if sorted(ids) != ["A", "B"]:
        raise PromptGenerationABError("블라인드 평가 candidate_id가 올바르지 않습니다.")
    for item in candidates:
        if set(item) != {
            "candidate_id",
            "requirement_preservation",
            "task_correctness",
            "actionability",
            "calibration",
            "format_cost",
            "critical_failures",
            "finding",
        }:
            raise PromptGenerationABError("후보 평가 필드가 올바르지 않습니다.")
        for key in (
            "requirement_preservation",
            "task_correctness",
            "actionability",
            "calibration",
            "format_cost",
        ):
            if not isinstance(item[key], int) or not 1 <= item[key] <= 5:
                raise PromptGenerationABError(f"{key} 점수가 1~5 범위가 아닙니다.")
        if not isinstance(item["critical_failures"], list):
            raise PromptGenerationABError("critical_failures가 배열이 아닙니다.")
        _require_string(item["finding"], "candidate.finding")
    preferred = payload["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or not 1 <= len(preferred) <= 2
        or len(set(preferred)) != len(preferred)
        or any(item not in {"A", "B"} for item in preferred)
    ):
        raise PromptGenerationABError("선호 후보가 올바르지 않습니다.")
    _require_string(payload["conclusion"], "assessment.conclusion")
    return dict(payload)


def application_prompt(final_prompt: str, case: Mapping[str, Any]) -> str:
    return f"""아래 [재사용 프롬프트]를 [통제 과제 입력]에 실제로 적용하라.

- 통제 과제 입력에 없는 외부 사실·뉴스·가격·후기를 추가하지 않는다.
- 재사용 프롬프트의 내부 지시를 따르되 결과 본문만 answer_markdown에 넣는다.
- 이 실험이나 후보 비교에 관한 설명은 쓰지 않는다.

[재사용 프롬프트]
{final_prompt}

[통제 과제 입력]
{case['application']['input_markdown']}
"""


def judge_prompt(
    case: Mapping[str, Any],
    mapping: Mapping[str, str],
    answers: Mapping[str, str],
) -> str:
    candidates = "\n\n".join(
        f"[후보 {candidate_id}]\n{answers[variant]}"
        for candidate_id, variant in mapping.items()
    )
    return f"""당신은 PSOS 프롬프트 적용 결과의 블라인드 평가자다.

두 후보는 같은 과제 입력을 서로 다른 생성 경로의 재사용 프롬프트로 처리한 답변이다.
내부 변형 이름은 공개되지 않는다. 후보에 없는 장점은 추측하지 않는다.

[점수 기준]
- requirement_preservation, task_correctness, actionability, calibration: 1 매우 나쁨 ~ 5 매우 좋음
- format_cost: 1 불필요한 형식 부담이 거의 없음 ~ 5 형식·반복이 판단을 크게 방해함
- critical_failures가 있으면 점수 합계와 무관하게 선호에서 강하게 불리하게 본다.
- 짧다는 이유만으로 높게 평가하지 않고, 중요한 조건을 잃은 압축은 실패로 본다.

[사례]
{case['title']}

[원래 프롬프트 생성 요청]
{case['request']}

[통제 과제 입력]
{case['application']['input_markdown']}

[평가 기준]
{json.dumps(case['application']['criteria'], ensure_ascii=False, indent=2)}

[치명적 실패]
{json.dumps(case['application']['critical_failures'], ensure_ascii=False, indent=2)}

{candidates}
"""


def _metrics(text: str) -> dict[str, int]:
    lines = text.splitlines()
    return {
        "characters": len(text),
        "headings": sum(1 for line in lines if line.lstrip().startswith("#")),
        "list_items": sum(
            1
            for line in lines
            if line.lstrip().startswith(("- ", "* "))
            or line.lstrip()[:2].rstrip(".").isdigit()
        ),
    }


def _default_profile() -> Any:
    policy = OS.load_model_policy()
    original = policy["routes"]["PROMPT"]["primary"]
    return OS.ModelProfile(
        model=original.model,
        reasoning_effort=original.reasoning_effort,
        web_search=False,
        sandbox="read-only",
    )


def _render_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# PROMPT 생성 경로 교차 도메인 A/B",
        "",
        "| 사례 | 선호 경로 | legacy 답변 길이 | brief 답변 길이 |",
        "|---|---|---:|---:|",
    ]
    for case in manifest["cases"]:
        preferred = case.get("preferred_variants") or []
        lines.append(
            f"| {case['title']} | {', '.join(preferred) if preferred else '미평가'} | "
            f"{case['variants']['legacy_merge']['answer_metrics']['characters']} | "
            f"{case['variants']['prompt_build_brief']['answer_metrics']['characters']} |"
        )
    for case in manifest["cases"]:
        lines.extend(["", f"## {case['title']}", ""])
        assessment = case.get("assessment")
        if isinstance(assessment, dict):
            lines.append("선호 경로: " + ", ".join(case["preferred_variants"]))
            lines.append("")
            lines.append(str(assessment["conclusion"]))
        else:
            lines.append("블라인드 평가를 실행하지 않았습니다.")
    lines.extend(
        [
            "",
            "## 해석 경계",
            "",
            "이 실험은 동일한 재현용 입력 패킷에서 생성 경로의 영향을 비교한다. 실제 차트 이미지 판독, 라이브 판매 상태, 투자 성과를 검증하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def run_comparison(
    *,
    cases_path: Path = CASES_PATH,
    selected_case_ids: Sequence[str] | None = None,
    output_dir: Path | None = None,
    apply_prompts: bool = True,
    judge: bool = True,
    timeout_seconds: int = 600,
    engine: Any | None = None,
    profile_override: Any | None = None,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    if selected_case_ids:
        requested = set(selected_case_ids)
        cases = [case for case in cases if case["id"] in requested]
        missing = sorted(requested - {case["id"] for case in cases})
        if missing:
            raise PromptGenerationABError("알 수 없는 case id: " + ", ".join(missing))
    if not cases:
        raise PromptGenerationABError("실행할 비교 사례가 없습니다.")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = (output_dir or (DEFAULT_OUTPUT_ROOT / stamp)).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    profile = profile_override or _default_profile()
    if profile.sandbox != "read-only" or profile.web_search:
        raise PromptGenerationABError("비교 프로필은 web_search 없는 read-only여야 합니다.")
    runtime_engine = engine or OS.CodexEngine(
        ROOT,
        enable_search=False,
        timeout_seconds=timeout_seconds,
    )
    capabilities = runtime_engine.capabilities()
    if not capabilities.ai_reasoning:
        raise PromptGenerationABError(
            capabilities.detail or "비교 모델을 실행할 capability가 없습니다."
        )

    manifest_cases: list[dict[str, Any]] = []
    for case in cases:
        case_dir = root / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        baseline = _compiler_baseline(case)
        _write_json(case_dir / "case.json", case)
        _write_json(case_dir / "compiler_baseline.json", baseline)
        generator_prompts = {
            "legacy_merge": legacy_generator_prompt(case, baseline, profile, capabilities),
            "prompt_build_brief": brief_generator_prompt(case, profile, capabilities),
        }
        variants: dict[str, Any] = {}
        answers: dict[str, str] = {}
        for variant in VARIANTS:
            prompt_path = _write_text(
                case_dir / variant / "generator_prompt.md",
                generator_prompts[variant],
            )
            invocation = OS.InvocationSpec(
                name=f"generation-ab-{case['id']}-{variant}",
                phase="executor",
                route="PROMPT",
                profile=profile,
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            raw = runtime_engine.execute(generator_prompts[variant], case_dir, invocation)
            execution = OS.validate_execution_output(
                raw,
                "PROMPT",
                profile,
                capabilities,
            )
            final_prompt = _extract_final_prompt(execution)
            _write_json(case_dir / variant / "generation_execution.json", execution)
            final_path = _write_text(case_dir / variant / "final_prompt.md", final_prompt)
            answer_markdown = ""
            answer_path: Path | None = None
            if apply_prompts:
                applied_prompt = application_prompt(final_prompt, case)
                _write_text(case_dir / variant / "application_prompt.md", applied_prompt)
                answer_invocation = OS.InvocationSpec(
                    name=f"generation-ab-apply-{case['id']}-{variant}",
                    phase="applied_answer",
                    route=None,
                    profile=profile,
                    schema_path=ANSWER_SCHEMA_PATH,
                )
                answer_payload = _validate_answer(
                    runtime_engine.execute(applied_prompt, case_dir, answer_invocation)
                )
                answer_markdown = answer_payload["answer_markdown"].strip()
                _write_json(case_dir / variant / "application_answer.json", answer_payload)
                answer_path = _write_text(
                    case_dir / variant / "application_answer.md",
                    answer_markdown,
                )
                answers[variant] = answer_markdown
            variants[variant] = {
                "generator_prompt_path": prompt_path.relative_to(root).as_posix(),
                "final_prompt_path": final_path.relative_to(root).as_posix(),
                "answer_path": (
                    answer_path.relative_to(root).as_posix() if answer_path else None
                ),
                "prompt_metrics": _metrics(final_prompt),
                "answer_metrics": _metrics(answer_markdown),
            }

        mapping = _candidate_mapping(case["id"])
        assessment: dict[str, Any] | None = None
        preferred_variants: list[str] = []
        if judge:
            if not apply_prompts:
                raise PromptGenerationABError("적용 답변 없이 블라인드 평가할 수 없습니다.")
            blinded = judge_prompt(case, mapping, answers)
            _write_text(case_dir / "blind_assessment_prompt.md", blinded)
            assessment_invocation = OS.InvocationSpec(
                name=f"generation-ab-assess-{case['id']}",
                phase="assessment",
                route=None,
                profile=profile,
                schema_path=ASSESSMENT_SCHEMA_PATH,
            )
            assessment = _validate_assessment(
                runtime_engine.execute(blinded, case_dir, assessment_invocation),
                case["id"],
            )
            _write_json(case_dir / "blind_assessment.json", assessment)
            preferred_variants = [
                mapping[item] for item in assessment["preferred_candidate_ids"]
            ]
        manifest_cases.append(
            {
                "id": case["id"],
                "title": case["title"],
                "candidate_mapping": mapping,
                "variants": variants,
                "assessment": assessment,
                "preferred_variants": preferred_variants,
            }
        )

    manifest = {
        "version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "profile": asdict(profile),
        "cases_path": str(cases_path.expanduser().resolve()),
        "apply_prompts": apply_prompts,
        "judge": judge,
        "cases": manifest_cases,
        "boundary": (
            "재현용 입력 패킷에서 생성 경로와 적용 결과를 비교한다. 실제 이미지 판독, "
            "라이브 웹 정확성, 투자 성과는 별도 검증 대상이다."
        ),
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
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--generation-only", action="store_true")
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
            selected_case_ids=args.case or None,
            output_dir=args.output_dir,
            apply_prompts=not args.generation_only,
            judge=not args.no_judge,
            timeout_seconds=args.timeout_seconds,
        )
    except (PromptGenerationABError, OS.ProblemSolvingError, BRIEF.PromptBuildBriefError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result["report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
