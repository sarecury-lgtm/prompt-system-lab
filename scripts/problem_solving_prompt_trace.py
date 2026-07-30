#!/usr/bin/env python3
"""Trace how a PSOS PROMPT request expands from request to final reusable prompt."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9_]+")
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)
BULLET_PATTERN = re.compile(r"^\s*[-*+]\s+", re.M)
NUMBERED_PATTERN = re.compile(r"^\s*\d+[.)]\s+", re.M)
RULE_MARKERS = (
    "하지 않는다",
    "하지 마",
    "금지",
    "반드시",
    "명시",
    "확인 불가",
    "꾸며내",
    "단정하지",
    "관망",
    "비추천",
    "조건부",
    "제한",
    "주의",
)
PROMPT_MARKER = "[기존 Prompt Compiler baseline]"
OUTPUT_MARKERS = (
    "출력 형식",
    "출력 규칙",
    "반환 형식",
    "결과 형식",
    "output",
)
SAFETY_MARKERS = (
    "하지 않는다",
    "하지 마",
    "금지",
    "확인 불가",
    "꾸며내",
    "단정하지",
    "검증할 수 없는",
    "무조건",
    "확실",
    "주의사항",
)


class PromptTraceError(ValueError):
    """Raised when a run cannot be traced without inventing missing stages."""


def _read_text(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptTraceError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not value.strip():
        raise PromptTraceError(f"{label}이 비어 있습니다.")
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptTraceError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptTraceError(f"{label}은 JSON 객체여야 합니다.")
    return value


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)]


def _unique_tokens(text: str) -> set[str]:
    return set(_tokens(text))


def _clean_clause(value: str) -> str:
    value = re.sub(r"`{1,3}", "", value)
    value = re.sub(r"^\s*(?:#{1,6}|[-*+]|\d+[.)])\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n-–—:;,. ")
    return value


def _clauses(text: str) -> list[str]:
    clauses: list[str] = []
    for line in text.splitlines():
        line = _clean_clause(line)
        if len(line) < 18:
            continue
        for part in re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+", line):
            cleaned = _clean_clause(part)
            if len(cleaned) >= 18 and cleaned not in clauses:
                clauses.append(cleaned)
    return clauses


def _metrics(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    lowered = text.casefold()
    safety_hits = sum(lowered.count(marker.casefold()) for marker in SAFETY_MARKERS)
    rule_hits = sum(lowered.count(marker.casefold()) for marker in RULE_MARKERS)
    output_lines = sum(
        1
        for line in lines
        if any(marker.casefold() in line.casefold() for marker in OUTPUT_MARKERS)
    )
    return {
        "characters": len(text),
        "tokens": len(_tokens(text)),
        "unique_tokens": len(_unique_tokens(text)),
        "nonempty_lines": len(lines),
        "headings": len(HEADING_PATTERN.findall(text)),
        "bullets": len(BULLET_PATTERN.findall(text)),
        "numbered_items": len(NUMBERED_PATTERN.findall(text)),
        "rule_marker_hits": rule_hits,
        "safety_marker_hits": safety_hits,
        "output_marker_lines": output_lines,
    }


def _transition(previous: str, current: str) -> dict[str, Any]:
    previous_tokens = _unique_tokens(previous)
    current_tokens = _unique_tokens(current)
    retained = previous_tokens & current_tokens
    added = current_tokens - previous_tokens
    removed = previous_tokens - current_tokens
    previous_count = max(len(previous_tokens), 1)
    current_count = max(len(current_tokens), 1)
    return {
        "character_ratio": round(len(current) / max(len(previous), 1), 3),
        "retained_previous_token_ratio": round(len(retained) / previous_count, 3),
        "new_current_token_ratio": round(len(added) / current_count, 3),
        "added_unique_tokens": len(added),
        "removed_unique_tokens": len(removed),
        "sample_added_tokens": sorted(added)[:25],
    }


def _extract_json_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    position = text.find(marker)
    if position < 0:
        return None
    start = text.find("{", position + len(marker))
    if start < 0:
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _find_executor_request(run_dir: Path) -> Path:
    candidates: list[Path] = []
    for path in sorted(run_dir.glob("*-request.md")):
        name = path.name.casefold()
        if any(
            excluded in name
            for excluded in (
                "router",
                "result-contract",
                "assessment",
                "repair",
                "deep-report",
                "normalizer",
            )
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "PROMPT 실행기" in content or PROMPT_MARKER in content:
            candidates.append(path)
    if not candidates:
        raise PromptTraceError("PROMPT 실행기 request 파일을 찾을 수 없습니다.")
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


def _find_execution_output(run_dir: Path, request_path: Path) -> tuple[Path, dict[str, Any]]:
    expected = request_path.with_name(
        request_path.name.removesuffix("-request.md") + "-output.json"
    )
    candidates = [expected, *sorted(run_dir.glob("*-output.json"), reverse=True)]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        execution = _execution_from_output(path)
        if execution and isinstance(execution.get("result_markdown"), str):
            return path, execution
    raise PromptTraceError("PROMPT 실행 결과 JSON을 찾을 수 없습니다.")


def _ledger_text(ledger: Mapping[str, Any]) -> str:
    ordered = [
        "parent_goal",
        "current_goal_hypothesis",
        "fixed_constraints",
        "current_step",
        "completion_condition",
        "important_uncertainties",
    ]
    parts: list[str] = []
    for key in ordered:
        value = ledger.get(key)
        if isinstance(value, list):
            rendered = "\n".join(f"- {item}" for item in value if isinstance(item, str))
        elif value is None:
            rendered = ""
        else:
            rendered = str(value)
        if rendered.strip():
            parts.append(f"[{key}]\n{rendered.strip()}")
    return "\n\n".join(parts)


def _duplicate_groups(text: str) -> list[dict[str, Any]]:
    clauses = _clauses(text)
    groups: list[dict[str, Any]] = []
    used_pairs: set[tuple[int, int]] = set()
    for left_index, left in enumerate(clauses):
        left_tokens = _unique_tokens(left)
        if len(left_tokens) < 4:
            continue
        for right_index in range(left_index + 1, len(clauses)):
            right = clauses[right_index]
            right_tokens = _unique_tokens(right)
            if len(right_tokens) < 4:
                continue
            union = left_tokens | right_tokens
            jaccard = len(left_tokens & right_tokens) / max(len(union), 1)
            sequence = difflib.SequenceMatcher(None, left, right).ratio()
            if jaccard < 0.45 and sequence < 0.62:
                continue
            pair = (left_index, right_index)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            groups.append(
                {
                    "left": left,
                    "right": right,
                    "token_overlap": round(jaccard, 3),
                    "sequence_similarity": round(sequence, 3),
                }
            )
            if len(groups) >= 20:
                return groups
    return groups


def _best_source(clause: str, sources: Mapping[str, str]) -> dict[str, Any]:
    clause_tokens = _unique_tokens(clause)
    best_name = "novel"
    best_score = 0.0
    for name, source in sources.items():
        source_tokens = _unique_tokens(source)
        if not clause_tokens or not source_tokens:
            continue
        score = len(clause_tokens & source_tokens) / len(clause_tokens)
        if score > best_score:
            best_name = name
            best_score = score
    return {
        "clause": clause,
        "source": best_name if best_score >= 0.35 else "novel",
        "token_coverage": round(best_score, 3),
    }


def _attribution(final_prompt: str, sources: Mapping[str, str]) -> list[dict[str, Any]]:
    return [_best_source(clause, sources) for clause in _clauses(final_prompt)[:120]]


def _structural_findings(
    *,
    request: str,
    ledger: Mapping[str, Any],
    baseline: Mapping[str, Any],
    executor_request: str,
    final_prompt: str,
    transitions: Sequence[Mapping[str, Any]],
    duplicates: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    fixed = ledger.get("fixed_constraints")
    if isinstance(fixed, list):
        findings.append(
            {
                "code": "flat-ledger",
                "stage": "goal_ledger",
                "finding": (
                    "fixed_constraints가 우선순위·핵심/보조/안전 구분 없는 평면 배열이라 "
                    "서로 다른 역할의 조건이 같은 무게로 전달됩니다."
                ),
            }
        )
    baseline_prompt = str(baseline.get("final_prompt") or "")
    if any(
        marker in baseline_prompt
        for marker in ("[수행 및 출력 규칙]", "[작업별 추가 규칙]")
    ):
        findings.append(
            {
                "code": "additive-baseline",
                "stage": "prompt_compiler_baseline",
                "finding": (
                    "Prompt Compiler baseline은 기존 요청 뒤에 패턴·작업 규칙을 덧붙이는 "
                    "additive 방식이며, 중복을 합치거나 중요도를 재배치하는 단계가 없습니다."
                ),
            }
        )
    repeated_inputs = []
    if request.strip() and request.strip() in executor_request:
        repeated_inputs.append("사용자 요청")
    if "Goal Ledger" in executor_request:
        repeated_inputs.append("Goal Ledger")
    if PROMPT_MARKER in executor_request:
        repeated_inputs.append("Prompt Compiler baseline")
    if len(repeated_inputs) >= 3:
        findings.append(
            {
                "code": "triple-input-surface",
                "stage": "executor_input",
                "finding": (
                    "PROMPT 실행기는 "
                    + ", ".join(repeated_inputs)
                    + "을 동시에 받아 같은 요구가 여러 표현으로 재노출됩니다."
                ),
            }
        )
    if duplicates:
        findings.append(
            {
                "code": "final-semantic-repetition",
                "stage": "final_prompt",
                "finding": (
                    f"최종 프롬프트에서 의미가 가까운 규칙 쌍 {len(duplicates)}개가 감지돼, "
                    "요구 보존이 통합보다 반복으로 실현된 흔적이 있습니다."
                ),
            }
        )
    final_metrics = _metrics(final_prompt)
    if final_metrics["headings"] >= 6 or (
        final_metrics["bullets"] + final_metrics["numbered_items"] >= 20
    ):
        findings.append(
            {
                "code": "format-pressure",
                "stage": "final_prompt",
                "finding": (
                    "출력·규칙 구조가 많은 제목과 항목으로 확장돼 실제 판단 절차보다 "
                    "양식 충족이 모델 행동을 지배할 가능성이 큽니다."
                ),
            }
        )
    if final_metrics["safety_marker_hits"] >= 8:
        findings.append(
            {
                "code": "safety-rule-dominance",
                "stage": "final_prompt",
                "finding": (
                    "금지·확인 불가·단정 금지 계열 안전 문구가 여러 번 나타나 "
                    "핵심 작업 절차와 같은 수준의 주의를 요구합니다."
                ),
            }
        )
    if transitions:
        largest_index = max(
            range(len(transitions)),
            key=lambda index: float(transitions[index]["character_ratio"]),
        )
        names = (
            "request→goal_ledger",
            "goal_ledger→compiler_baseline",
            "compiler_baseline→executor_input",
            "executor_input→final_prompt",
        )
        findings.append(
            {
                "code": "largest-expansion",
                "stage": names[largest_index],
                "finding": (
                    f"문자 수 기준 가장 큰 팽창은 {names[largest_index]} 구간 "
                    f"({transitions[largest_index]['character_ratio']}배)에서 발생했습니다."
                ),
            }
        )
    baseline_record = json.dumps(
        {
            "selected_mode": baseline.get("selected_mode"),
            "used_patterns": baseline.get("used_patterns"),
            "used_active_sources": baseline.get("used_active_sources"),
        },
        ensure_ascii=False,
    )
    if "Prompt Improvement Loop" in baseline_record or "Structured Output" in baseline_record:
        findings.append(
            {
                "code": "coverage-reward",
                "stage": "prompt_compiler_baseline",
                "finding": (
                    "선택된 패턴이 누락 점검과 출력 계약 명시를 보상하지만, "
                    "규칙 수·반복·판단 집중도를 줄이는 반대 기준은 없습니다."
                ),
            }
        )
    return findings


def build_prompt_generation_trace(
    run_dir: Path,
    execution_override: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    run_dir = run_dir.expanduser().resolve()
    route = _read_json(run_dir / "route.json", "route.json")
    selected = route.get("selected_route")
    prompt_in_route = selected == "PROMPT" or (
        selected == "HYBRID"
        and "PROMPT" in {route.get("primary_route"), route.get("secondary_route")}
    )
    if not prompt_in_route:
        return None

    request = _read_text(run_dir / "request.txt", "request.txt").strip()
    ledger = _read_json(run_dir / "goal_ledger.json", "goal_ledger.json")
    executor_path = _find_executor_request(run_dir)
    executor_request = _read_text(executor_path, executor_path.name)
    baseline = _extract_json_after_marker(executor_request, PROMPT_MARKER)
    if baseline is None:
        raise PromptTraceError(
            "PROMPT 실행기 request에서 실제 Prompt Compiler baseline JSON을 찾지 못했습니다."
        )
    baseline_prompt = baseline.get("final_prompt")
    if not isinstance(baseline_prompt, str) or not baseline_prompt.strip():
        raise PromptTraceError("Prompt Compiler baseline에 final_prompt가 없습니다.")
    output_path, execution = _find_execution_output(run_dir, executor_path)
    if (
        isinstance(execution_override, Mapping)
        and isinstance(execution_override.get("result_markdown"), str)
    ):
        execution = dict(execution_override)
    final_prompt = str(execution["result_markdown"]).strip()
    ledger_rendered = _ledger_text(ledger)

    stage_texts = [
        ("request", request),
        ("goal_ledger", ledger_rendered),
        ("prompt_compiler_baseline", baseline_prompt),
        ("executor_input", executor_request),
        ("final_prompt", final_prompt),
    ]
    stages = [
        {
            "id": stage_id,
            "source": (
                "request.txt"
                if stage_id == "request"
                else "goal_ledger.json"
                if stage_id == "goal_ledger"
                else executor_path.name
                if stage_id in {"prompt_compiler_baseline", "executor_input"}
                else output_path.name
            ),
            "metrics": _metrics(text),
        }
        for stage_id, text in stage_texts
    ]
    transitions = []
    for index in range(1, len(stage_texts)):
        previous_id, previous_text = stage_texts[index - 1]
        current_id, current_text = stage_texts[index]
        transitions.append(
            {
                "from": previous_id,
                "to": current_id,
                **_transition(previous_text, current_text),
            }
        )

    duplicates = _duplicate_groups(final_prompt)
    attribution = _attribution(
        final_prompt,
        {
            "request": request,
            "goal_ledger": ledger_rendered,
            "prompt_compiler_baseline": baseline_prompt,
            "executor_rules": executor_request,
        },
    )
    findings = _structural_findings(
        request=request,
        ledger=ledger,
        baseline=baseline,
        executor_request=executor_request,
        final_prompt=final_prompt,
        transitions=transitions,
        duplicates=duplicates,
    )
    return {
        "version": 1,
        "run_id": run_dir.name,
        "selected_route": selected,
        "sources": {
            "request": "request.txt",
            "goal_ledger": "goal_ledger.json",
            "executor_request": executor_path.name,
            "executor_output": output_path.name,
        },
        "compiler": {
            "selected_mode": baseline.get("selected_mode"),
            "selection_reason": baseline.get("selection_reason"),
            "used_patterns": baseline.get("used_patterns", []),
            "used_active_sources": baseline.get("used_active_sources", []),
            "fallback": baseline.get("fallback"),
            "fallback_reason": baseline.get("fallback_reason"),
        },
        "stages": stages,
        "transitions": transitions,
        "final_prompt_duplicate_pairs": duplicates,
        "final_clause_attribution": attribution,
        "structural_findings": findings,
        "diagnostic_boundary": (
            "이 기록은 실제 run artifact의 텍스트 구조와 중복을 추적합니다. "
            "최종 프롬프트의 매매·법률·의학 등 도메인 정확성을 판정하지 않습니다."
        ),
    }


def render_prompt_generation_trace(trace: Mapping[str, Any]) -> str:
    lines = [
        "# PROMPT 생성 경로 진단",
        "",
        f"실행: `{trace['run_id']}`",
        f"경로: `{trace['selected_route']}`",
        "",
        "## 단계별 크기",
        "",
        "| 단계 | 문자 | 토큰 | 제목 | 불릿 | 번호 항목 | 안전 문구 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "request": "사용자 원문",
        "goal_ledger": "Goal Ledger",
        "prompt_compiler_baseline": "Compiler baseline",
        "executor_input": "PROMPT 실행기 입력",
        "final_prompt": "최종 프롬프트",
    }
    for stage in trace["stages"]:
        metrics = stage["metrics"]
        lines.append(
            f"| {labels.get(stage['id'], stage['id'])} | "
            f"{metrics['characters']} | {metrics['tokens']} | {metrics['headings']} | "
            f"{metrics['bullets']} | {metrics['numbered_items']} | "
            f"{metrics['safety_marker_hits']} |"
        )
    lines.extend(["", "## 구간별 변화", ""])
    for transition in trace["transitions"]:
        lines.append(
            f"- **{labels.get(transition['from'], transition['from'])} → "
            f"{labels.get(transition['to'], transition['to'])}**: "
            f"길이 {transition['character_ratio']}배 · 이전 고유 토큰 "
            f"{transition['retained_previous_token_ratio']:.0%} 유지 · 현재 토큰 중 "
            f"{transition['new_current_token_ratio']:.0%} 신규"
        )
    lines.extend(["", "## 구조적 원인", ""])
    findings = trace.get("structural_findings", [])
    if findings:
        for item in findings:
            lines.append(
                f"- **{item['code']}** · `{item['stage']}`: {item['finding']}"
            )
    else:
        lines.append("- 자동 진단에서 뚜렷한 구조적 팽창 신호를 찾지 못했습니다.")
    lines.extend(["", "## 최종 프롬프트의 반복 신호", ""])
    duplicates = trace.get("final_prompt_duplicate_pairs", [])
    if duplicates:
        for item in duplicates[:8]:
            lines.append(
                f"- `{item['token_overlap']:.0%}` 겹침: "
                f"“{item['left']}” ↔ “{item['right']}”"
            )
    else:
        lines.append("- 유사도가 높은 규칙 쌍이 감지되지 않았습니다.")
    lines.extend(
        [
            "",
            "## 진단 경계",
            "",
            str(trace["diagnostic_boundary"]),
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_json(path: Path, payload: Any) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def write_prompt_generation_trace(
    run_dir: Path,
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    json_path = _atomic_json(run_dir / "prompt_generation_trace.json", trace)
    markdown_path = run_dir / "prompt_generation_trace.md"
    markdown_path.write_text(
        render_prompt_generation_trace(trace),
        encoding="utf-8",
    )
    return {
        "version": 1,
        "json_path": json_path.name,
        "markdown_path": markdown_path.name,
        "finding_count": len(trace.get("structural_findings", [])),
        "duplicate_pair_count": len(trace.get("final_prompt_duplicate_pairs", [])),
    }


def attach_prompt_generation_trace(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    trace = build_prompt_generation_trace(
        run_dir,
        payload.get("execution") if isinstance(payload.get("execution"), Mapping) else None,
    )
    if trace is None:
        return None
    record = write_prompt_generation_trace(run_dir, trace)
    payload["prompt_generation_trace"] = record
    if isinstance(payload.get("run"), dict):
        payload["run"]["prompt_generation_trace"] = record
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        trace = build_prompt_generation_trace(args.run_dir)
        if trace is None:
            print("PROMPT 경로가 아니므로 진단 파일을 만들지 않았습니다.")
            return 0
        record = write_prompt_generation_trace(args.run_dir, trace)
    except PromptTraceError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(args.run_dir / record["markdown_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
