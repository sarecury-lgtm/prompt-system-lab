#!/usr/bin/env python3
"""Trace PROMPT generation after parallel inputs are normalized into one brief."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"
BRIEF_MARKER = "[Prompt Build Brief]"


def _load_trace() -> Any:
    spec = importlib.util.spec_from_file_location(
        "psos_legacy_prompt_trace_for_brief",
        TRACE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prompt trace module: {TRACE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


TRACE = _load_trace()


class PromptBriefTraceError(ValueError):
    """Raised when persisted brief artifacts are incomplete."""


def _read_path(run_dir: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise PromptBriefTraceError(f"{label} 경로가 비어 있습니다.")
    path = (run_dir / relative).resolve()
    try:
        path.relative_to(run_dir)
    except ValueError as exc:
        raise PromptBriefTraceError(f"{label} 경로가 run 밖을 가리킵니다.") from exc
    if not path.is_file():
        raise PromptBriefTraceError(f"{label} 파일이 없습니다: {relative}")
    return path


def _find_final_prompt_executor(run_dir: Path) -> Path:
    candidates: list[Path] = []
    for path in sorted(run_dir.glob("*-request.md")):
        lowered = path.name.casefold()
        if any(
            marker in lowered
            for marker in (
                "router",
                "result-contract",
                "assessment",
                "repair",
                "prompt-build-brief",
            )
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if BRIEF_MARKER in text and "PROMPT 실행기" in text:
            candidates.append(path)
    if not candidates:
        raise PromptBriefTraceError("Brief를 받은 최종 PROMPT 실행기 request를 찾지 못했습니다.")
    return candidates[-1]


def _execution_from_output(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    execution = value.get("execution")
    if isinstance(execution, dict):
        return execution
    if "result_markdown" in value and "status" in value:
        return value
    return None


def _find_output(run_dir: Path, request_path: Path) -> tuple[Path, dict[str, Any]]:
    expected = request_path.with_name(
        request_path.name.removesuffix("-request.md") + "-output.json"
    )
    for path in [expected, *sorted(run_dir.glob("*-output.json"), reverse=True)]:
        if not path.is_file():
            continue
        execution = _execution_from_output(path)
        if execution and isinstance(execution.get("result_markdown"), str):
            return path, execution
    raise PromptBriefTraceError("Brief 기반 PROMPT 실행 결과를 찾지 못했습니다.")


def build_prompt_brief_trace(
    run_dir: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    record = payload.get("prompt_build_brief")
    if not isinstance(record, Mapping) or record.get("status") != "applied":
        return None
    entries = record.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PromptBriefTraceError("Prompt Build Brief entry가 없습니다.")
    entry = entries[0]
    if not isinstance(entry, Mapping):
        raise PromptBriefTraceError("Prompt Build Brief entry가 객체가 아닙니다.")

    run_dir = run_dir.expanduser().resolve()
    request = TRACE._read_text(run_dir / "request.txt", "request.txt").strip()
    ledger = TRACE._read_json(run_dir / "goal_ledger.json", "goal_ledger.json")
    ledger_text = TRACE._ledger_text(ledger)
    baseline_path = _read_path(
        run_dir,
        entry.get("compiler_baseline_path"),
        "Compiler baseline",
    )
    baseline = TRACE._read_json(baseline_path, baseline_path.name)
    baseline_text = str(baseline.get("final_prompt") or "").strip()
    if not baseline_text:
        raise PromptBriefTraceError("Compiler baseline final_prompt가 비어 있습니다.")
    legacy_path = _read_path(
        run_dir,
        entry.get("original_executor_input_path"),
        "이전 Executor 입력",
    )
    legacy_input = TRACE._read_text(legacy_path, legacy_path.name)
    brief_path = _read_path(run_dir, entry.get("brief_path"), "Prompt Build Brief")
    brief = TRACE._read_json(brief_path, brief_path.name)
    brief_text = json.dumps(brief, ensure_ascii=False, indent=2)
    executor_path = _find_final_prompt_executor(run_dir)
    executor_input = TRACE._read_text(executor_path, executor_path.name)
    output_path, execution = _find_output(run_dir, executor_path)
    final_prompt = str(execution["result_markdown"]).strip()

    source_surfaces = [
        {"id": "request", "source": "request.txt", "metrics": TRACE._metrics(request)},
        {
            "id": "goal_ledger",
            "source": "goal_ledger.json",
            "metrics": TRACE._metrics(ledger_text),
        },
        {
            "id": "prompt_compiler_baseline",
            "source": baseline_path.relative_to(run_dir).as_posix(),
            "metrics": TRACE._metrics(baseline_text),
        },
    ]
    pipeline_texts = [
        ("legacy_executor_input", legacy_input),
        ("prompt_build_brief", brief_text),
        ("executor_input", executor_input),
        ("final_prompt", final_prompt),
    ]
    pipeline = [
        {
            "id": stage_id,
            "source": (
                legacy_path.relative_to(run_dir).as_posix()
                if stage_id == "legacy_executor_input"
                else brief_path.relative_to(run_dir).as_posix()
                if stage_id == "prompt_build_brief"
                else executor_path.name
                if stage_id == "executor_input"
                else output_path.name
            ),
            "metrics": TRACE._metrics(text),
        }
        for stage_id, text in pipeline_texts
    ]
    transitions = [
        {
            "from": pipeline_texts[index - 1][0],
            "to": pipeline_texts[index][0],
            **TRACE._transition(
                pipeline_texts[index - 1][1],
                pipeline_texts[index][1],
            ),
        }
        for index in range(1, len(pipeline_texts))
    ]
    duplicates = TRACE._duplicate_groups(final_prompt)
    raw_surfaces_absent = all(
        marker not in executor_input
        for marker in ("[사용자 요청]", "[Goal Ledger]", "[기존 Prompt Compiler baseline]")
    )
    findings = [
        {
            "code": "parallel-inputs-normalized",
            "stage": "prompt_build_brief",
            "finding": (
                "사용자 원문·Goal Ledger·Compiler baseline은 감사 파일에 보존되고, "
                "최종 Executor에는 통합된 Prompt Build Brief만 전달됩니다."
            ),
        },
        {
            "code": "raw-surfaces-removed",
            "stage": "executor_input",
            "finding": (
                "최종 Executor 입력에서 원문·전체 Ledger·baseline 블록이 제거됐습니다."
                if raw_surfaces_absent
                else "최종 Executor 입력에 기존 병렬 입력 표면 일부가 남아 있습니다."
            ),
        },
    ]
    if duplicates:
        findings.append(
            {
                "code": "remaining-final-repetition",
                "stage": "final_prompt",
                "finding": f"최종 프롬프트에 의미가 가까운 문장 쌍 {len(duplicates)}개가 남았습니다.",
            }
        )
    final_metrics = TRACE._metrics(final_prompt)
    if final_metrics["headings"] >= 8:
        findings.append(
            {
                "code": "remaining-format-pressure",
                "stage": "final_prompt",
                "finding": "Brief 이후에도 최종 프롬프트 제목 수가 많아 출력 형식 압력이 남을 수 있습니다.",
            }
        )

    return {
        "version": 2,
        "run_id": run_dir.name,
        "input_contract": record.get("input_contract"),
        "source_surfaces": source_surfaces,
        "pipeline": pipeline,
        "transitions": transitions,
        "normalization": {
            "legacy_to_brief_character_ratio": round(
                len(brief_text) / max(len(legacy_input), 1),
                3,
            ),
            "legacy_to_executor_character_ratio": round(
                len(executor_input) / max(len(legacy_input), 1),
                3,
            ),
            "raw_parallel_surfaces_absent_from_executor": raw_surfaces_absent,
        },
        "brief": {
            "goal": brief.get("goal"),
            "core_procedure_count": len(brief.get("core_procedure", [])),
            "supporting_input_count": len(brief.get("supporting_inputs", [])),
            "fixed_constraint_count": len(brief.get("fixed_constraints", [])),
            "output_contract_count": len(brief.get("output_contract", [])),
            "generation": entry.get("generation"),
        },
        "final_prompt_duplicate_pairs": duplicates,
        "structural_findings": findings,
        "diagnostic_boundary": (
            "이 기록은 입력 통합과 생성 결과의 구조만 측정합니다. "
            "최종 프롬프트의 도메인 정확성과 실제 적용 품질은 별도 실행 비교가 필요합니다."
        ),
    }


def render_prompt_brief_trace(trace: Mapping[str, Any]) -> str:
    labels = {
        "request": "사용자 원문",
        "goal_ledger": "Goal Ledger",
        "prompt_compiler_baseline": "Compiler baseline",
        "legacy_executor_input": "이전 병렬 합류 입력",
        "prompt_build_brief": "Prompt Build Brief",
        "executor_input": "새 PROMPT 실행기 입력",
        "final_prompt": "최종 프롬프트",
    }
    lines = [
        "# PROMPT Build Brief 생성 진단",
        "",
        f"실행: `{trace['run_id']}`",
        "",
        "## 병렬 원천",
        "",
        "| 원천 | 문자 | 토큰 | 제목 | 규칙 표현 | 안전 문구 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for stage in trace["source_surfaces"]:
        metrics = stage["metrics"]
        lines.append(
            f"| {labels[stage['id']]} | {metrics['characters']} | {metrics['tokens']} | "
            f"{metrics['headings']} | {metrics['rule_marker_hits']} | {metrics['safety_marker_hits']} |"
        )
    lines.extend(
        [
            "",
            "## 통합 이후 경로",
            "",
            "| 단계 | 문자 | 토큰 | 제목 | 규칙 표현 | 안전 문구 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for stage in trace["pipeline"]:
        metrics = stage["metrics"]
        lines.append(
            f"| {labels[stage['id']]} | {metrics['characters']} | {metrics['tokens']} | "
            f"{metrics['headings']} | {metrics['rule_marker_hits']} | {metrics['safety_marker_hits']} |"
        )
    normalization = trace["normalization"]
    lines.extend(
        [
            "",
            "## 통합 결과",
            "",
            f"- 이전 합류 입력 대비 Brief 길이: {normalization['legacy_to_brief_character_ratio']:.2f}배",
            f"- 이전 합류 입력 대비 새 Executor 입력 길이: {normalization['legacy_to_executor_character_ratio']:.2f}배",
            "- 원문·전체 Ledger·baseline 표면 제거: "
            + ("예" if normalization["raw_parallel_surfaces_absent_from_executor"] else "아니요"),
            "",
            "## 구조적 판정",
            "",
        ]
    )
    for item in trace["structural_findings"]:
        lines.append(f"- **{item['code']}** · `{item['stage']}`: {item['finding']}")
    lines.extend(["", "## 진단 경계", "", str(trace["diagnostic_boundary"]), ""])
    return "\n".join(lines)


def attach_prompt_brief_trace(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    trace = build_prompt_brief_trace(run_dir, payload)
    if trace is None:
        return None
    json_path = TRACE._atomic_json(run_dir / "prompt_generation_trace.json", trace)
    markdown_path = run_dir / "prompt_generation_trace.md"
    markdown_path.write_text(render_prompt_brief_trace(trace), encoding="utf-8")
    return {
        "version": 2,
        "status": "completed",
        "json_path": json_path.relative_to(run_dir).as_posix(),
        "markdown_path": markdown_path.relative_to(run_dir).as_posix(),
        "input_contract": "single_prompt_build_brief",
    }
