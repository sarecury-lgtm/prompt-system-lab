#!/usr/bin/env python3
"""Compare PROMPT input structures through the manual ChatGPT bridge."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


VARIANT_ORDER = (
    "current",
    "without_raw_request",
    "compact_ledger",
    "single_build_brief",
)
NEW_VARIANTS = VARIANT_ORDER[1:]
VARIANT_LABELS = {
    "current": "현재 방식",
    "without_raw_request": "원문 중복 제거",
    "compact_ledger": "Goal Ledger 축약",
    "single_build_brief": "단일 Build Brief",
}
ASSESSMENT_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "problem-solving-manual-prompt-ablation-assessment.schema.json"
)
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
    "주의",
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
BASELINE_MARKER = "[기존 Prompt Compiler baseline]"


class ManualPromptAblationError(ValueError):
    """Raised when a manual PROMPT comparison cannot continue safely."""


def _write_json(manual: Any, path: Path, payload: Any) -> None:
    manual.write_json(path, payload)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualPromptAblationError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise ManualPromptAblationError(f"{label}은 JSON 객체여야 합니다.")
    return value


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


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)}


def _clean_clause(value: str) -> str:
    value = re.sub(r"`{1,3}", "", value)
    value = re.sub(r"^\s*(?:#{1,6}|[-*+]|\d+[.)])\s*", "", value)
    return re.sub(r"\s+", " ", value).strip(" \t\r\n-–—:;,. ")


def _clauses(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        cleaned = _clean_clause(line)
        if len(cleaned) < 18:
            continue
        for part in re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+", cleaned):
            clause = _clean_clause(part)
            if len(clause) >= 18 and clause not in values:
                values.append(clause)
    return values


def _duplicate_count(text: str) -> int:
    clauses = _clauses(text)
    count = 0
    for left_index, left in enumerate(clauses):
        left_tokens = _tokens(left)
        if len(left_tokens) < 4:
            continue
        for right in clauses[left_index + 1 :]:
            right_tokens = _tokens(right)
            if len(right_tokens) < 4:
                continue
            union = left_tokens | right_tokens
            overlap = len(left_tokens & right_tokens) / max(len(union), 1)
            similarity = difflib.SequenceMatcher(None, left, right).ratio()
            if overlap >= 0.45 or similarity >= 0.62:
                count += 1
                if count >= 20:
                    return count
    return count


def _surface_coverage(source: str, target: str) -> float:
    source_tokens = _tokens(source)
    target_tokens = _tokens(target)
    if not target_tokens:
        return 1.0
    return round(len(source_tokens & target_tokens) / len(target_tokens), 3)


def _metrics(text: str, constraints: list[str]) -> dict[str, Any]:
    lowered = text.casefold()
    coverages = [_surface_coverage(text, item) for item in constraints]
    return {
        "characters": len(text),
        "headings": len(HEADING_PATTERN.findall(text)),
        "bullets": len(BULLET_PATTERN.findall(text)),
        "numbered_items": len(NUMBERED_PATTERN.findall(text)),
        "rule_marker_hits": sum(lowered.count(item.casefold()) for item in RULE_MARKERS),
        "safety_marker_hits": sum(
            lowered.count(item.casefold()) for item in SAFETY_MARKERS
        ),
        "duplicate_pair_count": _duplicate_count(text),
        "average_constraint_token_coverage": (
            round(sum(coverages) / len(coverages), 3) if coverages else 1.0
        ),
        "metric_boundary": (
            "토큰 겹침은 요구 보존의 표면 신호일 뿐 의미 충족을 증명하지 않습니다."
        ),
    }


def _compiler_guidance(baseline_prompt: str) -> str:
    markers = ("[수행 및 출력 규칙]", "[작업별 추가 규칙]")
    positions = [baseline_prompt.find(marker) for marker in markers]
    positions = [position for position in positions if position >= 0]
    return baseline_prompt[min(positions) :].strip() if positions else ""


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
    parts = [
        "[Prompt Build Brief]",
        f"목표: {str(ledger.get('current_goal_hypothesis') or '').strip()}",
        "",
        "고정 조건:",
        constraint_text or "- 없음",
        "",
        f"완료 조건: {str(ledger.get('completion_condition') or '').strip()}",
    ]
    if guidance:
        parts.extend(["", guidance])
    parts.extend(
        [
            "",
            "위 brief의 의미를 보존하되 같은 요구를 여러 규칙이나 출력 섹션으로 반복하지 마라.",
            "먼저 핵심 작업 절차를 정하고 보조 규칙·안전 규칙·출력 형식은 그 절차에 종속시켜라.",
            "짧게 만드는 것 자체가 목표는 아니다. 중요한 조건은 빠뜨리지 마라.",
        ]
    )
    return "\n".join(parts).strip()


def _find_prompt_executor(parent_state: Mapping[str, Any], parent_dir: Path) -> Path:
    history = parent_state.get("history")
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict) or item.get("route") != "PROMPT":
                continue
            raw_path = item.get("prompt_path")
            if isinstance(raw_path, str):
                path = parent_dir / raw_path
                if path.is_file() and BASELINE_MARKER in path.read_text(encoding="utf-8"):
                    return path
    for path in sorted(parent_dir.glob("manual-*-prompt-request.md"), reverse=True):
        text = path.read_text(encoding="utf-8")
        if "PROMPT 실행기" in text and BASELINE_MARKER in text:
            return path
    raise ManualPromptAblationError("원본 PROMPT 실행기 지시문을 찾지 못했습니다.")


def _parent_result(parent_state: Mapping[str, Any], parent_dir: Path) -> str:
    output_path = parent_dir / str(parent_state.get("output_path") or "output.md")
    if output_path.is_file() and output_path.read_text(encoding="utf-8").strip():
        return output_path.read_text(encoding="utf-8").strip()
    history = parent_state.get("history")
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict) or item.get("route") != "PROMPT":
                continue
            raw_path = item.get("response_path")
            if not isinstance(raw_path, str):
                continue
            value = _read_json(parent_dir / raw_path, raw_path)
            execution = value.get("execution")
            if isinstance(execution, dict) and isinstance(
                execution.get("result_markdown"), str
            ):
                return execution["result_markdown"].strip()
    raise ManualPromptAblationError("원본 PROMPT 결과 본문을 찾지 못했습니다.")


def _build_variants(
    executor_prompt: str,
    request: str,
    ledger: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    baseline = _extract_json_after_marker(executor_prompt, BASELINE_MARKER)
    if baseline is None:
        raise ManualPromptAblationError("원본 지시문에서 Prompt Compiler baseline을 복원하지 못했습니다.")
    ledger_marker = "[Goal Ledger]"
    profile_marker = "[현재 실행 프로필]"
    request_marker = "[사용자 요청]"
    trust_marker = "[수동 브리지 신뢰 규칙]"
    positions = {
        marker: executor_prompt.find(marker)
        for marker in (ledger_marker, profile_marker, request_marker, trust_marker)
    }
    if any(position < 0 for position in positions.values()):
        raise ManualPromptAblationError("원본 PROMPT 지시문의 구간 경계를 찾지 못했습니다.")
    if not (
        positions[ledger_marker]
        < positions[profile_marker]
        < positions[request_marker]
        < positions[trust_marker]
    ):
        raise ManualPromptAblationError("원본 PROMPT 지시문의 구간 순서가 예상과 다릅니다.")

    prefix = executor_prompt[: positions[ledger_marker]].rstrip()
    profile_block = executor_prompt[
        positions[profile_marker] : positions[request_marker]
    ].strip()
    suffix = executor_prompt[positions[trust_marker] :].strip()
    ledger_json = json.dumps(ledger, ensure_ascii=False, indent=2)
    baseline_json = json.dumps(baseline, ensure_ascii=False, indent=2)
    compact_json = json.dumps(_compact_ledger(ledger), ensure_ascii=False, indent=2)
    brief_prefix = prefix.replace(
        "기존 Prompt Compiler baseline을 출발점으로 삼아",
        "아래 Prompt Build Brief를 출발점으로 삼아",
    ).replace(
        "baseline을 바꿀 때는 목적·제약·출력 계약을 보존하고",
        "brief를 구체화할 때는 목적·제약·출력 계약을 보존하고",
    )
    variants = {
        "without_raw_request": (
            f"{prefix}\n\n[Goal Ledger]\n{ledger_json}\n\n{profile_block}"
            f"\n\n{BASELINE_MARKER}\n{baseline_json}\n\n{suffix}"
        ),
        "compact_ledger": (
            f"{prefix}\n\n[Compact Goal Contract]\n{compact_json}\n\n{profile_block}"
            f"\n\n{BASELINE_MARKER}\n{baseline_json}\n\n{suffix}"
        ),
        "single_build_brief": (
            f"{brief_prefix}\n\n{profile_block}\n\n{_single_brief(ledger, baseline)}"
            f"\n\n{suffix}"
        ),
    }
    metadata = {
        name: {
            "characters": len(prompt),
            "exact_request_occurrences": prompt.count(request),
            "contains_full_goal_ledger": ledger_json in prompt,
            "contains_full_compiler_baseline": baseline_json in prompt,
            "contains_single_build_brief": "[Prompt Build Brief]" in prompt,
        }
        for name, prompt in variants.items()
    }
    return variants, metadata


def _candidate_mapping(run_id: str) -> dict[str, str]:
    offset = int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16) % 4
    rotated = list(VARIANT_ORDER[offset:] + VARIANT_ORDER[:offset])
    return {chr(ord("A") + index): variant for index, variant in enumerate(rotated)}


def _assessment_prompt(
    manual: Any,
    request: str,
    ledger: Mapping[str, Any],
    mapping: Mapping[str, str],
    results: Mapping[str, str],
) -> str:
    constraints = ledger.get("fixed_constraints")
    if not isinstance(constraints, list):
        constraints = []
    candidates = "\n\n".join(
        f"[후보 {candidate_id}]\n{results[variant].strip()}"
        for candidate_id, variant in mapping.items()
    )
    base = f"""당신은 재사용 프롬프트 생성 실험의 블라인드 평가자다.

아래 네 후보는 같은 사용자 요청을 서로 다른 내부 입력 구조로 처리한 결과다. 내부 변형 이름은 공개되지 않는다.

[평가 기준]
1. 사용자 목표와 고정 조건을 실제로 보존하는지 확인한다.
2. 핵심 작업 절차가 보조 분석 도구·안전 규칙·출력 형식보다 먼저 보이고 우선되는지 평가한다.
3. 같은 뜻의 규칙과 형식이 반복되어 실제 작업을 방해하는지 평가한다.
4. 다른 AI가 그대로 반복 사용할 때 실용적인지 평가한다.
5. 짧다는 이유만으로 높게 평가하지 않는다. 중요한 조건을 잃은 압축은 실패다.
6. 후보에 없는 장점이나 충족 여부를 추측하지 않는다.
7. 내부 추론은 쓰지 말고 각 판정의 짧은 근거만 반환한다.

[사용자 요청]
{request.strip()}

[고정 조건]
{json.dumps(constraints, ensure_ascii=False, indent=2)}

[완료 조건]
{str(ledger.get('completion_condition') or '').strip()}

{candidates}
"""
    try:
        schema = ASSESSMENT_SCHEMA.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ManualPromptAblationError(f"비교 평가 schema를 읽을 수 없습니다: {exc}") from exc
    return f"""{base.rstrip()}

[반환 계약: prompt-ablation-assessment]
아래 JSON Schema를 만족하는 JSON 객체 하나만 반환한다. 코드 펜스나 설명문을 붙이지 않는다.

{schema}
"""


def _validate_assessment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version",
        "variants",
        "preferred_candidate_ids",
        "conclusion",
    }:
        raise ManualPromptAblationError("블라인드 평가 결과 필드가 계약과 일치하지 않습니다.")
    if value["version"] != 1:
        raise ManualPromptAblationError("지원하지 않는 블라인드 평가 버전입니다.")
    variants = value["variants"]
    if not isinstance(variants, list) or len(variants) != 4:
        raise ManualPromptAblationError("블라인드 평가에는 후보 네 개의 판정이 필요합니다.")
    expected_fields = {
        "candidate_id",
        "requirement_preservation",
        "procedure_clarity",
        "repetition_pressure",
        "format_pressure",
        "practical_reusability",
        "finding",
        "missing_conditions",
    }
    ids: set[str] = set()
    for item in variants:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ManualPromptAblationError("후보별 블라인드 평가 필드가 계약과 일치하지 않습니다.")
        candidate_id = item["candidate_id"]
        if candidate_id not in {"A", "B", "C", "D"} or candidate_id in ids:
            raise ManualPromptAblationError("블라인드 평가 candidate_id가 유효하지 않습니다.")
        ids.add(candidate_id)
        if item["requirement_preservation"] not in {"satisfied", "partial", "failed"}:
            raise ManualPromptAblationError("요구 보존 판정이 유효하지 않습니다.")
        if item["procedure_clarity"] not in {"strong", "mixed", "weak"}:
            raise ManualPromptAblationError("절차 선명도 판정이 유효하지 않습니다.")
        for field in ("repetition_pressure", "format_pressure"):
            if item[field] not in {"low", "medium", "high"}:
                raise ManualPromptAblationError(f"{field} 판정이 유효하지 않습니다.")
        if item["practical_reusability"] not in {"strong", "mixed", "weak"}:
            raise ManualPromptAblationError("재사용성 판정이 유효하지 않습니다.")
        if not isinstance(item["finding"], str) or not item["finding"].strip():
            raise ManualPromptAblationError("후보 판정 근거가 비어 있습니다.")
        if not isinstance(item["missing_conditions"], list) or not all(
            isinstance(condition, str) and condition.strip()
            for condition in item["missing_conditions"]
        ):
            raise ManualPromptAblationError("누락 조건 목록이 유효하지 않습니다.")
    preferred = value["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or not 1 <= len(preferred) <= 2
        or len(set(preferred)) != len(preferred)
        or any(item not in ids for item in preferred)
    ):
        raise ManualPromptAblationError("선호 후보 판정이 유효하지 않습니다.")
    if not isinstance(value["conclusion"], str) or not value["conclusion"].strip():
        raise ManualPromptAblationError("블라인드 평가 결론이 비어 있습니다.")
    return value


def _render_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# PROMPT 입력 구조 비교",
        "",
        f"원본 run: `{report['parent_run_id']}`",
        "",
        "## 구조 지표",
        "",
        "| 변형 | 문자 | 제목 | 규칙 표현 | 안전 문구 | 반복 쌍 | 조건 표면 보존 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANT_ORDER:
        metrics = report["results"][variant]["metrics"]
        lines.append(
            f"| {VARIANT_LABELS[variant]} | {metrics['characters']} | "
            f"{metrics['headings']} | {metrics['rule_marker_hits']} | "
            f"{metrics['safety_marker_hits']} | {metrics['duplicate_pair_count']} | "
            f"{metrics['average_constraint_token_coverage']:.0%} |"
        )
    assessment = report["assessment"]
    mapping = report["candidate_mapping"]
    by_id = {item["candidate_id"]: item for item in assessment["variants"]}
    preferred = [VARIANT_LABELS[mapping[item]] for item in assessment["preferred_candidate_ids"]]
    lines.extend(
        [
            "",
            "## 블라인드 평가",
            "",
            "선호 변형: **" + ", ".join(preferred) + "**",
            "",
            assessment["conclusion"],
            "",
        ]
    )
    for candidate_id, variant in mapping.items():
        item = by_id[candidate_id]
        lines.append(
            f"- **{VARIANT_LABELS[variant]}**: 조건 {item['requirement_preservation']} · "
            f"절차 {item['procedure_clarity']} · 반복 {item['repetition_pressure']} · "
            f"형식 {item['format_pressure']} · 재사용 {item['practical_reusability']} — "
            f"{item['finding']}"
        )
    lines.extend(
        [
            "",
            "## 해석 경계",
            "",
            "이 비교는 생성된 프롬프트 자체를 평가했습니다. 실제 차트 이미지에 각 프롬프트를 적용한 매매 판단 품질은 아직 비교하지 않았습니다.",
            "토큰 겹침 수치는 표면 신호이며, 조건의 의미가 보존됐다는 증명으로 사용하지 않았습니다.",
            "",
        ]
    )
    return "\n".join(lines)


class ManualPromptAblation:
    def __init__(self, bridge: Any, manual_module: Any, problem_os: Any):
        self.bridge = bridge
        self.manual = manual_module
        self.problem_os = problem_os

    def _public(self, state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        return self.manual.public_state(state, run_dir)

    def _prepare_variant(
        self,
        run_dir: Path,
        state: dict[str, Any],
        variant: str,
    ) -> None:
        prompt_path = run_dir / state["ablation"]["input_files"][variant]
        prompt = prompt_path.read_text(encoding="utf-8")
        self.bridge.set_prompt(
            run_dir,
            state,
            f"ablation_{variant}",
            "PROMPT",
            variant,
            prompt,
            self.problem_os.EXECUTION_SCHEMA_PATH,
        )

    def _load_results(self, run_dir: Path) -> dict[str, str]:
        results = {}
        for variant in VARIANT_ORDER:
            path = run_dir / "prompt_ablation" / "results" / f"{variant}.md"
            if not path.is_file():
                raise ManualPromptAblationError(
                    f"비교 결과가 아직 없습니다: {VARIANT_LABELS[variant]}"
                )
            results[variant] = path.read_text(encoding="utf-8").strip()
        return results

    def _prepare_assessment(self, run_dir: Path, state: dict[str, Any]) -> None:
        results = self._load_results(run_dir)
        prompt = _assessment_prompt(
            self.manual,
            state["request"],
            state["route_payload"]["goal_ledger"],
            state["ablation"]["candidate_mapping"],
            results,
        )
        self.bridge.set_prompt(
            run_dir,
            state,
            "ablation_assessment",
            None,
            "blind_assessment",
            prompt,
            ASSESSMENT_SCHEMA,
        )

    def start(self, parent_run_id: str) -> dict[str, Any]:
        with self.bridge.lock:
            parent_dir = self.bridge.run_dir(parent_run_id)
            if not parent_dir.is_dir():
                raise ManualPromptAblationError("비교할 원본 run을 찾을 수 없습니다.")
            parent_state = self.manual.read_state(parent_dir)
            if parent_state.get("state") != "completed":
                raise ManualPromptAblationError("완료된 결과만 비교할 수 있습니다.")
            if parent_state.get("session_kind", "psos") != "psos":
                raise ManualPromptAblationError("비교 결과를 다시 비교 대상으로 사용할 수 없습니다.")
            route_record = _read_json(parent_dir / "route.json", "원본 route.json")
            if route_record.get("selected_route") != "PROMPT":
                raise ManualPromptAblationError("현재는 PROMPT 단일 경로 결과만 구조 비교할 수 있습니다.")
            ledger = _read_json(parent_dir / "goal_ledger.json", "원본 Goal Ledger")
            request = (parent_dir / "request.txt").read_text(encoding="utf-8").strip()
            executor_path = _find_prompt_executor(parent_state, parent_dir)
            executor_prompt = executor_path.read_text(encoding="utf-8")
            variants, metadata = _build_variants(executor_prompt, request, ledger)
            current_result = _parent_result(parent_state, parent_dir)

            run_id = self.problem_os.make_run_id()
            run_dir = self.bridge.run_dir(run_id)
            if run_dir.exists():
                raise ManualPromptAblationError(f"이미 존재하는 비교 run-id입니다: {run_id}")
            run_dir.mkdir(parents=True)
            (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
            _write_json(self.manual, run_dir / "goal_ledger.json", ledger)
            work_dir = run_dir / "prompt_ablation"
            inputs_dir = work_dir / "inputs"
            results_dir = work_dir / "results"
            inputs_dir.mkdir(parents=True)
            results_dir.mkdir(parents=True)
            input_files = {}
            for variant, prompt in variants.items():
                path = inputs_dir / f"{variant}.md"
                path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
                input_files[variant] = path.relative_to(run_dir).as_posix()
            (results_dir / "current.md").write_text(
                current_result.rstrip() + "\n",
                encoding="utf-8",
            )
            _write_json(
                self.manual,
                results_dir / "current.json",
                {
                    "source": "parent_output",
                    "parent_run_id": parent_run_id,
                    "result_markdown": current_result,
                },
            )
            now = self.manual.utc_now()
            route_payload = {
                "goal_ledger": ledger,
                "route": {
                    "selected_route": "PROMPT",
                    "primary_route": None,
                    "secondary_route": None,
                    "route_reason": "완료된 PROMPT 결과의 입력 구조를 통제 비교",
                },
            }
            state = {
                "version": 1,
                "session_kind": "prompt_ablation",
                "run_id": run_id,
                "request": request,
                "original_request": request,
                "search_enabled": False,
                "research_mode": "none",
                "parent_run_id": parent_run_id,
                "revision_feedback": None,
                "state": "created",
                "created_at": now,
                "updated_at": now,
                "route_payload": route_payload,
                "primary_execution": None,
                "prompt_compiler": None,
                "deep_research_reports": {},
                "stage": None,
                "history": [],
                "error": None,
                "model_policy": parent_state.get("model_policy", {}),
                "ablation": {
                    "version": 1,
                    "parent_run_id": parent_run_id,
                    "source_prompt_path": executor_path.name,
                    "new_variants": list(NEW_VARIANTS),
                    "completed_variants": [],
                    "input_files": input_files,
                    "input_metadata": metadata,
                    "candidate_mapping": _candidate_mapping(run_id),
                },
            }
            _write_json(
                self.manual,
                work_dir / "manifest.json",
                {
                    **state["ablation"],
                    "experiment_boundary": (
                        "원본 결과는 보존하며 세 변형과 블라인드 평가만 수동으로 실행합니다."
                    ),
                },
            )
            _write_json(
                self.manual,
                run_dir / "route.json",
                {
                    **route_payload["route"],
                    "execution_status": "in_progress",
                    "parent_run_id": parent_run_id,
                    "session_kind": "prompt_ablation",
                },
            )
            self._prepare_variant(run_dir, state, NEW_VARIANTS[0])
            self.bridge.save(run_dir, state)
            return self._public(state, run_dir)

    def _finalize(self, run_dir: Path, state: dict[str, Any], assessment: dict[str, Any]) -> None:
        results_text = self._load_results(run_dir)
        constraints = state["route_payload"]["goal_ledger"].get("fixed_constraints")
        if not isinstance(constraints, list):
            constraints = []
        result_records = {
            variant: {
                "label": VARIANT_LABELS[variant],
                "path": f"prompt_ablation/results/{variant}.md",
                "metrics": _metrics(
                    results_text[variant],
                    [item for item in constraints if isinstance(item, str)],
                ),
            }
            for variant in VARIANT_ORDER
        }
        report = {
            "version": 1,
            "run_id": state["run_id"],
            "parent_run_id": state["parent_run_id"],
            "results": result_records,
            "candidate_mapping": state["ablation"]["candidate_mapping"],
            "assessment": assessment,
            "original_result_preserved": True,
            "comparison_boundary": (
                "생성된 프롬프트를 비교했으며 실제 차트 적용 결과는 아직 비교하지 않았습니다."
            ),
        }
        work_dir = run_dir / "prompt_ablation"
        _write_json(self.manual, work_dir / "comparison.json", report)
        markdown = _render_report(report)
        (work_dir / "comparison.md").write_text(markdown, encoding="utf-8")
        (run_dir / "output.md").write_text(markdown, encoding="utf-8")
        (run_dir / "result.md").write_text(
            "# PROMPT 구조 비교 감사 기록\n\n"
            f"부모 run: `{state['parent_run_id']}`\n\n"
            f"{markdown}\n\n"
            "내부 입력과 개별 응답은 `prompt_ablation/` 및 `manual-handoff.json`에 보존됩니다.\n",
            encoding="utf-8",
        )
        route_path = run_dir / "route.json"
        route_record = _read_json(route_path, "비교 route.json")
        route_record["execution_status"] = "completed"
        route_record["comparison"] = {
            "report": "prompt_ablation/comparison.json",
            "markdown": "prompt_ablation/comparison.md",
            "assessment": "prompt_ablation/results/blind_assessment.json",
        }
        _write_json(self.manual, route_path, route_record)
        state["output_path"] = "output.md"
        state["state"] = "completed"
        state["stage"] = None
        state["error"] = None
        state["finished_at"] = self.manual.utc_now()
        self.bridge.save(run_dir, state)

    def submit(self, run_id: str, response: str) -> dict[str, Any]:
        with self.bridge.lock:
            run_dir = self.bridge.run_dir(run_id)
            if not run_dir.is_dir():
                raise ManualPromptAblationError("해당 비교 run을 찾을 수 없습니다.")
            state = self.manual.read_state(run_dir)
            if state.get("session_kind") != "prompt_ablation":
                raise ManualPromptAblationError("PROMPT 구조 비교 세션이 아닙니다.")
            if state.get("state") == "completed":
                return self._public(state, run_dir)
            if not str(state.get("state", "")).startswith("awaiting_ablation_"):
                raise ManualPromptAblationError("현재 비교 응답을 받을 단계가 아닙니다.")
            stage = state["stage"]
            try:
                value, normalized = self.manual.parse_response(response)
                if stage["phase"] == "ablation_assessment":
                    assessment = _validate_assessment(value)
                    self.bridge.record(run_dir, state, response, normalized)
                    assessment_path = (
                        run_dir / "prompt_ablation" / "results" / "blind_assessment.json"
                    )
                    _write_json(self.manual, assessment_path, assessment)
                    self._finalize(run_dir, state, assessment)
                    return self._public(state, run_dir)

                variant = stage["stage_label"]
                if variant not in NEW_VARIANTS:
                    raise ManualPromptAblationError("알 수 없는 PROMPT 비교 변형입니다.")
                execution = self.problem_os.validate_execution_output(
                    value,
                    "PROMPT",
                    self.manual.profile(False),
                    self.manual.capabilities(False),
                )
                if execution["status"] not in {"completed", "partial"}:
                    raise ManualPromptAblationError(
                        "비교 후보는 실제 프롬프트 본문을 포함한 completed 또는 partial 결과여야 합니다."
                    )
                self.bridge.record(run_dir, state, response, normalized)
                results_dir = run_dir / "prompt_ablation" / "results"
                _write_json(self.manual, results_dir / f"{variant}.json", execution)
                (results_dir / f"{variant}.md").write_text(
                    execution["result_markdown"].strip() + "\n",
                    encoding="utf-8",
                )
                completed = state["ablation"]["completed_variants"]
                if variant not in completed:
                    completed.append(variant)
                next_index = len(completed)
                if next_index < len(NEW_VARIANTS):
                    self._prepare_variant(run_dir, state, NEW_VARIANTS[next_index])
                else:
                    self._prepare_assessment(run_dir, state)
                state["error"] = None
                self.bridge.save(run_dir, state)
                return self._public(state, run_dir)
            except (
                self.problem_os.ProblemSolvingError,
                self.manual.ManualBridgeError,
                ManualPromptAblationError,
            ) as exc:
                state["error"] = str(exc)
                self.bridge.save(run_dir, state)
                raise ManualPromptAblationError(str(exc)) from exc
