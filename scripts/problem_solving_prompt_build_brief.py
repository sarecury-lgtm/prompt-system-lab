#!/usr/bin/env python3
"""Compile parallel PROMPT inputs into one validated Prompt Build Brief."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Protocol


ROOT = Path(__file__).resolve().parents[1]
BRIEF_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-prompt-build-brief.schema.json"
BASELINE_MARKER = "[기존 Prompt Compiler baseline]"
PRIMARY_MARKER = "[주 경로의 실제 결과]"
CONTRACT_MARKER = "[Result Contract]"
BRIEF_MARKER = "[Prompt Build Brief]"
PROMPT_OUTPUT_START = "<!-- PSOS_PROMPT_START -->"
PROMPT_OUTPUT_END = "<!-- PSOS_PROMPT_END -->"
BRIEF_FIELDS = {
    "version",
    "goal",
    "core_procedure",
    "supporting_inputs",
    "fixed_constraints",
    "output_contract",
    "defaults_and_exceptions",
    "exclusions",
    "upstream_context",
}
LIST_LIMITS: dict[str, tuple[int, int | None]] = {
    "core_procedure": (1, 8),
    "supporting_inputs": (0, 8),
    "fixed_constraints": (0, None),
    "output_contract": (1, 8),
    "defaults_and_exceptions": (0, 6),
    "exclusions": (0, 6),
    "upstream_context": (0, 8),
}


class CompatibleEngine(Protocol):
    def capabilities(self) -> Any: ...

    def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]: ...

    def trace(self) -> list[dict[str, Any]]: ...


class PromptBuildBriefError(ValueError):
    """Raised when a PROMPT brief cannot be validated or safely delivered."""


def _deduplicated_strings(value: Any) -> list[str]:
    result: list[str] = []
    for item in value if isinstance(value, (list, tuple)) else []:
        if isinstance(item, str) and item.strip() and item.strip() not in result:
            result.append(item.strip())
    return result


def _validated_string_list(value: Any, field: str) -> list[str]:
    minimum, maximum = LIST_LIMITS[field]
    if not isinstance(value, list):
        raise PromptBuildBriefError(f"{field}는 문자열 배열이어야 합니다.")
    normalized = _deduplicated_strings(value)
    if len(normalized) != len(value):
        raise PromptBuildBriefError(f"{field}에 빈 값이나 중복 값이 있습니다.")
    if len(normalized) < minimum or (
        maximum is not None and len(normalized) > maximum
    ):
        maximum_text = str(maximum) if maximum is not None else "제한 없음"
        raise PromptBuildBriefError(
            f"{field} 항목 수는 {minimum}~{maximum_text}개여야 합니다."
        )
    return normalized


def validate_prompt_build_brief(
    value: Any,
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BRIEF_FIELDS:
        raise PromptBuildBriefError("Prompt Build Brief 필드가 schema와 일치하지 않습니다.")
    if value.get("version") != 1:
        raise PromptBuildBriefError("지원하지 않는 Prompt Build Brief 버전입니다.")
    goal = value.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise PromptBuildBriefError("Prompt Build Brief goal이 비어 있습니다.")

    validated: dict[str, Any] = {"version": 1, "goal": goal.strip()}
    for field in LIST_LIMITS:
        validated[field] = _validated_string_list(value.get(field), field)

    expected_constraints = _deduplicated_strings(ledger.get("fixed_constraints"))
    if validated["fixed_constraints"] != expected_constraints:
        raise PromptBuildBriefError(
            "Prompt Build Brief가 Goal Ledger의 fixed_constraints를 정확히 보존하지 않았습니다."
        )
    completion = str(ledger.get("completion_condition") or "").strip()
    if not completion or validated["output_contract"][0] != completion:
        raise PromptBuildBriefError(
            "output_contract의 첫 항목은 Goal Ledger completion_condition과 같아야 합니다."
        )
    return validated


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


def _contract_suffix(prompt: str) -> str:
    position = prompt.find(CONTRACT_MARKER)
    if position < 0:
        return ""
    start = prompt.rfind("\n\n", 0, position)
    return prompt[start if start >= 0 else position :].rstrip()


def _logical_stage(name: str) -> str:
    base = re.sub(r"-fallback(?:-\d+)?$", "", name)
    if "secondary" in base:
        return "secondary"
    if "primary" in base:
        return "primary"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-") or "prompt"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def build_prompt_build_brief_prompt(
    request: str,
    ledger: Mapping[str, Any],
    baseline: Mapping[str, Any],
    primary_execution: Mapping[str, Any] | None,
) -> str:
    return f"""당신은 Personal Problem-Solving OS의 Prompt Build Brief 컴파일러다.

최종 프롬프트를 작성하지 않는다. 서로 다른 표현으로 반복된 사용자 원문, Goal Ledger,
Prompt Compiler baseline과 선택적 주 경로 결과를 하나의 짧은 작업 계약으로 통합한다.

[컴파일 원칙]
1. goal은 최종 프롬프트가 다른 AI에게 실제로 수행시킬 일을 쓴다.
2. core_procedure는 그 AI가 실행할 도메인 작업의 판단·처리 순서다.
   "요구를 반영한다", "프롬프트를 작성한다", "형식을 채운다" 같은 컴파일 작업을 쓰지 않는다.
3. supporting_inputs에는 핵심 절차를 돕는 자료·분석 요소·도구만 둔다.
4. 같은 의미의 요구는 하나의 상위 원리나 절차로 합친다. 원문 표현을 모두 보존하려고 반복하지 않는다.
5. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
6. output_contract의 첫 항목은 Goal Ledger completion_condition을 정확히 복사한다.
   나머지는 사용자 결과에 꼭 필요한 최소 산출물만 둔다. 임의의 섹션 수나 장식 형식은 추가하지 않는다.
7. defaults_and_exceptions에는 입력이 없거나 불확실할 때 실제 결과가 달라지는 처리만 둔다.
8. exclusions에는 사용자가 원하지 않거나 목표를 벗어나는 작업만 둔다.
9. upstream_context에는 주 경로 결과 중 최종 프롬프트가 실제로 사용해야 할 검증된 내용만 압축한다.
10. 사용자 원문이나 baseline 전체를 어느 필드에도 그대로 복사하지 않는다.
11. 특정 도메인의 일반 상식을 새로 추가하지 않는다.
12. 내부 추론을 노출하지 말고 schema에 맞는 JSON 객체 하나만 반환한다.

[사용자 요청]
{request.strip()}

[Goal Ledger]
{json.dumps(dict(ledger), ensure_ascii=False, indent=2)}

[Prompt Compiler baseline]
{json.dumps(dict(baseline), ensure_ascii=False, indent=2)}

[선택적 주 경로 결과]
{json.dumps(dict(primary_execution) if primary_execution is not None else None, ensure_ascii=False, indent=2)}
"""


def deterministic_prompt_build_brief(
    ledger: Mapping[str, Any],
    primary_execution: Mapping[str, Any] | None,
) -> dict[str, Any]:
    uncertainties = _deduplicated_strings(ledger.get("important_uncertainties"))[:6]
    upstream: list[str] = []
    if primary_execution is not None:
        summary = primary_execution.get("summary")
        if isinstance(summary, str) and summary.strip():
            upstream.append(summary.strip())
    return {
        "version": 1,
        "goal": str(ledger.get("current_goal_hypothesis") or "").strip(),
        "core_procedure": [str(ledger.get("current_step") or "").strip()],
        "supporting_inputs": [],
        "fixed_constraints": _deduplicated_strings(ledger.get("fixed_constraints")),
        "output_contract": [str(ledger.get("completion_condition") or "").strip()],
        "defaults_and_exceptions": uncertainties,
        "exclusions": [],
        "upstream_context": upstream,
    }


def render_prompt_build_brief(brief: Mapping[str, Any]) -> str:
    lines = ["# Prompt Build Brief", "", f"## 목표\n{brief['goal']}", ""]
    labels = (
        ("core_procedure", "핵심 작업 절차"),
        ("supporting_inputs", "보조 입력·도구"),
        ("fixed_constraints", "고정 조건"),
        ("output_contract", "출력 계약"),
        ("defaults_and_exceptions", "기본값과 예외"),
        ("exclusions", "제외 범위"),
        ("upstream_context", "주 경로에서 사용할 내용"),
    )
    for field, label in labels:
        lines.extend([f"## {label}", ""])
        values = brief[field]
        if values:
            lines.extend(f"{index}. {item}" for index, item in enumerate(values, 1))
        else:
            lines.append("- 없음")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_prompt_executor_from_brief(
    brief: Mapping[str, Any],
    invocation: Any,
    capabilities: Any,
    contract_suffix: str,
) -> str:
    contract_note = ""
    if contract_suffix:
        contract_note = (
            "\n\n[검증 계약 사용법]\n"
            "Result Contract는 완료 여부를 확인하는 계약이다. 각 요구를 같은 수의 제목이나 "
            "별도 규칙으로 다시 펼치지 말고 Prompt Build Brief의 절차와 출력 계약 안에서 충족한다."
            + contract_suffix
        )
    return f"""당신은 Personal Problem-Solving OS의 PROMPT 실행기다.

아래 Prompt Build Brief를 유일한 사용자 요구 표면으로 사용해, 다른 AI가 반복 실행할
최종 프롬프트 하나를 완성한다. 사용자 원문·Goal Ledger·Compiler baseline은 이미 Brief에
통합됐으므로 다시 복원하거나 별도 규칙으로 나열하지 않는다.

[작성 원칙]
1. 목표와 고정 조건은 의미를 보존하되 원래 표현을 모두 반복하지 않는다.
2. 핵심 작업 절차를 프롬프트의 중심에 두고, 보조 입력·안전 규칙·출력 형식은 그 절차에 종속시킨다.
3. 같은 의미가 원칙, 절차, 출력 형식에서 되풀이되면 하나로 합친다.
4. 세부 요구가 핵심 절차에 포함되면 독립 규칙으로 다시 쓰지 않는다.
5. 출력 형식은 실제 사용자가 판단하거나 행동하는 데 필요한 최소 구조만 둔다.
6. 글자 수나 섹션 수를 목표로 삼지 않는다. 짧게 만들기 위해 고정 조건을 버리지도 않는다.
7. 없는 사실·수치·도구 사용을 만들지 않는다.
8. limitations에는 최종 프롬프트 자체에 실제로 남은 한계만 쓴다.
9. 내부 시스템·브리지·receipt·생성 과정 설명을 사용자용 프롬프트에 넣지 않는다.

[PROMPT 결과 전용 계약]
1. 내부에서 초안을 점검하고 필요하면 수정하되 그 검토 과정은 출력하지 않는다.
2. execution.result_markdown에는 아래 시작·종료 표식을 정확히 한 번씩 넣는다.
3. 표식 사이에는 복사해 바로 쓸 완성된 프롬프트 하나만 넣는다.
4. 표식 앞뒤에는 평가, 설명, 개선점, 사용법, 선택 기록을 붙이지 않는다.

{PROMPT_OUTPUT_START}
[완성된 프롬프트 하나]
{PROMPT_OUTPUT_END}

{BRIEF_MARKER}
{json.dumps(dict(brief), ensure_ascii=False, indent=2)}

[현재 실행 프로필]
{json.dumps(asdict(invocation.profile), ensure_ascii=False, indent=2)}

[현재 capability]
{json.dumps(asdict(capabilities), ensure_ascii=False, indent=2)}{contract_note}
"""


class PromptBuildBriefEngine:
    """Intercept PROMPT executor calls and replace parallel inputs with one brief."""

    def __init__(
        self,
        delegate: CompatibleEngine,
        *,
        request: str,
        os_module: Any,
    ) -> None:
        self.delegate = delegate
        self.request = request.strip()
        self.OS = os_module
        self._router_payload: dict[str, Any] | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._records: dict[str, dict[str, Any]] = {}

    def capabilities(self) -> Any:
        return self.delegate.capabilities()

    def trace(self) -> list[dict[str, Any]]:
        return self.delegate.trace()

    def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]:
        if invocation.phase == "router":
            result = self.delegate.execute(prompt, run_dir, invocation)
            try:
                self._router_payload = self.OS.validate_route_output(copy.deepcopy(result))
            except self.OS.ProblemSolvingError:
                self._router_payload = None
            return result

        if invocation.phase != "executor" or invocation.route != "PROMPT":
            return self.delegate.execute(prompt, run_dir, invocation)
        if self._router_payload is None:
            return self.delegate.execute(prompt, run_dir, invocation)

        stage = _logical_stage(invocation.name)
        if stage not in self._cache:
            self._compile(run_dir, stage, prompt, invocation)
        brief = self._cache[stage]
        rewritten = build_prompt_executor_from_brief(
            brief,
            invocation,
            self.capabilities(),
            _contract_suffix(prompt),
        )
        record = self._records[stage]
        record.setdefault("deliveries", []).append(
            {
                "invocation": invocation.name,
                "model": invocation.profile.model,
                "reasoning_effort": invocation.profile.reasoning_effort,
                "executor_prompt_sha256": _sha256_text(rewritten),
            }
        )
        record["delivered_to_executor"] = True
        return self.delegate.execute(rewritten, run_dir, invocation)

    def _compile(
        self,
        run_dir: Path,
        stage: str,
        original_prompt: str,
        executor_invocation: Any,
    ) -> None:
        ledger = self._router_payload["goal_ledger"]
        baseline = _extract_json_after_marker(original_prompt, BASELINE_MARKER) or {}
        primary = _extract_json_after_marker(original_prompt, PRIMARY_MARKER)
        compiler_prompt = build_prompt_build_brief_prompt(
            self.request,
            ledger,
            baseline,
            primary,
        )
        profile = self.OS.ModelProfile(
            model=executor_invocation.profile.model,
            reasoning_effort=executor_invocation.profile.reasoning_effort,
            web_search=False,
            sandbox="read-only",
        )
        invocation = self.OS.InvocationSpec(
            name=f"prompt-build-brief-{stage}",
            phase="prompt_brief",
            route=None,
            profile=profile,
            schema_path=BRIEF_SCHEMA_PATH,
        )
        generation = "model_compiled"
        generation_error: str | None = None
        try:
            candidate = self.delegate.execute(compiler_prompt, run_dir, invocation)
            brief = validate_prompt_build_brief(candidate, ledger)
        except (self.OS.ProblemSolvingError, PromptBuildBriefError) as exc:
            generation = "deterministic_fallback"
            generation_error = str(exc)
            brief = validate_prompt_build_brief(
                deterministic_prompt_build_brief(ledger, primary),
                ledger,
            )

        root = run_dir / "prompt_build_brief" / stage
        root.mkdir(parents=True, exist_ok=True)
        original_path = root / "original_executor_input.md"
        original_path.write_text(original_prompt.rstrip() + "\n", encoding="utf-8")
        baseline_path = _write_json(root / "compiler_baseline.json", baseline)
        primary_path: Path | None = None
        if primary is not None:
            primary_path = _write_json(root / "primary_execution.json", primary)
        brief_path = _write_json(root / "brief.json", brief)
        markdown_path = root / "brief.md"
        markdown_path.write_text(render_prompt_build_brief(brief), encoding="utf-8")
        source_record = {
            "version": 1,
            "stage": stage,
            "request_sha256": _sha256_text(self.request),
            "goal_ledger_sha256": _sha256_text(
                json.dumps(ledger, ensure_ascii=False, sort_keys=True)
            ),
            "compiler_baseline_sha256": _sha256_text(
                json.dumps(baseline, ensure_ascii=False, sort_keys=True)
            ),
            "primary_execution_sha256": (
                _sha256_text(json.dumps(primary, ensure_ascii=False, sort_keys=True))
                if primary is not None
                else None
            ),
            "original_executor_input_sha256": _sha256_text(original_prompt),
        }
        source_path = _write_json(root / "sources.json", source_record)
        relative = lambda path: path.relative_to(run_dir).as_posix()
        self._cache[stage] = brief
        self._records[stage] = {
            "stage": stage,
            "generation": generation,
            "generation_error": generation_error,
            "brief_path": relative(brief_path),
            "markdown_path": relative(markdown_path),
            "sources_path": relative(source_path),
            "original_executor_input_path": relative(original_path),
            "compiler_baseline_path": relative(baseline_path),
            "primary_execution_path": relative(primary_path) if primary_path else None,
            "brief_sha256": hashlib.sha256(brief_path.read_bytes()).hexdigest(),
            "delivered_to_executor": False,
            "deliveries": [],
        }

    def record(self) -> dict[str, Any] | None:
        if not self._records:
            return None
        return {
            "version": 1,
            "status": "applied",
            "input_contract": "single_prompt_build_brief",
            "entries": [copy.deepcopy(self._records[key]) for key in sorted(self._records)],
        }
