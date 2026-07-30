#!/usr/bin/env python3
"""Audit PROMPT generation as parallel request branches that converge at the executor."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"


def _load_trace() -> Any:
    spec = importlib.util.spec_from_file_location(
        "psos_prompt_trace_for_causal_audit",
        TRACE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prompt trace module: {TRACE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TRACE = _load_trace()


class PromptCausalAuditError(ValueError):
    """Raised when the actual convergence structure cannot be reconstructed."""


def _token_set(text: str) -> set[str]:
    return set(TRACE._tokens(text))


def _coverage(source: str, target: str) -> float:
    source_tokens = _token_set(source)
    if not source_tokens:
        return 0.0
    return round(len(source_tokens & _token_set(target)) / len(source_tokens), 3)


def _remove_once(text: str, fragment: str) -> str:
    if not fragment:
        return text
    position = text.find(fragment)
    if position < 0:
        return text
    return text[:position] + text[position + len(fragment) :]


def _stage_metrics(trace: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(stage["id"]): stage["metrics"]
        for stage in trace.get("stages", [])
        if isinstance(stage, Mapping) and isinstance(stage.get("metrics"), Mapping)
    }


def build_prompt_generation_causal_audit(
    run_dir: Path,
    execution_override: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    run_dir = run_dir.expanduser().resolve()
    trace = TRACE.build_prompt_generation_trace(run_dir, execution_override)
    if trace is None:
        return None

    request = TRACE._read_text(run_dir / "request.txt", "request.txt").strip()
    ledger = TRACE._read_json(run_dir / "goal_ledger.json", "goal_ledger.json")
    executor_path = run_dir / trace["sources"]["executor_request"]
    executor_input = TRACE._read_text(executor_path, executor_path.name)
    baseline = TRACE._extract_json_after_marker(executor_input, TRACE.PROMPT_MARKER)
    if baseline is None:
        raise PromptCausalAuditError("PROMPT 실행기 입력에서 baseline을 복원하지 못했습니다.")
    baseline_prompt = str(baseline.get("final_prompt") or "").strip()
    if not baseline_prompt:
        raise PromptCausalAuditError("baseline final_prompt가 비어 있습니다.")

    ledger_text = TRACE._ledger_text(ledger)
    ledger_json = json.dumps(ledger, ensure_ascii=False, indent=2)
    baseline_json = json.dumps(baseline, ensure_ascii=False, indent=2)

    shell = executor_input
    shell = _remove_once(shell, baseline_json)
    shell = _remove_once(shell, ledger_json)
    shell = _remove_once(shell, request)

    stage_metrics = _stage_metrics(trace)
    final_metrics = stage_metrics.get("final_prompt", {})
    executor_metrics = stage_metrics.get("executor_input", {})
    request_occurrences = executor_input.count(request)
    attribution_counts = Counter(
        str(item.get("source", "unknown"))
        for item in trace.get("final_clause_attribution", [])
        if isinstance(item, Mapping)
    )

    branches = {
        "request": {
            "characters": len(request),
            "role": "original_user_intent",
        },
        "goal_ledger": {
            "characters": len(ledger_text),
            "role": "goal_and_constraint_restatement",
            "request_token_coverage": _coverage(request, ledger_text),
        },
        "prompt_compiler_baseline": {
            "characters": len(baseline_prompt),
            "role": "reusable_prompt_scaffold",
            "request_token_coverage": _coverage(request, baseline_prompt),
        },
        "executor_shell": {
            "characters": len(shell),
            "role": "route_and_execution_contract",
        },
    }
    convergence = {
        "executor_input_characters": int(executor_metrics.get("characters", len(executor_input))),
        "component_character_sum": sum(item["characters"] for item in branches.values()),
        "exact_request_occurrences": request_occurrences,
        "request_duplicate_characters": max(request_occurrences - 1, 0) * len(request),
        "contains_goal_ledger": "[Goal Ledger]" in executor_input,
        "contains_raw_request": "[사용자 요청]" in executor_input,
        "contains_compiler_baseline": TRACE.PROMPT_MARKER in executor_input,
    }

    edges = [
        {
            "from": "request",
            "to": "goal_ledger",
            "kind": "parallel_transformation",
            **TRACE._transition(request, ledger_text),
        },
        {
            "from": "request",
            "to": "prompt_compiler_baseline",
            "kind": "parallel_transformation",
            **TRACE._transition(request, baseline_prompt),
        },
        {
            "from": "executor_input",
            "to": "final_prompt",
            "kind": "model_generation",
            **TRACE._transition(executor_input, str(execution_override.get("result_markdown") if isinstance(execution_override, Mapping) else "") or TRACE._find_execution_output(run_dir, executor_path)[1]["result_markdown"]),
        },
    ]

    findings: list[dict[str, str]] = []
    if all(
        convergence[key]
        for key in (
            "contains_goal_ledger",
            "contains_raw_request",
            "contains_compiler_baseline",
        )
    ):
        findings.append(
            {
                "code": "parallel-branches-converge-uncompressed",
                "stage": "executor_input",
                "finding": (
                    "원문에서 병렬 생성된 Goal Ledger와 Prompt Compiler baseline이 원문과 함께 "
                    "요약·대표본 선택 없이 PROMPT 실행기 입력에 합류합니다."
                ),
            }
        )
    if request_occurrences >= 2:
        findings.append(
            {
                "code": "raw-request-duplicated-at-convergence",
                "stage": "executor_input",
                "finding": (
                    f"동일한 사용자 원문이 실행기 입력에 정확히 {request_occurrences}회 포함됩니다. "
                    "baseline 내부 원문과 별도 사용자 요청 블록이 중복됩니다."
                ),
            }
        )
    if branches["goal_ledger"]["request_token_coverage"] >= 0.45:
        findings.append(
            {
                "code": "ledger-restates-request",
                "stage": "goal_ledger",
                "finding": (
                    "Goal Ledger가 원문의 상당 부분을 다시 표현하므로 합류 시 새 정보와 "
                    "의도 보존용 반복을 구분하기 어렵습니다."
                ),
            }
        )
    if branches["prompt_compiler_baseline"]["request_token_coverage"] >= 0.65:
        findings.append(
            {
                "code": "baseline-embeds-request",
                "stage": "prompt_compiler_baseline",
                "finding": "Prompt Compiler baseline이 사용자 원문을 거의 그대로 포함합니다.",
            }
        )
    output_ratio = float(edges[-1]["character_ratio"])
    if output_ratio >= 1.5:
        findings.append(
            {
                "code": "executor-amplifies-converged-input",
                "stage": "executor_input→final_prompt",
                "finding": (
                    f"최종 모델이 이미 중복된 실행기 입력을 다시 {output_ratio}배로 확장합니다. "
                    "입력 합류가 원인 표면이고 최종 생성기는 형식·규칙 증폭기로 작동합니다."
                ),
            }
        )
    if int(final_metrics.get("headings", 0)) >= 8:
        findings.append(
            {
                "code": "formatting-is-output-amplifier",
                "stage": "final_prompt",
                "finding": (
                    f"최종 프롬프트에 제목이 {final_metrics.get('headings', 0)}개 생겨, "
                    "합류된 요구가 판단 위계보다 문서 섹션으로 전개됩니다."
                ),
            }
        )

    return {
        "version": 1,
        "run_id": run_dir.name,
        "topology": {
            "description": "request branches into ledger and baseline, then all surfaces converge at the executor",
            "nodes": [
                "request",
                "goal_ledger",
                "prompt_compiler_baseline",
                "executor_shell",
                "executor_input",
                "final_prompt",
            ],
            "edges": edges,
        },
        "branches": branches,
        "convergence": convergence,
        "final_output": {
            "characters": int(final_metrics.get("characters", 0)),
            "headings": int(final_metrics.get("headings", 0)),
            "rule_marker_hits": int(final_metrics.get("rule_marker_hits", 0)),
            "safety_marker_hits": int(final_metrics.get("safety_marker_hits", 0)),
            "duplicate_pair_count": len(trace.get("final_prompt_duplicate_pairs", [])),
            "clause_attribution_counts": dict(sorted(attribution_counts.items())),
        },
        "causal_findings": findings,
        "interpretation_boundary": (
            "이 감사는 입력 표면의 중복과 출력 팽창을 관찰합니다. 실제 모델 출력 비교 없이 "
            "각 입력 요소를 제거했을 때 품질이 좋아진다고 단정하지 않습니다."
        ),
    }


def render_prompt_generation_causal_audit(audit: Mapping[str, Any]) -> str:
    branches = audit["branches"]
    convergence = audit["convergence"]
    output = audit["final_output"]
    lines = [
        "# PROMPT 생성 인과 구조 감사",
        "",
        f"실행: `{audit['run_id']}`",
        "",
        "## 실제 토폴로지",
        "",
        "```text",
        "사용자 원문 ─┬→ Goal Ledger ─────────────┐",
        "              ├→ Prompt Compiler baseline ├→ PROMPT 실행기 입력 → 최종 프롬프트",
        "              └───────────────────────────┘",
        "실행기 공통 규칙 ─────────────────────────┘",
        "```",
        "",
        "Ledger와 baseline은 앞뒤 단계가 아니라 원문에서 갈라지는 병렬 산출물이다.",
        "",
        "## 합류 전 구성요소",
        "",
        "| 구성요소 | 문자 수 | 원문 토큰 포함률 | 역할 |",
        "|---|---:|---:|---|",
    ]
    for key in ("request", "goal_ledger", "prompt_compiler_baseline", "executor_shell"):
        item = branches[key]
        coverage = item.get("request_token_coverage")
        coverage_text = "-" if coverage is None else f"{coverage:.0%}"
        lines.append(
            f"| {key} | {item['characters']} | {coverage_text} | {item['role']} |"
        )
    lines.extend(
        [
            "",
            "## 합류와 최종 팽창",
            "",
            f"- 실행기 입력: **{convergence['executor_input_characters']}자**",
            f"- 동일한 원문 포함 횟수: **{convergence['exact_request_occurrences']}회**",
            f"- 최종 프롬프트: **{output['characters']}자**",
            f"- 최종 제목: **{output['headings']}개**",
            f"- 규칙 표지: **{output['rule_marker_hits']}회**",
            f"- 안전 문구: **{output['safety_marker_hits']}회**",
            "",
            "## 관찰된 구조적 원인",
            "",
        ]
    )
    findings = audit.get("causal_findings", [])
    if findings:
        for item in findings:
            lines.append(f"- **{item['code']}** · `{item['stage']}`: {item['finding']}")
    else:
        lines.append("- 자동 감사에서 뚜렷한 합류·증폭 신호를 찾지 못했습니다.")
    lines.extend(
        [
            "",
            "## 해석 경계",
            "",
            str(audit["interpretation_boundary"]),
            "",
        ]
    )
    return "\n".join(lines)


def write_prompt_generation_causal_audit(
    run_dir: Path,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    json_path = TRACE._atomic_json(run_dir / "prompt_generation_causal_audit.json", audit)
    markdown_path = run_dir / "prompt_generation_causal_audit.md"
    markdown_path.write_text(
        render_prompt_generation_causal_audit(audit),
        encoding="utf-8",
    )
    return {
        "version": 1,
        "json_path": json_path.name,
        "markdown_path": markdown_path.name,
        "finding_count": len(audit.get("causal_findings", [])),
    }


def attach_prompt_generation_causal_audit(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    execution = payload.get("execution")
    audit = build_prompt_generation_causal_audit(
        run_dir,
        execution if isinstance(execution, Mapping) else None,
    )
    if audit is None:
        return None
    record = write_prompt_generation_causal_audit(run_dir, audit)
    payload["prompt_generation_causal_audit"] = record
    if isinstance(payload.get("run"), dict):
        payload["run"]["prompt_generation_causal_audit"] = record
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        audit = build_prompt_generation_causal_audit(args.run_dir)
        if audit is None:
            print("PROMPT 경로가 아니므로 인과 감사 파일을 만들지 않았습니다.")
            return 0
        record = write_prompt_generation_causal_audit(args.run_dir, audit)
    except (PromptCausalAuditError, TRACE.PromptTraceError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(args.run_dir / record["markdown_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
