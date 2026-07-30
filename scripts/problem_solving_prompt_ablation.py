#!/usr/bin/env python3
"""Generate controlled PROMPT executor-input variants without changing the original run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"


def _load_trace() -> Any:
    spec = importlib.util.spec_from_file_location(
        "psos_prompt_trace_for_ablation",
        TRACE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prompt trace module: {TRACE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TRACE = _load_trace()


class PromptAblationError(ValueError):
    """Raised when a PROMPT input cannot be safely decomposed."""


def _remove_block(text: str, heading: str, content: str) -> str:
    candidates = (
        f"\n\n{heading}\n{content}",
        f"{heading}\n{content}\n\n",
        f"{heading}\n{content}",
    )
    for candidate in candidates:
        if candidate in text:
            return text.replace(candidate, "", 1)
    raise PromptAblationError(f"실행기 입력에서 {heading} 블록을 찾지 못했습니다.")


def _compiler_guidance(baseline_prompt: str) -> str:
    markers = ("[수행 및 출력 규칙]", "[작업별 추가 규칙]")
    positions = [baseline_prompt.find(marker) for marker in markers]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return ""
    guidance = baseline_prompt[min(positions) :].strip()
    guidance = re.sub(r"\n{3,}", "\n\n", guidance)
    return guidance


def _compact_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "goal": ledger.get("current_goal_hypothesis"),
        "fixed_constraints": ledger.get("fixed_constraints", []),
        "completion_condition": ledger.get("completion_condition"),
    }


def _single_brief(ledger: Mapping[str, Any], baseline: Mapping[str, Any]) -> str:
    constraints = ledger.get("fixed_constraints")
    if not isinstance(constraints, list):
        constraints = []
    constraint_text = "\n".join(
        f"- {item}" for item in constraints if isinstance(item, str) and item.strip()
    )
    baseline_prompt = str(baseline.get("final_prompt") or "")
    guidance = _compiler_guidance(baseline_prompt)
    used_patterns = baseline.get("used_patterns")
    if not isinstance(used_patterns, list):
        used_patterns = []
    pattern_text = ", ".join(str(item) for item in used_patterns if str(item).strip())
    sections = [
        "[Prompt Build Brief]",
        f"목표: {str(ledger.get('current_goal_hypothesis') or '').strip()}",
        "",
        "고정 조건:",
        constraint_text or "- 없음",
        "",
        f"완료 조건: {str(ledger.get('completion_condition') or '').strip()}",
    ]
    if pattern_text:
        sections.extend(["", f"적용 패턴: {pattern_text}"])
    if guidance:
        sections.extend(["", guidance])
    sections.extend(
        [
            "",
            "위 brief의 의미를 보존하되 같은 요구를 여러 규칙이나 출력 섹션으로 반복하지 마라.",
            "먼저 핵심 작업 절차를 정하고, 보조 규칙과 안전 규칙은 그 절차에 종속시켜라.",
        ]
    )
    return "\n".join(sections).strip()


def build_prompt_ablation_variants(run_dir: Path) -> dict[str, Any] | None:
    run_dir = run_dir.expanduser().resolve()
    route = TRACE._read_json(run_dir / "route.json", "route.json")
    selected = route.get("selected_route")
    prompt_in_route = selected == "PROMPT" or (
        selected == "HYBRID"
        and "PROMPT" in {route.get("primary_route"), route.get("secondary_route")}
    )
    if not prompt_in_route:
        return None

    request = TRACE._read_text(run_dir / "request.txt", "request.txt").strip()
    ledger = TRACE._read_json(run_dir / "goal_ledger.json", "goal_ledger.json")
    executor_path = TRACE._find_executor_request(run_dir)
    current = TRACE._read_text(executor_path, executor_path.name).strip()
    baseline = TRACE._extract_json_after_marker(current, TRACE.PROMPT_MARKER)
    if baseline is None:
        raise PromptAblationError("PROMPT 실행기 입력에서 baseline을 복원하지 못했습니다.")

    ledger_json = json.dumps(ledger, ensure_ascii=False, indent=2)
    baseline_json = json.dumps(baseline, ensure_ascii=False, indent=2)
    shell = current
    shell = _remove_block(shell, "[기존 Prompt Compiler baseline]", baseline_json)
    shell = _remove_block(shell, "[사용자 요청]", request)
    shell = _remove_block(shell, "[Goal Ledger]", ledger_json)
    shell = shell.strip()

    compact_json = json.dumps(_compact_ledger(ledger), ensure_ascii=False, indent=2)
    variants = {
        "current": current,
        "without_raw_request": (
            f"{shell}\n\n[Goal Ledger]\n{ledger_json}"
            f"\n\n[기존 Prompt Compiler baseline]\n{baseline_json}"
        ),
        "compact_ledger": (
            f"{shell}\n\n[Compact Goal Contract]\n{compact_json}"
            f"\n\n[기존 Prompt Compiler baseline]\n{baseline_json}"
        ),
        "single_build_brief": f"{shell}\n\n{_single_brief(ledger, baseline)}",
    }

    metadata = {}
    for name, prompt in variants.items():
        metadata[name] = {
            "characters": len(prompt),
            "exact_request_occurrences": prompt.count(request),
            "contains_full_goal_ledger": ledger_json in prompt,
            "contains_full_compiler_baseline": baseline_json in prompt,
            "contains_single_build_brief": "[Prompt Build Brief]" in prompt,
        }
    return {
        "version": 1,
        "run_id": run_dir.name,
        "source_executor_request": executor_path.name,
        "variants": variants,
        "metadata": metadata,
        "experiment_contract": {
            "constant": (
                "같은 모델·reasoning·출력 schema를 사용하고 입력 합류 구조만 바꾼다. "
                "각 결과는 별도 파일에 저장하며 원래 run을 덮어쓰지 않는다."
            ),
            "compare": [
                "요청 조건 누락 여부",
                "핵심 작업 절차가 먼저 보이는지",
                "제목·규칙·안전 문구 수",
                "동일 의미 반복",
                "실제 입력에 적용했을 때 양식 채우기 성향",
            ],
            "boundary": (
                "이 파일 생성만으로 어느 변형이 더 좋은지 결론내리지 않는다. "
                "같은 실행 모델의 실제 출력 비교가 필요하다."
            ),
        },
    }


def write_prompt_ablation_variants(
    run_dir: Path,
    experiment: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    output_dir = run_dir / "prompt_ablation"
    output_dir.mkdir(exist_ok=True)
    variants = experiment["variants"]
    files = {}
    for name, prompt in variants.items():
        path = output_dir / f"{name}.md"
        path.write_text(str(prompt).rstrip() + "\n", encoding="utf-8")
        files[name] = path.relative_to(run_dir).as_posix()
    manifest = {
        key: value
        for key, value in experiment.items()
        if key != "variants"
    }
    manifest["files"] = files
    manifest_path = TRACE._atomic_json(output_dir / "manifest.json", manifest)
    return {
        "version": 1,
        "directory": output_dir.relative_to(run_dir).as_posix(),
        "manifest_path": manifest_path.relative_to(run_dir).as_posix(),
        "files": files,
    }


def attach_prompt_ablation_variants(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    experiment = build_prompt_ablation_variants(run_dir)
    if experiment is None:
        return None
    record = write_prompt_ablation_variants(run_dir, experiment)
    payload["prompt_ablation"] = record
    if isinstance(payload.get("run"), dict):
        payload["run"]["prompt_ablation"] = record
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        experiment = build_prompt_ablation_variants(args.run_dir)
        if experiment is None:
            print("PROMPT 경로가 아니므로 비교 입력을 만들지 않았습니다.")
            return 0
        record = write_prompt_ablation_variants(args.run_dir, experiment)
    except (PromptAblationError, TRACE.PromptTraceError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(args.run_dir / record["manifest_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
