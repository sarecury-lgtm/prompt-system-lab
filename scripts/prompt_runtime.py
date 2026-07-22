#!/usr/bin/env python3
"""Create one ready-to-use prompt with conservative routing and fallbacks."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "scripts" / "prompt_mode_compare.py"
DEFAULT_RESULTS_DIR = ROOT / "runtime-results"

PATTERN_INSTRUCTIONS = {
    "Role + Task Frame": "역할, 실제 목표, 고정 제약, 필요한 산출물을 분명히 구분하세요.",
    "Interface Emulation": "모의 인터페이스 출력임을 명시하고 실제 실행 결과처럼 표현하지 마세요.",
    "Prompt Improvement Loop": "초안의 누락과 모호함을 점검하고 수정한 뒤 요구사항 충족 여부를 다시 확인하세요.",
    "Defensive Jailbreak Analysis": "공격 메커니즘만 방어적으로 분류하고 실행 가능한 우회 문구를 복원하거나 개선하지 마세요.",
    "Grounded Research": "출처를 확인하고 주장에 근거를 연결하며 사실·추론·불확실성을 구분하세요.",
    "Structured Output / Extraction": "필수 필드, 값이 없을 때의 처리, 근거 규칙과 정확한 출력 형식을 정의하세요.",
    "Evaluation Rubric": "관찰 가능한 기준, 점수 기준점, 통과·실패 규칙과 실패 예시를 사용하세요.",
    "Persistent Project Instruction": "트리거, 기본 행동, 우선순위, 경계와 fallback을 명시하세요.",
    "Coding-Agent Workflow": "관련 맥락을 확인하고 가장 작은 안전한 변경을 한 뒤 검증하고 변경 내용을 요약하세요.",
}


class RuntimeFailure(Exception):
    """A recoverable runtime-stage failure."""


def load_router() -> Any:
    spec = importlib.util.spec_from_file_location("prompt_mode_compare", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeFailure(f"라우터를 불러올 수 없습니다: {ROUTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_context_files(paths: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    contexts: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve(strict=True)
            contexts.append({"path": str(resolved), "content": resolved.read_text(encoding="utf-8")})
        except Exception as exc:  # Context failure must not suppress the prompt.
            errors.append({"stage": "context-read", "path": str(path), "error": str(exc)})
    return contexts, errors


def context_block(contexts: list[dict[str, str]]) -> str:
    if not contexts:
        return ""
    parts = []
    for item in contexts:
        parts.append(f"--- {item['path']} ---\n{item['content'].strip()}")
    return "\n\n[추가 문맥]\n" + "\n\n".join(parts)


def build_baseline(request: str, contexts: list[dict[str, str]]) -> str:
    if os.environ.get("PROMPT_RUNTIME_TEST_FAIL_BASELINE") == "1":
        raise RuntimeFailure("강제 baseline 생성 실패")
    return (
        "다음 사용자 요청을 수행하세요. 요청에 명시된 목표, 제약과 산출물을 보존하세요.\n\n"
        f"[사용자 요청]\n{request.strip()}"
        f"{context_block(contexts)}"
    ).strip()


def normalize_patterns(patterns: list[str]) -> list[str]:
    lookup = {name.casefold(): name for name in PATTERN_INSTRUCTIONS}
    normalized: list[str] = []
    for value in patterns:
        canonical = lookup.get(str(value).casefold())
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def build_pattern_only(baseline: str, patterns: list[str]) -> str:
    if os.environ.get("PROMPT_RUNTIME_TEST_FAIL_PATTERN") == "1":
        raise RuntimeFailure("강제 pattern-only 생성 실패")
    normalized = normalize_patterns(patterns)
    if not normalized:
        raise RuntimeFailure("적용 가능한 기존 패턴이 없습니다")
    instructions = "\n".join(
        f"- {PATTERN_INSTRUCTIONS[name]}" for name in normalized
    )
    return f"{baseline}\n\n[수행 및 출력 규칙]\n{instructions}".strip()


def active_policy(router: Any, source_id: str) -> dict[str, Any]:
    registry = router.load_active_source_policies()
    return next(item for item in registry["sources"] if item["source_id"] == source_id)


def build_active(pattern_prompt: str, router: Any, sources: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    if os.environ.get("PROMPT_RUNTIME_TEST_FAIL_ACTIVE") == "1":
        raise RuntimeFailure("강제 active 생성 실패")
    if len(sources) != 1:
        raise RuntimeFailure("active source는 요청당 정확히 1개여야 합니다")
    policy = active_policy(router, sources[0]["source_id"])
    rules = [policy["unique_behavior"], *policy["required_prompt_changes"]]
    rendered = "\n".join(f"- {rule}" for rule in rules)
    return (
        f"{pattern_prompt}\n\n[작업별 추가 규칙]\n{rendered}".strip(),
        [{"source_id": policy["source_id"], "name": sources[0].get("name", "")}],
    )


def active_contributes(pattern_prompt: str, active_prompt: str, router: Any, source_id: str) -> tuple[bool, str]:
    if os.environ.get("PROMPT_RUNTIME_TEST_FAIL_EVALUATION") == "1":
        raise RuntimeFailure("강제 active 기여 평가 실패")
    policy = active_policy(router, source_id)
    additions = [policy["unique_behavior"], *policy["required_prompt_changes"]]
    unique = active_prompt != pattern_prompt and all(item in active_prompt for item in additions)
    return unique, (
        "active source의 고유 행동과 필수 프롬프트 변화가 모두 추가됨"
        if unique else "active source가 pattern-only에 없는 고유 기여를 추가하지 못함"
    )


def fallback_route(request: str, router: Any | None) -> tuple[str, list[str], str]:
    if router is None:
        return "baseline", [], "라우팅 실패로 안전한 baseline 유지"
    patterns = normalize_patterns(router.hinted_patterns(request))
    if patterns:
        return "pattern-only", patterns, "라우팅 실패 후 기존 패턴 신호만 사용"
    return "baseline", [], "라우팅 실패 후 적용 가능한 패턴 신호가 없어 baseline 유지"


def create_prompt(request: str, context_paths: list[Path] | None = None, tools_allowed: bool = False) -> dict[str, Any]:
    if not request or not request.strip():
        raise ValueError("사용자 요청은 비어 있을 수 없습니다")
    started = dt.datetime.now(dt.timezone.utc)
    contexts, errors = read_context_files(context_paths or [])
    router: Any | None = None
    route_record: dict[str, Any] = {}
    route_detail: dict[str, Any] = {}

    try:
        baseline = build_baseline(request, contexts)
    except Exception as exc:
        # There is no useful prior prompt to fall back to.
        raise RuntimeFailure(f"baseline 프롬프트 생성 실패: {exc}") from exc

    try:
        router = load_router()
        documents = router.load_documents()
        token_index, idf = router.build_index(documents)
        public = {
            "user_request": request.strip(),
            "initial_information": [item["content"] for item in contexts],
            "initial_conditions": [],
            "tools_allowed": tools_allowed,
        }
        route_record, route_detail = router.route_request(
            "runtime-request", public, documents, 1, token_index, idf
        )
        requested_mode = route_record["selected_mode"]
        # Context may contain unrelated repository prose. It informs routing and
        # the final prompt, but pattern selection stays anchored to the request.
        patterns = normalize_patterns(router.hinted_patterns(request))
        reason = route_record["selection_reason"]
    except Exception as exc:
        errors.append({"stage": "routing", "error": str(exc)})
        requested_mode, patterns, reason = fallback_route(request, router)
        route_record = {"selected_mode": requested_mode, "selection_reason": reason, "used_sources": []}

    final_prompt = baseline
    final_mode = "baseline"
    fallback = bool(route_record.get("fallback"))
    fallback_reasons: list[str] = []
    if route_record.get("fallback"):
        fallback_reasons.append(reason)
    used_sources: list[dict[str, Any]] = []

    pattern_prompt: str | None = None
    if requested_mode in {"pattern-only", "active"}:
        try:
            pattern_prompt = build_pattern_only(baseline, patterns)
            final_prompt = pattern_prompt
            final_mode = "pattern-only"
        except Exception as exc:
            fallback = True
            message = f"pattern-only 생성 실패로 baseline 복귀: {exc}"
            fallback_reasons.append(message)
            errors.append({"stage": "pattern-generation", "error": str(exc)})
            reason = message

    if requested_mode == "active" and pattern_prompt is not None:
        candidates = route_record.get("used_sources") or []
        try:
            active_prompt, active_sources = build_active(pattern_prompt, router, candidates)
            keep, evaluation_reason = active_contributes(
                pattern_prompt, active_prompt, router, active_sources[0]["source_id"]
            )
            if keep:
                final_prompt = active_prompt
                final_mode = "active"
                used_sources = active_sources
                reason = f"{reason}; {evaluation_reason}"
            else:
                fallback = True
                fallback_reasons.append(evaluation_reason)
                reason = evaluation_reason
        except Exception as exc:
            fallback = True
            message = f"active 생성·평가 실패로 pattern-only 복귀: {exc}"
            fallback_reasons.append(message)
            errors.append({"stage": "active-generation-or-evaluation", "error": str(exc)})
            reason = message

    finished = dt.datetime.now(dt.timezone.utc)
    return {
        "version": "0.1",
        "request": request.strip(),
        "context_files": [item["path"] for item in contexts],
        "tools_allowed": tools_allowed,
        "final_prompt": final_prompt,
        "selected_mode": final_mode,
        "selection_reason": reason,
        "used_patterns": patterns if final_mode != "baseline" else [],
        "used_active_sources": used_sources,
        "fallback": fallback,
        "fallback_reason": "; ".join(fallback_reasons),
        "errors": errors,
        "routing": {"record": route_record, "detail": route_detail},
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
    }


def output_paths(output: Path | None) -> tuple[Path, Path]:
    if output is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = DEFAULT_RESULTS_DIR / stamp
        return run_dir / "prompt.txt", run_dir / "routing.json"
    prompt_path = output.expanduser().resolve()
    return prompt_path, prompt_path.with_name(f"{prompt_path.stem}.routing.json")


def save_results(result: dict[str, Any], output: Path | None) -> tuple[Path | None, Path | None, list[str]]:
    prompt_path, record_path = output_paths(output)
    save_errors: list[str] = []
    saved_prompt: Path | None = None
    saved_record: Path | None = None
    try:
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(result["final_prompt"] + "\n", encoding="utf-8")
        saved_prompt = prompt_path
    except Exception as exc:
        save_errors.append(f"최종 프롬프트 저장 실패: {exc}")
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        saved_record = record_path
    except Exception as exc:
        save_errors.append(f"라우팅 기록 저장 실패: {exc}")
    return saved_prompt, saved_record, save_errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="프롬프트로 바꿀 사용자 요청")
    parser.add_argument(
        "--context", type=Path, action="append", default=[], metavar="FILE",
        help="함께 넣을 UTF-8 문맥 파일(여러 번 사용 가능)",
    )
    parser.add_argument("--output", type=Path, help="최종 프롬프트를 저장할 파일 경로")
    parser.add_argument(
        "--tools-allowed", action="store_true",
        help="대상 모델이 파일·명령 도구를 실제로 사용할 수 있음을 표시",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        result = create_prompt(args.request, args.context, args.tools_allowed)
    except (ValueError, RuntimeFailure) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    prompt_path, record_path, save_errors = save_results(result, args.output)
    print(f"모드: {result['selected_mode']}")
    print(f"이유: {result['selection_reason']}")
    print(f"패턴: {', '.join(result['used_patterns']) or '없음'}")
    print("active source: " + (", ".join(item["source_id"] for item in result["used_active_sources"]) or "없음"))
    print(f"fallback: {'예' if result['fallback'] else '아니요'}")
    if result["fallback_reason"]:
        print(f"fallback 이유: {result['fallback_reason']}")
    print(f"최종 프롬프트: {prompt_path or '저장 실패—아래 내용을 사용하세요'}")
    print(f"상세 기록: {record_path or '저장 실패'}")
    for message in save_errors:
        print(f"WARNING: {message}", file=sys.stderr)
    if prompt_path is None:
        print("\n--- 최종 프롬프트 ---\n" + result["final_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
