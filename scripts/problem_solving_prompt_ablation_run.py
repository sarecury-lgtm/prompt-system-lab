#!/usr/bin/env python3
"""Execute PROMPT input-ablation variants with the original executor model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OS_PATH = ROOT / "scripts" / "problem_solving_os.py"
TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"
ABLATION_PATH = ROOT / "scripts" / "problem_solving_prompt_ablation.py"
ASSESSMENT_SCHEMA_PATH = (
    ROOT / "schemas" / "problem-solving-prompt-ablation-assessment.schema.json"
)
VARIANT_ORDER = (
    "current",
    "without_raw_request",
    "compact_ledger",
    "single_build_brief",
)


def _load_local_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = _load_local_module("psos_for_prompt_ablation_run", OS_PATH)
TRACE = _load_local_module("psos_trace_for_prompt_ablation_run", TRACE_PATH)
ABLATION = _load_local_module("psos_ablation_for_prompt_ablation_run", ABLATION_PATH)


class PromptAblationRunError(ValueError):
    """Raised when a controlled PROMPT comparison cannot be executed safely."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptAblationRunError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptAblationRunError(f"{label}은 JSON 객체여야 합니다.")
    return value


def _actual_prompt_profile(run_dir: Path) -> Any:
    route = _read_json(run_dir / "route.json", "route.json")
    executor_path = TRACE._find_executor_request(run_dir)
    invocation_name = executor_path.name.removesuffix("-request.md")
    run = route.get("run")
    if not isinstance(run, dict):
        raise PromptAblationRunError("route.json에 원래 실행 기록이 없습니다.")

    trace = run.get("engine_trace")
    if isinstance(trace, list):
        for item in trace:
            if not isinstance(item, dict):
                continue
            if item.get("name") != invocation_name or item.get("route") != "PROMPT":
                continue
            try:
                profile = OS.ModelProfile(
                    model=str(item["model"]),
                    reasoning_effort=str(item["reasoning_effort"]),
                    web_search=bool(item["web_search"]),
                    sandbox=str(
                        item.get("requested_sandbox")
                        or item.get("sandbox")
                        or "read-only"
                    ),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PromptAblationRunError(
                    "원래 PROMPT 실행 프로필을 복원할 수 없습니다."
                ) from exc
            if profile.sandbox != "read-only":
                raise PromptAblationRunError(
                    "PROMPT 비교 실행은 read-only 원본 프로필만 지원합니다."
                )
            return profile

    model_plan = run.get("model_plan")
    if isinstance(model_plan, list):
        for item in model_plan:
            if not isinstance(item, dict) or item.get("route") != "PROMPT":
                continue
            try:
                profile = OS.ModelProfile(
                    model=str(item["model"]),
                    reasoning_effort=str(item["reasoning_effort"]),
                    web_search=bool(item["web_search"]),
                    sandbox=str(item["sandbox"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PromptAblationRunError(
                    "PROMPT model_plan을 복원할 수 없습니다."
                ) from exc
            if profile.sandbox != "read-only":
                raise PromptAblationRunError(
                    "PROMPT 비교 실행은 read-only 원본 프로필만 지원합니다."
                )
            return profile

    raise PromptAblationRunError(
        "원래 PROMPT 실행에 사용된 모델·reasoning 프로필을 찾지 못했습니다."
    )


def _original_execution(run_dir: Path) -> dict[str, Any]:
    executor_path = TRACE._find_executor_request(run_dir)
    _output_path, execution = TRACE._find_execution_output(run_dir, executor_path)
    return dict(execution)


def _surface_coverage(source: str, target: str) -> float:
    source_tokens = TRACE._unique_tokens(source)
    target_tokens = TRACE._unique_tokens(target)
    if not target_tokens:
        return 1.0
    return round(len(source_tokens & target_tokens) / len(target_tokens), 3)


def _output_metrics(
    result_markdown: str,
    request: str,
    constraints: Sequence[str],
) -> dict[str, Any]:
    metrics = TRACE._metrics(result_markdown)
    duplicate_pairs = TRACE._duplicate_groups(result_markdown)
    constraint_signals = []
    for constraint in constraints:
        coverage = _surface_coverage(result_markdown, constraint)
        constraint_signals.append(
            {
                "constraint": constraint,
                "token_coverage": coverage,
                "surface_signal": (
                    "strong" if coverage >= 0.6 else "partial" if coverage >= 0.3 else "weak"
                ),
            }
        )
    average_constraint_coverage = (
        round(
            sum(item["token_coverage"] for item in constraint_signals)
            / len(constraint_signals),
            3,
        )
        if constraint_signals
        else 1.0
    )
    return {
        **metrics,
        "duplicate_pair_count": len(duplicate_pairs),
        "request_token_coverage": _surface_coverage(result_markdown, request),
        "average_constraint_token_coverage": average_constraint_coverage,
        "constraint_surface_signals": constraint_signals,
        "metric_boundary": (
            "토큰 겹침은 요구 보존의 표면 신호일 뿐 의미 충족을 증명하지 않습니다."
        ),
    }


def _candidate_mapping(run_id: str, variants: Sequence[str]) -> dict[str, str]:
    ordered = [variant for variant in VARIANT_ORDER if variant in variants]
    if not ordered:
        raise PromptAblationRunError("실행할 비교 변형이 없습니다.")
    offset = int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16) % len(
        ordered
    )
    rotated = ordered[offset:] + ordered[:offset]
    return {chr(ord("A") + index): variant for index, variant in enumerate(rotated)}


def _judge_prompt(
    request: str,
    ledger: Mapping[str, Any],
    mapping: Mapping[str, str],
    executions: Mapping[str, Mapping[str, Any]],
) -> str:
    constraints = ledger.get("fixed_constraints")
    if not isinstance(constraints, list):
        constraints = []
    candidates = []
    for candidate_id, variant in mapping.items():
        result = str(executions[variant]["result_markdown"]).strip()
        candidates.append(f"[후보 {candidate_id}]\n{result}")
    return f"""당신은 재사용 프롬프트 생성 실험의 블라인드 평가자다.

아래 후보는 같은 사용자 요청을 서로 다른 내부 입력 구조로 처리한 결과다. 후보의 내부 변형 이름은 공개되지 않는다.

[평가 목표]
1. 사용자 목표와 고정 조건을 실제로 보존하는지 확인한다.
2. 핵심 작업 절차가 보조 분석 도구·안전 규칙·출력 형식보다 먼저 보이고 우선되는지 평가한다.
3. 같은 뜻의 규칙과 형식이 반복되어 실제 작업을 방해하는지 평가한다.
4. 다른 AI가 그대로 반복 사용할 때 실용적인지 평가한다.
5. 짧다는 이유만으로 높게 평가하지 않는다. 중요한 조건을 잃은 압축은 실패다.
6. 후보에 없는 장점이나 충족 여부를 추측하지 않는다.
7. 내부 추론은 쓰지 말고 schema에 맞는 짧은 판정 근거만 반환한다.

[사용자 요청]
{request.strip()}

[고정 조건]
{json.dumps(constraints, ensure_ascii=False, indent=2)}

[완료 조건]
{str(ledger.get('completion_condition') or '').strip()}

{chr(10).join(candidates)}
"""


def _validate_assessment(
    payload: Any,
    candidate_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "variants",
        "preferred_candidate_ids",
        "conclusion",
    }:
        raise PromptAblationRunError("블라인드 평가 결과 필드가 schema와 일치하지 않습니다.")
    if payload["version"] != 1:
        raise PromptAblationRunError("지원하지 않는 블라인드 평가 버전입니다.")
    variants = payload["variants"]
    if not isinstance(variants, list) or len(variants) != len(candidate_ids):
        raise PromptAblationRunError("블라인드 평가 후보 수가 일치하지 않습니다.")
    seen: set[str] = set()
    for item in variants:
        if not isinstance(item, dict):
            raise PromptAblationRunError("블라인드 평가 후보 판정이 객체가 아닙니다.")
        candidate_id = item.get("candidate_id")
        if candidate_id not in candidate_ids or candidate_id in seen:
            raise PromptAblationRunError("블라인드 평가 candidate_id가 유효하지 않습니다.")
        seen.add(candidate_id)
    preferred = payload["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or not preferred
        or len(preferred) > 2
        or len(set(preferred)) != len(preferred)
        or any(item not in candidate_ids for item in preferred)
    ):
        raise PromptAblationRunError("선호 후보 판정이 유효하지 않습니다.")
    if not isinstance(payload["conclusion"], str) or not payload["conclusion"].strip():
        raise PromptAblationRunError("블라인드 평가 결론이 비어 있습니다.")
    return payload


def _write_json(path: Path, payload: Any) -> Path:
    return TRACE._atomic_json(path, payload)


def _render_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# PROMPT 입력 구조 실제 비교",
        "",
        f"원본 실행: `{report['run_id']}`",
        f"모델: `{report['profile']['model']}` · reasoning `{report['profile']['reasoning_effort']}`",
        "",
        "## 구조 지표",
        "",
        "| 변형 | 문자 | 제목 | 규칙 표현 | 안전 문구 | 반복 쌍 | 조건 토큰 보존 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANT_ORDER:
        if variant not in report["results"]:
            continue
        metrics = report["results"][variant]["metrics"]
        lines.append(
            f"| `{variant}` | {metrics['characters']} | {metrics['headings']} | "
            f"{metrics['rule_marker_hits']} | {metrics['safety_marker_hits']} | "
            f"{metrics['duplicate_pair_count']} | "
            f"{metrics['average_constraint_token_coverage']:.0%} |"
        )
    lines.extend(["", "## 블라인드 평가", ""])
    assessment = report.get("assessment")
    if isinstance(assessment, dict):
        reverse = report["candidate_mapping"]
        preferred = [
            f"`{reverse[candidate_id]}`"
            for candidate_id in assessment["preferred_candidate_ids"]
        ]
        lines.append("선호 변형: " + ", ".join(preferred))
        lines.append("")
        lines.append(str(assessment["conclusion"]))
        lines.append("")
        by_id = {item["candidate_id"]: item for item in assessment["variants"]}
        for candidate_id, variant in reverse.items():
            item = by_id[candidate_id]
            lines.append(
                f"- **`{variant}`**: 조건 {item['requirement_preservation']} · "
                f"절차 {item['procedure_clarity']} · 반복 {item['repetition_pressure']} · "
                f"형식 {item['format_pressure']} · 재사용 {item['practical_reusability']} — "
                f"{item['finding']}"
            )
    else:
        lines.append("- 블라인드 평가를 실행하지 않았거나 실패했습니다. 구조 지표만 비교할 수 있습니다.")
    lines.extend(
        [
            "",
            "## 해석 경계",
            "",
            "이 비교는 생성된 프롬프트 자체를 평가합니다. 실제 차트 이미지에 각 프롬프트를 적용한 매매 판단 품질은 별도의 적용 실험이 필요합니다.",
            "",
        ]
    )
    return "\n".join(lines)


def run_prompt_ablation(
    run_dir: Path,
    *,
    workspace: Path = ROOT,
    variants: Sequence[str] | None = None,
    judge: bool = True,
    force: bool = False,
    timeout_seconds: int = 600,
    engine: Any | None = None,
    profile_override: Any | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    workspace = workspace.expanduser().resolve()
    selected = tuple(variants or VARIANT_ORDER)
    unknown = sorted(set(selected) - set(VARIANT_ORDER))
    if unknown:
        raise PromptAblationRunError("알 수 없는 비교 변형: " + ", ".join(unknown))
    if len(selected) < 2:
        raise PromptAblationRunError("비교에는 최소 두 변형이 필요합니다.")

    experiment = ABLATION.build_prompt_ablation_variants(run_dir)
    if experiment is None:
        raise PromptAblationRunError("PROMPT 경로 run이 아닙니다.")
    ABLATION.write_prompt_ablation_variants(run_dir, experiment)
    prompts = experiment["variants"]
    request = TRACE._read_text(run_dir / "request.txt", "request.txt").strip()
    ledger = TRACE._read_json(run_dir / "goal_ledger.json", "goal_ledger.json")
    constraints = ledger.get("fixed_constraints")
    if not isinstance(constraints, list):
        constraints = []
    constraints = [item for item in constraints if isinstance(item, str)]

    profile = profile_override or _actual_prompt_profile(run_dir)
    if profile.sandbox != "read-only":
        raise PromptAblationRunError("비교 실행은 read-only profile만 허용합니다.")
    runtime_engine = engine or OS.CodexEngine(
        workspace,
        enable_search=profile.web_search,
        timeout_seconds=timeout_seconds,
    )
    capabilities = runtime_engine.capabilities()
    if not capabilities.ai_reasoning:
        raise PromptAblationRunError(
            capabilities.detail or "같은 PROMPT 모델을 실행할 capability가 없습니다."
        )
    if profile.web_search and not capabilities.web_search:
        raise PromptAblationRunError("원래 PROMPT 프로필의 web search capability가 없습니다.")

    output_root = run_dir / "prompt_ablation" / "executions"
    output_root.mkdir(parents=True, exist_ok=True)
    results_dir = run_dir / "prompt_ablation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    original = _original_execution(run_dir)

    for variant in selected:
        normalized_path = results_dir / f"{variant}.json"
        markdown_path = results_dir / f"{variant}.md"
        source = "original_execution" if variant == "current" else "ablation_execution"
        if normalized_path.is_file() and markdown_path.is_file() and not force:
            execution = _read_json(normalized_path, normalized_path.name)
        elif variant == "current":
            execution = original
            _write_json(normalized_path, execution)
            markdown_path.write_text(
                str(execution["result_markdown"]).rstrip() + "\n",
                encoding="utf-8",
            )
        else:
            invocation = OS.InvocationSpec(
                name=f"ablation-{variant}",
                phase="executor",
                route="PROMPT",
                profile=profile,
                schema_path=OS.EXECUTION_SCHEMA_PATH,
            )
            raw = runtime_engine.execute(prompts[variant], output_root, invocation)
            execution = OS.validate_execution_output(
                raw,
                "PROMPT",
                profile,
                capabilities,
            )
            _write_json(normalized_path, execution)
            markdown_path.write_text(
                str(execution["result_markdown"]).rstrip() + "\n",
                encoding="utf-8",
            )
        result_markdown = str(execution["result_markdown"]).strip()
        results[variant] = {
            "source": source,
            "result_path": markdown_path.relative_to(run_dir).as_posix(),
            "execution_path": normalized_path.relative_to(run_dir).as_posix(),
            "result_markdown": result_markdown,
            "metrics": _output_metrics(result_markdown, request, constraints),
        }

    mapping = _candidate_mapping(run_dir.name, selected)
    assessment: dict[str, Any] | None = None
    assessment_error: str | None = None
    if judge:
        assessment_path = results_dir / "blind_assessment.json"
        if assessment_path.is_file() and not force:
            assessment = _validate_assessment(
                _read_json(assessment_path, assessment_path.name),
                set(mapping),
            )
        else:
            try:
                invocation = OS.InvocationSpec(
                    name="ablation-blind-assessment",
                    phase="assessment",
                    route=None,
                    profile=profile,
                    schema_path=ASSESSMENT_SCHEMA_PATH,
                )
                raw_assessment = runtime_engine.execute(
                    _judge_prompt(request, ledger, mapping, results),
                    output_root,
                    invocation,
                )
                assessment = _validate_assessment(raw_assessment, set(mapping))
                _write_json(assessment_path, assessment)
            except (OS.ProblemSolvingError, PromptAblationRunError) as exc:
                assessment_error = str(exc)

    report = {
        "version": 1,
        "run_id": run_dir.name,
        "profile": {
            "model": profile.model,
            "reasoning_effort": profile.reasoning_effort,
            "web_search": profile.web_search,
            "sandbox": profile.sandbox,
        },
        "selected_variants": list(selected),
        "candidate_mapping": mapping,
        "results": results,
        "assessment": assessment,
        "assessment_error": assessment_error,
        "original_result_preserved": True,
        "comparison_boundary": (
            "현재 단계는 생성된 프롬프트를 비교하며 실제 차트 적용 결과는 비교하지 않습니다."
        ),
    }
    report_path = _write_json(
        run_dir / "prompt_ablation" / "comparison.json",
        report,
    )
    markdown_report = run_dir / "prompt_ablation" / "comparison.md"
    markdown_report.write_text(_render_report(report), encoding="utf-8")
    return {
        "version": 1,
        "report_path": report_path.relative_to(run_dir).as_posix(),
        "markdown_path": markdown_report.relative_to(run_dir).as_posix(),
        "selected_variants": list(selected),
        "assessment_completed": assessment is not None,
        "assessment_error": assessment_error,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument(
        "--variant",
        action="append",
        choices=VARIANT_ORDER,
        default=[],
        help="실행할 변형. 생략하면 네 변형 전체를 비교합니다.",
    )
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        record = run_prompt_ablation(
            args.run_dir,
            workspace=args.workspace,
            variants=args.variant or None,
            judge=not args.no_judge,
            force=args.force,
            timeout_seconds=args.timeout_seconds,
        )
    except (PromptAblationRunError, OS.ProblemSolvingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(args.run_dir / record["markdown_path"])
    if record["assessment_error"]:
        print(f"평가 경고: {record['assessment_error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
