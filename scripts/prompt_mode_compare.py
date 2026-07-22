#!/usr/bin/env python3
"""Route prompt generation conservatively and compare corpus-backed modes.

The routing dry-run stops after baseline-first analysis and evidence selection.
The legacy comparison command still stops after prompt generation. Neither
command executes or evaluates the generated prompts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "scripts" / "corpus_pipeline.py"
MANIFEST_PATH = ROOT / "prompt-corpus" / "corpus-manifest.json"
DRAFTS_DIR = ROOT / "prompt-corpus" / "pipeline-drafts"
SCHEMA_PATH = ROOT / "prompt-corpus" / "prompt-mode-generation.schema.json"
WORKFLOW_PATH = ROOT / "skills" / "prompt-design-workflow.md"
PATTERN_INDEX_PATH = ROOT / "prompt-corpus" / "PATTERN_LESSONS_INDEX.md"
CONTRIBUTION_EXPERIMENT_DIR = (
    ROOT / "specs" / "experiments" / "prompt-mode-contribution"
)
CONTRIBUTION_SCHEMA_PATH = CONTRIBUTION_EXPERIMENT_DIR / "active-contribution.schema.json"
HOLDOUT_REQUESTS_PATH = CONTRIBUTION_EXPERIMENT_DIR / "holdout-requests.json"
ACTIVE_SOURCE_POLICIES_PATH = CONTRIBUTION_EXPERIMENT_DIR / "active-source-policies.json"
ACTUAL_USAGE_REQUESTS_PATH = CONTRIBUTION_EXPERIMENT_DIR / "actual-usage-requests.json"
DEFAULT_REQUESTS_PATH = (
    ROOT / "specs" / "experiments" / "corpus-mode-minimal" / "requests.json"
)
RUNS_DIR = ROOT / "reports" / "prompt-mode-comparison"
MODES = ("full", "active")
ROUTED_MODES = ("baseline", "pattern-only", "active")
EXPERT_CASES_DIR = ROOT / "specs" / "experiments" / "expert-collaboration" / "cases"
EXPERT_CASE_IDS = ("A3", "A7", "C9", "C10", "C11", "C13", "C14", "C16")

CONTRIBUTION_TYPES = {
    "new_core_constraint",
    "decision_changing_variable",
    "concrete_counterexample",
    "realistic_alternative",
    "executable_validation",
    "stop_expand_switch_rule",
    "material_deliverable_improvement",
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+_.-]*|[가-힣]{2,}", re.IGNORECASE)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "with", "you", "your", "prompt", "make", "create", "write", "please",
    "그리고", "또는", "위해", "대한", "현재", "사용자", "해주세요", "합니다",
}

PATTERN_HINTS = {
    "Role + Task Frame": (
        "explain", "beginner", "audience", "role", "expert", "설명", "초보자", "대상 독자", "역할", "전문가",
    ),
    "Interface Emulation": (
        "terminal", "simulate", "simulation", "interface", "command", "터미널", "시뮬레이션", "인터페이스", "명령",
    ),
    "Prompt Improvement Loop": (
        "improve", "rewrite", "prompt enhancer", "clearer", "overbuilt", "개선", "다시 작성", "수정 후 재실행",
        "반대 가설", "가정 검토", "재검증",
    ),
    "Defensive Jailbreak Analysis": (
        "jailbreak", "ignore safety", "restrictions", "adversarial", "unsafe", "탈옥", "안전 무시", "적대적", "우회",
    ),
    "Grounded Research": (
        "research", "source", "citation", "compare product", "recommend", "uncertainty", "조사", "출처", "인용",
        "상품 비교", "근거", "불확실성",
    ),
    "Structured Output / Extraction": (
        "extract", "json", "schema", "structured output", "invoice", "null", "추출", "스키마", "구조화 출력",
        "필수 필드", "출력 형식", "표", "계산",
    ),
    "Evaluation Rubric": (
        "evaluate", "rubric", "score", "criteria", "regression", "compare outputs", "평가", "루브릭", "점수",
        "기준", "회귀", "결과 비교", "판정", "중단 기준", "확대 기준",
    ),
    "Persistent Project Instruction": (
        "project instruction", "keep answers", "persistent", "always", "ui action", "프로젝트 지침", "항상", "지속 규칙",
    ),
    "Coding-Agent Workflow": (
        "coding agent", "repository", "repo", "files and tools", "run tests", "destructive", "코딩 에이전트",
        "저장소", "파일 수정", "테스트 실행", "스크립트", "파이프라인",
    ),
}

SEMANTIC_CUES = {
    "coding_action": (
        "repository", "repo", "file", "script", "pipeline", "commit", "저장소", "파일", "스크립트", "파이프라인",
        "구현", "수정", "커밋",
    ),
    "structured_artifact": (
        "json", "schema", "extract", "table", "calculation", "comparison", "output contract", "구조화", "추출", "표",
        "계산", "비교", "필수 산출물", "출력 형식", "상태 전이",
    ),
    "evaluation_design": (
        "evaluate", "evaluation", "rubric", "score", "experiment", "blind", "adjudication", "평가", "실험", "점수",
        "루브릭", "블라인드", "판정", "반복 실행",
    ),
    "evidence_reasoning": (
        "evidence", "source", "citation", "research", "uncertainty", "근거", "출처", "조사", "불확실성", "원문",
    ),
    "tradeoff": (
        "tradeoff", "cost", "budget", "risk", "versus", "alternative", "비용", "예산", "위험", "충돌", "대안",
        "장단점", "수익성", "브랜드", "유지율", "사생활", "냉난방",
    ),
    "long_term_risk": (
        "long term", "short term", "lifetime", "rollback", "maintenance", "장기", "단기", "평생", "롤백", "유지관리",
        "이탈", "갱신", "기술 부채", "부작용",
    ),
    "decision_gate": (
        "stop", "expand", "gate", "pass", "fail", "threshold", "중단", "확대", "계속", "보류", "기준", "임계값",
    ),
    "reversible_test": (
        "reversible", "pilot", "test", "rerun", "validate", "가역", "파일럿", "시험", "재실행", "검증", "반증",
    ),
    "assumption_challenge": (
        "prove", "wrong", "best", "conclusion", "contrarian", "assumption", "증명", "틀렸", "최선", "결론", "찬성",
        "반대 가설", "전제", "가정", "완전히 분리", "최대한 통창",
    ),
}

PATTERNS_BY_CONCEPT = {
    "coding_action": ("Coding-Agent Workflow",),
    "structured_artifact": ("Structured Output / Extraction",),
    "evaluation_design": ("Evaluation Rubric", "Structured Output / Extraction"),
    "evidence_reasoning": ("Grounded Research",),
    "decision_gate": ("Evaluation Rubric",),
    "reversible_test": ("Prompt Improvement Loop", "Evaluation Rubric"),
    "assumption_challenge": ("Prompt Improvement Loop", "Evaluation Rubric"),
}

PROPOSED_SOLUTION_CUES = (
    "해 주세요", "하겠습니다", "하려 합니다", "없애", "제거", "한 화면", "평생", "퇴사", "전면 재작성", "설문",
    "모두 완전히", "최대한 통창", "use ", "must ", "only ", "remove ", "prove ",
)
EPISTEMIC_CAPTURE_CUES = (
    "증명", "틀렸", "답이라는", "찬성 비율", "찬성 60%", "평생 50%", "모든 신규 고객", "모두 완전히",
    "최대한 통창", "prove", "wrong", "predetermined conclusion",
)

GENERATION_INSTRUCTIONS = """Turn the user request into one ready-to-use prompt.
Use only the supplied corpus evidence; do not open or infer from other repository files.
Apply the smallest useful supported pattern. Preserve the user's real goal.
Add a concrete output contract and one missing-information or safety fallback when useful.
Do not mention source IDs or corpus research inside the final prompt.
Return JSON only. selected_patterns must use exact supplied pattern names.
used_reusable_moves must copy exact supplied reusable moves, not paraphrases.
This stage only writes the prompt; do not answer or execute it."""


class CompareError(Exception):
    pass


def load_pipeline() -> Any:
    spec = importlib.util.spec_from_file_location("corpus_pipeline", PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise CompareError("Could not load scripts/corpus_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompareError(f"Missing file: {path.relative_to(ROOT).as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise CompareError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def section(text: str, heading: str) -> str | None:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match and match.group(1).strip() else None


def embedded_field(text: str | None, field: str) -> str | None:
    """Read lesson fields embedded in legacy local evidence-note bullets."""
    match = re.search(
        rf"\*\*{re.escape(field)}:\*\*\s*(.*?)(?=\s+\*\*[^*]+:\*\*|\Z)",
        text or "",
        re.DOTALL | re.IGNORECASE,
    )
    return " ".join(match.group(1).split()) if match and match.group(1).strip() else None


def tokenize(text: str | None) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall((text or "").lower()):
        parts = [raw]
        if any(char in raw for char in "-_."):
            parts.extend(part for part in re.split(r"[-_.]+", raw) if part)
        tokens.extend(token for token in parts if len(token) > 1 and token not in STOP_WORDS)
    return tokens


def contains_any(text: str, cues: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(cue.lower() in lowered for cue in cues)


def semantic_concepts(text: str) -> set[str]:
    """Map Korean or English prose to task concepts, not just pattern-name hits."""
    return {
        concept for concept, cues in SEMANTIC_CUES.items()
        if contains_any(text, cues)
    }


def public_request_text(public: dict[str, Any]) -> str:
    initial = public.get("initial_information") or []
    if isinstance(initial, str):
        initial = [initial]
    conditions = public.get("initial_conditions") or []
    if isinstance(conditions, str):
        conditions = [conditions]
    return "\n".join([
        str(public.get("user_request") or ""),
        *(str(item) for item in initial),
        *(str(item) for item in conditions),
        str(public.get("tools_allowed") or ""),
    ])


def load_active_source_policies(path: Path = ACTIVE_SOURCE_POLICIES_PATH) -> dict[str, Any]:
    payload = read_json(path)
    required_root = {
        "version", "mode", "full_corpus_auto_search", "max_auto_sources_per_request",
        "excluded_source_ids", "sources",
    }
    if not isinstance(payload, dict) or set(payload) != required_root:
        raise CompareError("Active source policy registry fields are invalid.")
    if payload["full_corpus_auto_search"] is not False:
        raise CompareError("Full corpus automatic search must remain disabled.")
    if payload["max_auto_sources_per_request"] != 1:
        raise CompareError("Production active routing must select one minimal source at most.")
    sources = payload["sources"]
    if not isinstance(sources, list) or len(sources) != 7:
        raise CompareError("Production active registry must contain exactly seven sources.")
    required_source = {
        "source_id", "task_types", "required_request_signals", "do_not_apply",
        "unique_behavior", "required_prompt_changes", "fallback", "matching",
    }
    ids = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != required_source:
            raise CompareError("An active source policy has invalid fields.")
        ids.append(source["source_id"])
        matching = source["matching"]
        if not isinstance(matching, dict) or set(matching) != {
            "task_type_any", "required_all", "exclude_any", "requires_runtime_tools",
        }:
            raise CompareError(f"Invalid matching policy for {source['source_id']}.")
        if not matching["task_type_any"] or not matching["required_all"]:
            raise CompareError(f"Incomplete matching policy for {source['source_id']}.")
        for group in matching["required_all"]:
            if not isinstance(group, dict) or set(group) != {"id", "any"} or not group["any"]:
                raise CompareError(f"Invalid required signal group for {source['source_id']}.")
    if len(set(ids)) != len(ids):
        raise CompareError("Duplicate source ID in active source policy registry.")
    if set(ids) & set(payload["excluded_source_ids"]):
        raise CompareError("A production active source is also listed as excluded.")
    return payload


def policy_gate_decision(
    public: dict[str, Any], policy: dict[str, Any],
) -> tuple[bool, list[str], str]:
    text = public_request_text(public)
    matching = policy["matching"]
    excluded = [cue for cue in matching["exclude_any"] if contains_any(text, (cue,))]
    if excluded:
        return False, [], "적용 금지 신호와 일치: " + ", ".join(excluded[:3])
    task_matches = [
        cue for cue in matching["task_type_any"] if contains_any(text, (cue,))
    ]
    if not task_matches:
        return False, [], "작업 유형이 자료의 적용 범위와 일치하지 않음"
    matched_groups = []
    missing_groups = []
    for group in matching["required_all"]:
        matches = [cue for cue in group["any"] if contains_any(text, (cue,))]
        if matches:
            matched_groups.append(f"{group['id']}={matches[0]}")
        else:
            missing_groups.append(group["id"])
    if missing_groups:
        return False, [], "필수 요청 신호 누락: " + ", ".join(missing_groups)
    if matching["requires_runtime_tools"] and not bool(public.get("tools_allowed")):
        return False, [], "고유 행동 실행에 필요한 파일·도구 사용 권한이 없음"
    return True, [f"task_type={task_matches[0]}", *matched_groups], ""


def active_policy_matches(
    public: dict[str, Any], registry: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    registry = registry or load_active_source_policies()
    matches = {}
    for policy in registry["sources"]:
        passed, signals, reason = policy_gate_decision(public, policy)
        matches[policy["source_id"]] = {
            "passed": passed,
            "matched_signals": signals,
            "reason": reason,
        }
    return matches


def baseline_first_analysis(public: dict[str, Any]) -> dict[str, Any]:
    """Inspect purpose, proposed means, constraints, artifacts, and tool reality first."""
    request = str(public.get("user_request") or "")
    combined = public_request_text(public)
    concepts = semantic_concepts(combined)
    proposed_solution = contains_any(request, PROPOSED_SOLUTION_CUES)
    epistemic_capture = contains_any(request, EPISTEMIC_CAPTURE_CUES)
    tools_available = bool(public.get("tools_allowed"))
    repository_action = "coding_action" in semantic_concepts(request) and contains_any(
        request, ("구현", "수정", "제거", "자동화", "apply", "implement", "change", "remove")
    )
    artifact_risk = bool(
        concepts & {"structured_artifact", "evaluation_design", "tradeoff", "decision_gate"}
    )
    needs_counter_hypothesis = bool(
        epistemic_capture or (proposed_solution and "assumption_challenge" in concepts)
    )
    active_search_candidate = bool(
        "evaluation_design" in concepts
        or needs_counter_hypothesis
        or (
            proposed_solution
            and bool(concepts & {"tradeoff", "long_term_risk", "reversible_test", "decision_gate"})
        )
    )
    fallback_mode = "pattern-only" if artifact_risk else "baseline"
    tool_mismatch = bool(repository_action and not tools_available)
    return {
        "actual_purpose": request.strip(),
        "proposed_solution_present": proposed_solution,
        "fixed_constraints_present": bool(public.get("initial_information")),
        "required_artifact_risk": artifact_risk,
        "tools_available": tools_available,
        "repository_tool_mismatch": tool_mismatch,
        "semantic_concepts": sorted(concepts),
        "epistemic_capture": epistemic_capture,
        "needs_counter_hypothesis": needs_counter_hypothesis,
        "active_search_candidate": active_search_candidate and not tool_mismatch,
        "fallback_mode": "baseline" if tool_mismatch else fallback_mode,
    }


def active_source(source: dict[str, Any]) -> bool:
    """Use only records that carry all three automatic-verification traces."""
    return bool(
        source.get("automation_status") == "applied"
        and source.get("upgrade_status") in {"verified", "tested"}
        and source.get("source_checked") is True
        and source.get("verification_basis") == "external-source"
        and source.get("verified_at")
        and source.get("last_automation_run")
        and not source.get("deferred_reasons")
        and source.get("duplicate_status") not in {"alias", "deferred"}
    )


def load_documents() -> list[dict[str, Any]]:
    pipeline = load_pipeline()
    manifest = pipeline.load_manifest(MANIFEST_PATH)
    corpus = {item["source_id"]: item for item in pipeline.parse_corpus()}
    documents: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        source_id = source["source_id"]
        raw = corpus[source_id]
        lesson = dict(raw.get("lesson") or {})
        draft_path = DRAFTS_DIR / f"{source_id}.md"
        if draft_path.is_file():
            draft = draft_path.read_text(encoding="utf-8")
            lesson = {
                "pattern_lesson": section(draft, "Pattern lesson"),
                "mechanism": section(draft, "Mechanism"),
                "failure_mode": section(draft, "Failure mode"),
                "reusable_move": section(draft, "Reusable move"),
            }
        documents.append(
            {
                **source,
                "evidence_note": source.get("evidence_note") or raw.get("evidence_note"),
                "lesson": {
                    **lesson,
                    "reusable_move": lesson.get("reusable_move") or embedded_field(
                        source.get("evidence_note") or raw.get("evidence_note"), "Reusable move"
                    ),
                },
                "active": active_source(source),
            }
        )
    return documents


def searchable_fields(source: dict[str, Any]) -> dict[str, str]:
    lesson = source.get("lesson") or {}
    return {
        "metadata": " ".join(
            str(value or "")
            for value in (
                source.get("name"), source.get("source_type"),
                " ".join(source.get("tags") or []),
                " ".join(source.get("related_patterns") or []),
            )
        ),
        "evidence": str(source.get("evidence_note") or ""),
        "lesson": " ".join(
            str(lesson.get(key) or "")
            for key in ("pattern_lesson", "mechanism", "failure_mode")
        ),
        "move": str(lesson.get("reusable_move") or ""),
    }


def hinted_patterns(request: str) -> list[str]:
    lowered = request.lower()
    lexical = {
        pattern for pattern, hints in PATTERN_HINTS.items()
        if any(hint in lowered for hint in hints)
    }
    conceptual = {
        pattern
        for concept in semantic_concepts(request)
        for pattern in PATTERNS_BY_CONCEPT.get(concept, ())
    }
    return sorted(lexical | conceptual)


def build_index(documents: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Counter[str]]], dict[str, float]]:
    token_index: dict[str, dict[str, Counter[str]]] = {}
    document_frequency: Counter[str] = Counter()
    for source in documents:
        fields = {name: Counter(tokenize(text)) for name, text in searchable_fields(source).items()}
        token_index[source["source_id"]] = fields
        document_frequency.update(set().union(*(set(values) for values in fields.values())))
    total = len(documents)
    idf = {token: math.log((total + 1) / (count + 1)) + 1 for token, count in document_frequency.items()}
    return token_index, idf


def query_terms(request: str, patterns: list[str]) -> list[str]:
    terms = tokenize(request)
    for pattern in patterns:
        terms.extend(tokenize(pattern))
        for hint in PATTERN_HINTS[pattern]:
            terms.extend(tokenize(hint))
    return sorted(set(terms))


def score_source(
    source: dict[str, Any], terms: list[str], patterns: list[str],
    token_index: dict[str, dict[str, Counter[str]]], idf: dict[str, float],
) -> tuple[float, list[str]]:
    field_weights = {"metadata": 1.0, "evidence": 1.5, "lesson": 2.0, "move": 2.5}
    fields = token_index[source["source_id"]]
    matched: list[str] = []
    score = 0.0
    for term in terms:
        term_score = sum(
            field_weights[name] * math.log1p(counter.get(term, 0))
            for name, counter in fields.items()
        )
        if term_score:
            matched.append(term)
            score += idf.get(term, 1.0) * term_score
    supported = set(source.get("related_patterns") or []) & set(patterns)
    score += 8.0 * len(supported)
    return score, sorted(matched, key=lambda term: (-idf.get(term, 1.0), term))


def selected_source_record(
    source: dict[str, Any], score: float, matched: list[str], patterns: list[str],
    additions: list[str] | None = None,
) -> dict[str, Any]:
    matched_patterns = sorted(set(source.get("related_patterns") or []) & set(patterns))
    reasons = []
    if matched_patterns:
        reasons.append("요청 의미와 일치한 패턴: " + ", ".join(matched_patterns))
    if matched:
        reasons.append("요청·lesson·move·evidence 공통어: " + ", ".join(matched[:6]))
    if additions:
        reasons.append("추가 판단: " + "; ".join(additions))
    return {
        "source_id": source["source_id"],
        "name": source.get("name"),
        "score": round(score, 4),
        "selection_reason": "; ".join(reasons),
        "upgrade_status": source.get("upgrade_status"),
        "automation_status": source.get("automation_status"),
        "duplicate_status": source.get("duplicate_status"),
        "evidence_relation": source.get("evidence_relation"),
        "source_checked": source.get("source_checked"),
        "related_patterns": source.get("related_patterns") or [],
        "evidence_note": source.get("evidence_note"),
        "pattern_lesson": (source.get("lesson") or {}).get("pattern_lesson"),
        "reusable_move": (source.get("lesson") or {}).get("reusable_move"),
        "material_additions": additions or [],
    }


def source_gate_decision(
    analysis: dict[str, Any], source: dict[str, Any], score: float,
    matched: list[str], hinted: list[str],
) -> tuple[bool, list[str], str]:
    """Require a source to add a material decision variable or behavior."""
    if score <= 0:
        return False, [], "검색 관련성 점수가 0이므로 제외"
    patterns = set(source.get("related_patterns") or [])
    shared_patterns = patterns & set(hinted)
    text = " ".join(searchable_fields(source).values()).lower()
    only_generic_role = bool(patterns) and patterns <= {"Role + Task Frame", "Role + task frame"}
    prompt_quality_only = (
        "prompt quality" in text or "before running a reusable prompt" in text
    )
    has_output_contract = contains_any(
        text, ("output contract", "schema", "jsonl", "parsing rules", "expected answers", "exact output")
    )
    has_executable_eval = contains_any(
        text, (
            "empirical evaluation", "evaluation checks", "scoring template", "metrics", "regression", "human-labeled",
            "two-pass", "re-evaluate", "final validation", "consistency checks",
        ),
    )
    has_contrarian_review = contains_any(
        text, ("contrarian", "assumptions", "critique", "failure examples", "반대", "가정 검토")
    )
    additions: list[str] = []
    concepts = set(analysis["semantic_concepts"])
    if "evaluation_design" in concepts and has_output_contract and shared_patterns:
        additions.append("필수 산출물을 검사 가능한 출력 계약으로 고정")
    if "evaluation_design" in concepts and has_executable_eval and shared_patterns:
        additions.append("평가 표본·채점·재검증 절차를 실행 가능한 형태로 구체화")
    if analysis["epistemic_capture"] and has_contrarian_review and shared_patterns:
        additions.append("사용자가 제안한 해결책의 가정과 반대 가설을 별도로 검토")
    if (
        analysis["epistemic_capture"]
        and has_contrarian_review
        and has_executable_eval
        and shared_patterns
    ):
        additions.append("1차 판단을 비판한 뒤 수정·최종 검증하는 결정 절차 추가")
    if only_generic_role:
        return False, [], "일반 역할 부여만 제공하고 새로운 판단 변수나 검증 방법을 추가하지 않음"
    if prompt_quality_only and "evaluation_design" not in concepts and not has_contrarian_review:
        return False, [], "프롬프트 문장 품질 평가에 한정되어 현재 작업 판단을 바꾸지 못함"
    if not shared_patterns and len(matched) < 2:
        return False, [], "요청 의미와 source lesson·move·evidence 사이의 직접 연결이 부족함"
    if not additions:
        return False, [], "새 제약·판단 변수·반례·대안·검증법·필수 산출물을 추가하지 못함"
    return True, additions, ""


def select_sources(
    request: str, mode: str, documents: list[dict[str, Any]], top_k: int,
    token_index: dict[str, dict[str, Counter[str]]], idf: dict[str, float],
) -> dict[str, Any]:
    if mode not in MODES:
        raise CompareError(f"Unknown mode: {mode}")
    registry = load_active_source_policies()
    production_ids = {item["source_id"] for item in registry["sources"]}
    candidates = [
        source for source in documents
        if source.get("duplicate_status") != "alias" and (
            mode == "full" or (source["active"] and source["source_id"] in production_ids)
        )
    ]
    patterns = hinted_patterns(request)
    terms = query_terms(request, patterns)
    ranked = []
    for source in candidates:
        score, matched = score_source(source, terms, patterns, token_index, idf)
        ranked.append((score, source["source_id"], matched, source))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    positive = [item for item in ranked if item[0] > 0]
    selected = [
        selected_source_record(source, score, matched, patterns)
        for score, _, matched, source in positive[:top_k]
    ]
    excluded = [
        {
            "source_id": source["source_id"],
            "name": source.get("name"),
            "reason": "검색 관련성 점수가 0이므로 제외",
        }
        for score, _, _, source in ranked if score <= 0
    ]
    return {
        "candidate_count": len(candidates), "selected": selected,
        "excluded": excluded, "hinted_patterns": patterns,
    }


def select_relevant_active_sources(
    public: dict[str, Any], analysis: dict[str, Any], documents: list[dict[str, Any]], top_k: int,
    token_index: dict[str, dict[str, Counter[str]]], idf: dict[str, float],
) -> dict[str, Any]:
    request = public_request_text(public)
    patterns = hinted_patterns(request)
    terms = query_terms(request, patterns)
    registry = load_active_source_policies()
    policies = {item["source_id"]: item for item in registry["sources"]}
    policy_matches = active_policy_matches(public, registry)
    candidates = [
        source for source in documents
        if source.get("duplicate_status") != "alias"
        and source["active"]
        and source["source_id"] in policies
    ]
    accepted = []
    excluded = []
    for source in candidates:
        source_id = source["source_id"]
        policy_match = policy_matches[source_id]
        if not policy_match["passed"]:
            excluded.append(
                {
                    "source_id": source_id,
                    "name": source.get("name"),
                    "reason": policy_match["reason"],
                }
            )
            continue
        lexical_score, matched = score_source(source, terms, patterns, token_index, idf)
        policy = policies[source_id]
        score = 100.0 + 10.0 * len(policy_match["matched_signals"]) + lexical_score
        additions = [policy["unique_behavior"], *policy["required_prompt_changes"]]
        accepted.append((score, source_id, matched, source, additions))
    accepted.sort(key=lambda item: (-item[0], item[1]))
    limit = min(top_k, registry["max_auto_sources_per_request"])
    selected = [
        selected_source_record(source, score, matched, patterns, additions)
        for score, _, matched, source, additions in accepted[:limit]
    ]
    for _, _, _, source, _ in accepted[limit:]:
        excluded.append(
            {
                "source_id": source["source_id"], "name": source.get("name"),
                "reason": f"직접 관련성은 통과했지만 top-{top_k} 제한으로 제외",
            }
        )
    return {
        "candidate_count": len(candidates), "selected": selected,
        "excluded": sorted(excluded, key=lambda item: item["source_id"]),
        "hinted_patterns": patterns,
        "policy_matches": policy_matches,
    }


def evidence_context(selected: list[dict[str, Any]], max_chars: int) -> str:
    if not selected:
        raise CompareError("No evidence was selected.")
    per_source = max(300, max_chars // len(selected))
    blocks = []
    for item in selected:
        block = "\n".join(
            [
                f"Source ID: {item['source_id']}",
                f"Name: {item['name']}",
                f"Status: upgrade={item['upgrade_status']}; automation={item['automation_status']}; "
                f"duplicate={item['duplicate_status']}; evidence={item['evidence_relation']}; "
                f"source_checked={item['source_checked']}",
                "Patterns: " + ", ".join(item["related_patterns"]),
                f"Evidence note: {item['evidence_note'] or 'not available'}",
                f"Pattern lesson: {item['pattern_lesson'] or 'not available'}",
                f"Reusable move: {item['reusable_move'] or 'not available'}",
            ]
        )
        blocks.append(block[:per_source])
    context = "\n\n---\n\n".join(blocks)
    return context[:max_chars]


def generation_prompt(request: str, context: str) -> str:
    return f"""{GENERATION_INSTRUCTIONS}

USER REQUEST
{request}

SUPPLIED CORPUS EVIDENCE
{context}
"""


def find_codex() -> str:
    configured = os.environ.get("CODEX_BIN")
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
        raise CompareError(f"CODEX_BIN does not exist: {configured}")
    # Prefer the desktop-bundled native binary on Windows. The npm .cmd shim
    # resolves through Node and can fail before Codex starts in a restricted
    # desktop workspace.
    names = ("codex.cmd", "codex.exe", "codex") if os.name == "nt" else ("codex",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise CompareError("Codex CLI was not found or is not on PATH.")


def codex_command(arguments: list[str]) -> list[str]:
    """Build a subprocess-safe command for native and Windows batch installs."""
    executable = find_codex()
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline([executable, *arguments])
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]
    return [executable, *arguments]


def validate_generation(payload: Any, selected: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CompareError("Generator output is not a JSON object.")
    required = {"selected_patterns", "used_source_ids", "used_reusable_moves", "final_prompt"}
    if set(payload) != required:
        raise CompareError("Generator output fields do not match the schema.")
    allowed_ids = {item["source_id"] for item in selected}
    allowed_patterns = {pattern for item in selected for pattern in item["related_patterns"]}
    allowed_moves = {item["reusable_move"] for item in selected if item["reusable_move"]}
    if not set(payload["used_source_ids"]).issubset(allowed_ids):
        raise CompareError("Generator used a source that was not selected.")
    if not set(payload["selected_patterns"]).issubset(allowed_patterns):
        raise CompareError("Generator returned a pattern not present in selected evidence.")
    if not set(payload["used_reusable_moves"]).issubset(allowed_moves):
        raise CompareError("Generator returned a reusable move not present in selected evidence.")
    if not str(payload["final_prompt"]).strip():
        raise CompareError("Generator returned an empty final prompt.")
    return payload


def invoke_generator(prompt: str, selected: list[dict[str, Any]], work_dir: Path, label: str, model: str) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = work_dir / f"{label}-generator-prompt.md"
    output_path = work_dir / f"{label}-generator-output.json"
    log_path = work_dir / f"{label}-codex.log"
    prompt_path.write_text(prompt, encoding="utf-8")
    command = codex_command([
        "exec", "--ephemeral", "--ignore-user-config", "--model", model,
        "--sandbox", "read-only", "--cd", str(ROOT), "--output-schema", str(SCHEMA_PATH),
        "--output-last-message", str(output_path), "--color", "never", "-",
    ])
    try:
        completed = subprocess.run(
            command, input=prompt, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
    except OSError as exc:
        raise CompareError(f"Could not start Codex generator for {label}: {exc}") from exc
    log_path.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0:
        raise CompareError(f"Codex generator failed for {label}; see {log_path}")
    payload = read_json(output_path)
    return validate_generation(payload, selected)


def load_holdout_requests(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    requests = payload.get("requests") if isinstance(payload, dict) else None
    if not isinstance(requests, list) or not requests:
        raise CompareError("Holdout file must contain a non-empty requests array.")
    expected = {"id", "source", "type", "public"}
    seen: set[str] = set()
    for item in requests:
        if not isinstance(item, dict) or set(item) != expected:
            raise CompareError("Each holdout request needs id, source, type, and public.")
        if item["id"] in seen:
            raise CompareError(f"Duplicate holdout ID: {item['id']}")
        seen.add(item["id"])
        public = item["public"]
        if not isinstance(public, dict) or set(public) != {
            "user_request", "initial_information", "tools_allowed",
        }:
            raise CompareError(f"Invalid public input for {item['id']}")
        if not isinstance(public["user_request"], str) or not public["user_request"].strip():
            raise CompareError(f"Missing user request for {item['id']}")
        if not isinstance(public["initial_information"], list):
            raise CompareError(f"Invalid initial information for {item['id']}")
        if not isinstance(public["tools_allowed"], bool):
            raise CompareError(f"Invalid tools_allowed for {item['id']}")
    return requests


def normalized_exact(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def pattern_summary_catalog(index_text: str) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for line in index_text.splitlines():
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-", ":", " "}:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] == "Pattern":
            continue
        move = cells[2]
        if move.startswith("`") and move.endswith("`"):
            move = move[1:-1]
        catalog[cells[0]] = move
    if not catalog:
        raise CompareError("Pattern index table could not be parsed.")
    return catalog


def routed_generation_prompt(
    public: dict[str, Any], condition: str, selected: list[dict[str, Any]],
    workflow_text: str, index_text: str, pattern_catalog: dict[str, str],
    context_chars: int,
) -> str:
    if condition not in {"pattern-only", "active"}:
        raise CompareError(f"Unsupported routed generation condition: {condition}")
    pattern_moves = [
        {"pattern": pattern, "reusable_move": move}
        for pattern, move in pattern_catalog.items()
    ]
    if condition == "active":
        source_block = evidence_context(selected, context_chars)
        source_rule = (
            "List a source ID only when the final prompt directly incorporates that source's "
            "exact reusable move as a concrete instruction. It is valid to use no source."
        )
    else:
        source_block = "No individual corpus source is available."
        source_rule = "used_source_ids must be empty."
    return f"""Create one ready-to-use prompt for another model. Do not execute the task.

Preserve the user's actual objective, fixed constraints, deliverables, and declared tool availability.
Use the smallest useful pattern behavior. Do not add structure that does not change judgment or the required artifact.
Do not mention the repository's pattern system, corpus, source IDs, or reusable-move labels inside final_prompt.
Return JSON matching the supplied schema.
selected_patterns must use exact names from ALLOWED PATTERN MOVES.
used_reusable_moves must copy exact text from ALLOWED PATTERN MOVES or an actually used source reusable move.
{source_rule}

PUBLIC INPUT
{json.dumps(public, ensure_ascii=False, indent=2)}

ALLOWED PATTERN MOVES
{json.dumps(pattern_moves, ensure_ascii=False, indent=2)}

PROMPT DESIGN WORKFLOW
{workflow_text}

PATTERN LESSONS INDEX
{index_text}

INDIVIDUAL CORPUS EVIDENCE
{source_block}
"""


def validate_routed_generation(
    payload: Any, condition: str, selected: list[dict[str, Any]],
    pattern_catalog: dict[str, str], public: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CompareError("Generator output is not a JSON object.")
    required = {"selected_patterns", "used_source_ids", "used_reusable_moves", "final_prompt"}
    if set(payload) != required:
        raise CompareError("Generator output fields do not match the schema.")
    pattern_lookup = {normalized_exact(name): name for name in pattern_catalog}
    canonical_patterns = []
    for value in payload["selected_patterns"]:
        canonical = pattern_lookup.get(normalized_exact(value))
        if not canonical:
            raise CompareError(f"Generator returned an unknown pattern: {value}")
        canonical_patterns.append(canonical)
    allowed_ids = {item["source_id"] for item in selected}
    used_ids = set(payload["used_source_ids"])
    if condition == "pattern-only" and used_ids:
        raise CompareError("Pattern-only generator reported a corpus source.")
    if not used_ids.issubset(allowed_ids):
        raise CompareError("Generator used a source that was not selected.")
    pattern_moves = set(pattern_catalog.values())
    source_moves = {
        item["source_id"]: item.get("reusable_move")
        for item in selected if item.get("reusable_move")
    }
    allowed_move_lookup = {
        normalized_exact(move): move for move in pattern_moves | set(source_moves.values())
    }
    canonical_moves = []
    for value in payload["used_reusable_moves"]:
        canonical = allowed_move_lookup.get(normalized_exact(value))
        if not canonical:
            raise CompareError("Generator reported an unsupported reusable move.")
        canonical_moves.append(canonical)
    for source_id in used_ids:
        move = source_moves.get(source_id)
        if not move or move not in canonical_moves:
            raise CompareError(f"Generator claimed {source_id} without its exact reusable move.")
    final_prompt = str(payload["final_prompt"]).strip()
    if not final_prompt:
        raise CompareError("Generator returned an empty final prompt.")
    source_id_in_text = r"(?<![A-Za-z0-9])PR\d{3}(?!\d)"
    prompt_source_ids = set(re.findall(source_id_in_text, final_prompt))
    public_source_ids = set(
        re.findall(source_id_in_text, public_request_text(public or {}))
    )
    leaked_source_ids = prompt_source_ids - public_source_ids
    if leaked_source_ids:
        raise CompareError(
            "Generated prompt leaked a source ID not present in public input: "
            + ", ".join(sorted(leaked_source_ids))
        )
    return {
        **payload,
        "selected_patterns": canonical_patterns,
        "used_reusable_moves": canonical_moves,
        "final_prompt": final_prompt,
    }


def invoke_structured_codex(
    prompt: str, schema_path: Path, work_dir: Path, label: str, model: str,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = work_dir / f"{label}-prompt.md"
    output_path = work_dir / f"{label}-output.json"
    log_path = work_dir / f"{label}-codex.log"
    prompt_path.write_text(prompt, encoding="utf-8")
    command = codex_command([
        "exec", "--ephemeral", "--ignore-user-config", "--model", model,
        "--sandbox", "read-only", "--cd", str(ROOT), "--output-schema", str(schema_path),
        "--output-last-message", str(output_path), "--color", "never", "-",
    ])
    try:
        completed = subprocess.run(
            command, input=prompt, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
    except OSError as exc:
        raise CompareError(f"Could not start Codex for {label}: {exc}") from exc
    log_path.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0 or not output_path.is_file():
        raise CompareError(f"Codex failed for {label}; see {log_path}")
    return read_json(output_path)


def contribution_evaluation_prompt(
    public: dict[str, Any], pattern_only: dict[str, Any], active: dict[str, Any],
    selected: list[dict[str, Any]],
) -> str:
    evidence = [
        {
            "source_id": item["source_id"],
            "name": item.get("name"),
            "pattern_lesson": item.get("pattern_lesson"),
            "reusable_move": item.get("reusable_move"),
            "material_additions_claimed_before_generation": item.get("material_additions", []),
        }
        for item in selected
    ]
    return f"""Compare the two generated prompts and judge only source-specific incremental contribution.

Keep active only when an actually used source adds at least one concrete behavior absent from pattern-only:
- a new core constraint
- a decision-changing variable
- a concrete counterexample to the user's premise
- a new realistic alternative
- an executable validation method
- a stop, expand, or switch rule
- a material improvement to a required deliverable

Do not credit roles, generic self-review, abstract requests to consider another view, longer output formatting,
paraphrases of pattern-only behavior, source names, or source wording that does not change judgment or the artifact.
Repository inspection, minimal edits, validation, and diff summaries are already general Coding-Agent Workflow behavior.
Criteria, anchors, pass/fail decisions, and one revision are already general Evaluation Rubric behavior.
A source instruction that cannot be performed with the declared tools is not a material contribution.

For every selected source, set used_in_active_prompt from ACTIVE METADATA. If it was not reported as used,
return verdict=unused and no contributions. Quote the exact active instruction that allegedly adds value.
When pattern-only already contains equivalent behavior, mark already_in_pattern_only=true and explain the overlap.

PUBLIC INPUT
{json.dumps(public, ensure_ascii=False, indent=2)}

PATTERN-ONLY METADATA
{json.dumps({k: pattern_only[k] for k in ('selected_patterns', 'used_reusable_moves')}, ensure_ascii=False, indent=2)}

PATTERN-ONLY PROMPT
{pattern_only['final_prompt']}

ACTIVE METADATA
{json.dumps({k: active[k] for k in ('selected_patterns', 'used_source_ids', 'used_reusable_moves')}, ensure_ascii=False, indent=2)}

ACTIVE PROMPT
{active['final_prompt']}

SELECTED SOURCE EVIDENCE
{json.dumps(evidence, ensure_ascii=False, indent=2)}
"""


def unused_contribution_evaluation(selected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_assessments": [
            {
                "source_id": item["source_id"],
                "used_in_active_prompt": False,
                "contributions": [],
                "verdict": "unused",
                "reason": "The generator selected the source as a candidate but did not use it in the active prompt.",
            }
            for item in selected
        ],
        "keep_active": False,
        "fallback_reason": "No selected source was used in the generated active prompt.",
    }


def validate_contribution_evaluation(
    payload: Any, selected: list[dict[str, Any]], active: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "source_assessments", "keep_active", "fallback_reason",
    }:
        raise CompareError("Contribution evaluation fields are invalid.")
    selected_ids = [item["source_id"] for item in selected]
    assessments = payload["source_assessments"]
    if not isinstance(assessments, list) or {
        item.get("source_id") for item in assessments if isinstance(item, dict)
    } != set(selected_ids) or len(assessments) != len(selected_ids):
        raise CompareError("Contribution evaluation must assess every selected source exactly once.")
    used_ids = set(active["used_source_ids"])
    normalized = []
    unique_source_ids = []
    for source_id in selected_ids:
        item = next(value for value in assessments if value["source_id"] == source_id)
        actually_used = source_id in used_ids
        if bool(item["used_in_active_prompt"]) != actually_used:
            raise CompareError(f"Contribution evaluator misreported source use for {source_id}.")
        contributions = item["contributions"] if actually_used else []
        unique = any(
            contribution.get("type") in CONTRIBUTION_TYPES
            and contribution.get("already_in_pattern_only") is False
            and contribution.get("changes_judgment_or_deliverable") is True
            and contribution.get("supported_by_source") is True
            and bool(str(contribution.get("active_prompt_excerpt") or "").strip())
            for contribution in contributions
        )
        verdict = "unused" if not actually_used else ("unique" if unique else "not_unique")
        if unique:
            unique_source_ids.append(source_id)
        normalized.append({**item, "contributions": contributions, "verdict": verdict})
    keep_active = bool(unique_source_ids) and set(unique_source_ids) == used_ids
    fallback_reason = "" if keep_active else (
        str(payload.get("fallback_reason") or "").strip()
        or "Every used source must add a unique material behavior beyond pattern-only."
    )
    return {
        "source_assessments": normalized,
        "model_keep_active": bool(payload["keep_active"]),
        "keep_active": keep_active,
        "unique_source_ids": unique_source_ids,
        "fallback_reason": fallback_reason,
    }


def normalized_prompt(value: str) -> str:
    return " ".join(value.lower().split())


def compare_pair(full: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    full_ids = full["selected_source_ids"]
    active_ids = active["selected_source_ids"]
    left = normalized_prompt(full["final_prompt"])
    right = normalized_prompt(active["final_prompt"])
    similarity = SequenceMatcher(None, left, right).ratio()
    used_evidence_same = bool(
        full["used_source_ids"] == active["used_source_ids"]
        and full["selected_patterns"] == active["selected_patterns"]
        and full["used_reusable_moves"] == active["used_reusable_moves"]
    )
    return {
        "selected_sources_same": full_ids == active_ids,
        "used_evidence_same": used_evidence_same,
        "final_prompt_exactly_same": left == right,
        "final_prompt_similarity": round(similarity, 4),
        # Separate-session wording drift is not a mode effect. Count a meaningful
        # mode difference only when retrieval and actually used evidence differ.
        "final_prompt_meaningfully_different": bool(
            full_ids != active_ids
            and not used_evidence_same
            and left != right
            and similarity < 0.92
        ),
    }


def load_requests(path: Path) -> list[dict[str, str]]:
    payload = read_json(path)
    requests = payload.get("requests") if isinstance(payload, dict) else None
    if not isinstance(requests, list) or not requests:
        raise CompareError("Request file must contain a non-empty requests array.")
    for item in requests:
        if set(item) != {"id", "source", "request"} or not all(isinstance(v, str) and v.strip() for v in item.values()):
            raise CompareError("Every request needs non-empty id, source, and request strings.")
    return requests


def route_request(
    case_id: str, public: dict[str, Any], documents: list[dict[str, Any]], top_k: int,
    token_index: dict[str, dict[str, Counter[str]]], idf: dict[str, float],
) -> tuple[dict[str, Any], dict[str, Any]]:
    analysis = baseline_first_analysis(public)
    registry = load_active_source_policies()
    production_ids = {item["source_id"] for item in registry["sources"]}
    active_documents = [
        item for item in documents
        if item["active"] and item["source_id"] in production_ids
    ]
    policy_matches = active_policy_matches(public, registry)
    has_policy_candidate = any(item["passed"] for item in policy_matches.values())
    hints = hinted_patterns(public_request_text(public))
    if analysis["repository_tool_mismatch"]:
        reason = (
            "저장소 작업 요청이지만 실행 환경에서 파일·도구를 사용할 수 없어 "
            "Coding-Agent Workflow를 주입하지 않고 baseline 유지"
        )
        excluded = [
            {"source_id": item["source_id"], "name": item.get("name"), "reason": reason}
            for item in active_documents
        ]
        record = {
            "case_id": case_id,
            "selected_mode": "baseline",
            "selection_reason": reason,
            "excluded_sources": excluded,
            "used_sources": [],
            "material_additions": [],
            "fallback": False,
        }
        return record, {
            "analysis": analysis, "hinted_patterns": hints, "selected_scores": [],
            "policy_matches": policy_matches,
        }

    if analysis["active_search_candidate"] or has_policy_candidate:
        retrieval = select_relevant_active_sources(
            public, analysis, documents, top_k, token_index, idf
        )
        if retrieval["selected"]:
            additions = [
                {"source_id": item["source_id"], "additions": item["material_additions"]}
                for item in retrieval["selected"]
            ]
            record = {
                "case_id": case_id,
                "selected_mode": "active",
                "selection_reason": (
                    "사용자가 제안한 해결책 또는 평가 설계를 독립적으로 검토해야 하며, "
                    "직접 관련성 게이트를 통과한 자료가 반대 가설·검증 절차·결정 규칙을 추가함"
                ),
                "excluded_sources": retrieval["excluded"],
                "used_sources": [
                    {"source_id": item["source_id"], "name": item["name"]}
                    for item in retrieval["selected"]
                ],
                "material_additions": additions,
                "fallback": False,
            }
            return record, {
                "analysis": analysis, "hinted_patterns": retrieval["hinted_patterns"],
                "selected_scores": [item["score"] for item in retrieval["selected"]],
                "policy_matches": retrieval["policy_matches"],
            }
        fallback_mode = analysis["fallback_mode"]
        record = {
            "case_id": case_id,
            "selected_mode": fallback_mode,
            "selection_reason": (
                "active 검색 조건은 있었지만 새 제약·판단 변수·반례·검증법을 추가하는 자료가 없어 "
                f"{fallback_mode}로 복귀"
            ),
            "excluded_sources": retrieval["excluded"],
            "used_sources": [],
            "material_additions": [],
            "fallback": True,
        }
        return record, {
            "analysis": analysis, "hinted_patterns": retrieval["hinted_patterns"],
            "selected_scores": [],
            "policy_matches": retrieval["policy_matches"],
        }

    selected_mode = analysis["fallback_mode"]
    reason = (
        "필수 항목·표·계산·비교 누락 위험은 있으나 개별 corpus 없이 패턴 출력 계약으로 충분"
        if selected_mode == "pattern-only"
        else "입력만으로 판단 가능하고 개별 corpus가 새로운 판단을 추가할 필요가 없어 baseline 유지"
    )
    excluded = [
        {"source_id": item["source_id"], "name": item.get("name"), "reason": reason}
        for item in active_documents
    ]
    record = {
        "case_id": case_id,
        "selected_mode": selected_mode,
        "selection_reason": reason,
        "excluded_sources": excluded,
        "used_sources": [],
        "material_additions": [],
        "fallback": False,
    }
    return record, {
        "analysis": analysis, "hinted_patterns": hints, "selected_scores": [],
        "policy_matches": policy_matches,
    }


def load_expert_routing_cases(case_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    cases = []
    for case_id in EXPERT_CASE_IDS:
        payload = read_json(case_dir / f"{case_id}.json")
        cases.append(
            (
                case_id,
                {
                    "user_request": payload["original_user_request"],
                    "initial_information": payload["initial_information"],
                    "tools_allowed": False,
                },
            )
        )
    return cases


def validate_routing_dry_run(
    records: list[dict[str, Any]], diagnostics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_case = {item["case_id"]: item for item in records}
    production_ids = {
        item["source_id"] for item in load_active_source_policies()["sources"]
    }
    checks = {
        "A3_avoids_coding_agent_without_tools": (
            by_case["A3"]["selected_mode"] == "baseline"
            and not by_case["A3"]["used_sources"]
        ),
        "C10_C14_exclude_unrelated_corpus": all(
            by_case[case_id]["selected_mode"] == "pattern-only"
            and not by_case[case_id]["used_sources"]
            for case_id in ("C10", "C14")
        ),
        "A7_uses_executable_eval_source_only_if_policy_matches": (
            by_case["A7"]["selected_mode"] in {"active", "pattern-only"}
            and all(
                item["source_id"] == "PR065"
                for item in by_case["A7"]["used_sources"]
            )
        ),
        "general_challenge_cases_do_not_force_corpus": all(
            by_case[case_id]["selected_mode"] == "pattern-only"
            and not by_case[case_id]["used_sources"]
            for case_id in ("C11", "C13", "C16")
        ),
        "korean_requests_have_semantic_hints": all(
            diagnostics[case_id]["hinted_patterns"] for case_id in EXPERT_CASE_IDS
        ),
        "zero_relevance_sources_not_selected": all(
            all(score > 0 for score in diagnostics[case_id]["selected_scores"])
            for case_id in EXPERT_CASE_IDS
        ),
        "only_registered_sources_can_be_selected": all(
            all(item["source_id"] in production_ids for item in record["used_sources"])
            for record in records
        ),
        "minimal_source_count": all(len(record["used_sources"]) <= 1 for record in records),
        "full_never_selected": all(
            item["selected_mode"] in ROUTED_MODES for item in records
        ),
    }
    return {"pass": all(checks.values()), "checks": checks}


def run_routing_dry_run(args: argparse.Namespace) -> int:
    if args.top_k < 1:
        raise CompareError("top-k must be positive.")
    documents = load_documents()
    token_index, idf = build_index(documents)
    records = []
    diagnostics = {}
    for case_id, public in load_expert_routing_cases(args.cases_dir):
        record, detail = route_request(
            case_id, public, documents, args.top_k, token_index, idf
        )
        records.append(record)
        diagnostics[case_id] = detail
    validation = validate_routing_dry_run(records, diagnostics)
    run_id = "routing-dry-run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir or (RUNS_DIR / run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    result = {
        "run_id": run_id,
        "stage": "routing-and-relevance-gate-only",
        "records": records,
        "excluded_source_count": sum(len(item["excluded_sources"]) for item in records),
        "validation": validation,
    }
    write_json(run_dir / "routing-results.json", result)
    print(json.dumps({**result, "output": str(run_dir)}, ensure_ascii=False, indent=2))
    if not validation["pass"]:
        raise CompareError(f"Routing dry-run failed; see {run_dir / 'routing-results.json'}")
    return 0


def run_dry_run(args: argparse.Namespace) -> int:
    if args.top_k < 1 or args.context_chars < 1000:
        raise CompareError("top-k must be positive and context-chars must be at least 1000.")
    documents = load_documents()
    token_index, idf = build_index(documents)
    requests = load_requests(args.requests)
    run_id = "prompt-mode-dry-run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir or (RUNS_DIR / run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    records = []
    for request_item in requests:
        modes: dict[str, Any] = {}
        case_dir = run_dir / request_item["id"]
        for mode in MODES:
            retrieval = select_sources(
                request_item["request"], mode, documents, args.top_k, token_index, idf
            )
            context = evidence_context(retrieval["selected"], args.context_chars)
            generated = invoke_generator(
                generation_prompt(request_item["request"], context), retrieval["selected"],
                case_dir, mode, args.model,
            )
            modes[mode] = {
                "user_request": request_item["request"],
                "mode": mode,
                "candidate_count": retrieval["candidate_count"],
                "top_k": args.top_k,
                "context_char_limit": args.context_chars,
                "context_chars_used": len(context),
                "selected_source_ids": [item["source_id"] for item in retrieval["selected"]],
                "selected_sources": retrieval["selected"],
                "selected_patterns": generated["selected_patterns"],
                "used_source_ids": generated["used_source_ids"],
                "used_reusable_moves": generated["used_reusable_moves"],
                "final_prompt": generated["final_prompt"],
            }
        records.append(
            {
                "id": request_item["id"], "source": request_item["source"],
                "user_request": request_item["request"], "modes": modes,
                "comparison": compare_pair(modes["full"], modes["active"]),
            }
        )
    summary = {
        "run_id": run_id,
        "stage": "retrieval-and-prompt-generation-only",
        "model": args.model,
        "generation_instructions": GENERATION_INSTRUCTIONS,
        "request_count": len(records),
        "top_k": args.top_k,
        "context_char_limit": args.context_chars,
        "different_source_selection_count": sum(not item["comparison"]["selected_sources_same"] for item in records),
        "meaningfully_different_prompt_count": sum(item["comparison"]["final_prompt_meaningfully_different"] for item in records),
        "records": records,
    }
    write_json(run_dir / "results.json", summary)
    write_json(
        run_dir / "summary.json",
        {key: value for key, value in summary.items() if key != "records"},
    )
    print(json.dumps({**{key: value for key, value in summary.items() if key != "records"}, "output": str(run_dir)}, ensure_ascii=False, indent=2))
    return 0


def run_contribution_dry_run(args: argparse.Namespace) -> int:
    if args.top_k < 1 or args.context_chars < 1000:
        raise CompareError("top-k must be positive and context-chars must be at least 1000.")
    documents = load_documents()
    token_index, idf = build_index(documents)
    requests = load_holdout_requests(args.requests)
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    index_text = PATTERN_INDEX_PATH.read_text(encoding="utf-8")
    catalog = pattern_summary_catalog(index_text)
    run_id = "contribution-dry-run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir or (RUNS_DIR / run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    records = []
    for request_item in requests:
        case_id = request_item["id"]
        public = request_item["public"]
        case_dir = run_dir / case_id
        route, diagnostics = route_request(
            case_id, public, documents, args.top_k, token_index, idf
        )
        initial_mode = route["selected_mode"]
        record: dict[str, Any] = {
            "case_id": case_id,
            "source": request_item["source"],
            "type": request_item["type"],
            "public_input": public,
            "initial_route": route,
            "routing_diagnostics": diagnostics,
            "pattern_only": None,
            "active_attempt": None,
            "final_mode": initial_mode,
            "final_prompt": None,
            "fallback": False,
            "fallback_reason": "",
        }
        if initial_mode == "baseline":
            records.append(record)
            print(f"{case_id}: baseline retained", flush=True)
            continue

        pattern_raw = invoke_structured_codex(
            routed_generation_prompt(
                public, "pattern-only", [], workflow_text, index_text,
                catalog, args.context_chars,
            ),
            SCHEMA_PATH, case_dir, "pattern-only-generator", args.model,
        )
        pattern_generated = validate_routed_generation(
            pattern_raw, "pattern-only", [], catalog, public
        )
        write_json(case_dir / "pattern-only-validated.json", pattern_generated)
        record["pattern_only"] = pattern_generated
        record["final_prompt"] = pattern_generated["final_prompt"]
        if initial_mode == "pattern-only":
            records.append(record)
            print(f"{case_id}: pattern-only retained", flush=True)
            continue

        analysis = baseline_first_analysis(public)
        retrieval = select_relevant_active_sources(
            public, analysis, documents, args.top_k, token_index, idf
        )
        if not retrieval["selected"]:
            record["final_mode"] = "pattern-only"
            record["fallback"] = True
            record["fallback_reason"] = "No source passed the existing direct-relevance gate."
            record["active_attempt"] = {
                "selected_sources": [],
                "excluded_sources": retrieval["excluded"],
                "contribution_evaluation": None,
            }
            records.append(record)
            print(f"{case_id}: pattern-only fallback (no relevant source)", flush=True)
            continue

        active_raw = invoke_structured_codex(
            routed_generation_prompt(
                public, "active", retrieval["selected"], workflow_text,
                index_text, catalog, args.context_chars,
            ),
            SCHEMA_PATH, case_dir, "active-generator", args.model,
        )
        active_generated = validate_routed_generation(
            active_raw, "active", retrieval["selected"], catalog, public
        )
        write_json(case_dir / "active-validated.json", active_generated)
        if not active_generated["used_source_ids"]:
            raw_evaluation = unused_contribution_evaluation(retrieval["selected"])
            write_json(case_dir / "contribution-evaluator-output.json", raw_evaluation)
        else:
            raw_evaluation = invoke_structured_codex(
                contribution_evaluation_prompt(
                    public, pattern_generated, active_generated, retrieval["selected"]
                ),
                CONTRIBUTION_SCHEMA_PATH, case_dir, "contribution-evaluator", args.model,
            )
        contribution = validate_contribution_evaluation(
            raw_evaluation, retrieval["selected"], active_generated
        )
        write_json(case_dir / "contribution-decision.json", contribution)
        selected_ids = [item["source_id"] for item in retrieval["selected"]]
        unique_ids = contribution["unique_source_ids"]
        record["active_attempt"] = {
            "selected_sources": retrieval["selected"],
            "excluded_sources": retrieval["excluded"],
            "active_generation": active_generated,
            "claimed_contributions_before_generation": [
                {
                    "source_id": item["source_id"],
                    "claims": item.get("material_additions", []),
                }
                for item in retrieval["selected"]
            ],
            "contribution_evaluation": contribution,
            "discarded_source_ids": [
                source_id for source_id in selected_ids if source_id not in unique_ids
            ],
        }
        if contribution["keep_active"]:
            record["final_mode"] = "active"
            record["final_prompt"] = active_generated["final_prompt"]
            print(f"{case_id}: active retained ({', '.join(unique_ids)})", flush=True)
        else:
            record["final_mode"] = "pattern-only"
            record["final_prompt"] = pattern_generated["final_prompt"]
            record["fallback"] = True
            record["fallback_reason"] = contribution["fallback_reason"]
            print(f"{case_id}: pattern-only fallback", flush=True)
        records.append(record)

    by_case = {item["case_id"]: item for item in records}
    active_attempts = [
        item for item in records if item["initial_route"]["selected_mode"] == "active"
    ]
    validation_checks = {
        "unused_sources_are_not_final_contributors": all(
            not set(
                (item.get("active_attempt") or {}).get("discarded_source_ids", [])
            ) & set(
                ((item.get("active_attempt") or {}).get("contribution_evaluation") or {}).get(
                    "unique_source_ids", []
                )
            )
            for item in records
        ),
        "active_attempts_have_post_generation_decisions": all(
            bool((item.get("active_attempt") or {}).get("contribution_evaluation"))
            for item in active_attempts
        ),
        "baseline_cases_remain_baseline": all(
            item["final_mode"] == "baseline"
            for item in records
            if item["initial_route"]["selected_mode"] == "baseline"
        ),
        "only_registered_sources_reach_active": all(
            all(
                source_id in {
                    policy["source_id"]
                    for policy in load_active_source_policies()["sources"]
                }
                for source_id in (
                    ((item.get("active_attempt") or {}).get("contribution_evaluation") or {}).get(
                        "unique_source_ids", []
                    )
                )
            )
            for item in records
        ),
        "one_source_maximum": all(
            len((item.get("active_attempt") or {}).get("selected_sources", [])) <= 1
            for item in records
        ),
        "full_never_selected": all(item["final_mode"] in ROUTED_MODES for item in records),
    }
    if {"H04", "H05", "H10", "H11"}.issubset(by_case):
        validation_checks.update({
            "H05_falls_back_to_pattern_only": by_case["H05"]["final_mode"] == "pattern-only",
            "H10_has_post_generation_decision": bool(
                (by_case["H10"].get("active_attempt") or {}).get("contribution_evaluation")
            ),
            "H04_H11_not_final_active_without_tools": all(
                by_case[case_id]["final_mode"] != "active" for case_id in ("H04", "H11")
            ),
        })

    registry = load_active_source_policies()
    source_stats = {
        policy["source_id"]: {
            "source_id": policy["source_id"],
            "task_types": policy["task_types"],
            "candidate_count": 0,
            "final_used_count": 0,
            "fallback_count": 0,
            "unique_behavior": policy["unique_behavior"],
            "added_behaviors": [],
        }
        for policy in registry["sources"]
    }
    for item in records:
        attempt = item.get("active_attempt") or {}
        selected_ids = [
            source["source_id"] for source in attempt.get("selected_sources", [])
        ]
        contribution = attempt.get("contribution_evaluation") or {}
        final_ids = set(contribution.get("unique_source_ids", [])) if item["final_mode"] == "active" else set()
        assessments = {
            assessment["source_id"]: assessment
            for assessment in contribution.get("source_assessments", [])
        }
        for source_id in selected_ids:
            stats = source_stats[source_id]
            stats["candidate_count"] += 1
            if source_id in final_ids:
                stats["final_used_count"] += 1
                for detail in assessments.get(source_id, {}).get("contributions", []):
                    if (
                        detail.get("already_in_pattern_only") is False
                        and detail.get("changes_judgment_or_deliverable") is True
                        and detail.get("supported_by_source") is True
                    ):
                        description = str(detail.get("description") or "").strip()
                        if description and description not in stats["added_behaviors"]:
                            stats["added_behaviors"].append(description)
            else:
                stats["fallback_count"] += 1
    summary = {
        "run_id": run_id,
        "stage": "prompt-generation-and-post-generation-contribution-gate-only",
        "model": args.model,
        "request_count": len(records),
        "active_attempt_count": len(active_attempts),
        "active_retained_count": sum(item["final_mode"] == "active" for item in active_attempts),
        "pattern_only_fallback_count": sum(
            item["fallback"] and item["final_mode"] == "pattern-only"
            for item in active_attempts
        ),
        "mode_counts": {
            mode: sum(item["final_mode"] == mode for item in records)
            for mode in ROUTED_MODES
        },
        "source_stats": list(source_stats.values()),
        "validation": {
            "pass": all(validation_checks.values()),
            "checks": validation_checks,
        },
        "records": records,
    }
    write_json(run_dir / "results.json", summary)
    write_json(
        run_dir / "summary.json",
        {key: value for key, value in summary.items() if key != "records"},
    )
    print(json.dumps({
        **{key: value for key, value in summary.items() if key != "records"},
        "output": str(run_dir),
    }, ensure_ascii=False, indent=2))
    if not summary["validation"]["pass"]:
        raise CompareError(f"Contribution dry-run failed; see {run_dir / 'results.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    route = subparsers.add_parser(
        "routing-dry-run",
        help="Route the fixed expert-collaboration cases without model execution.",
    )
    route.add_argument("--cases-dir", type=Path, default=EXPERT_CASES_DIR)
    route.add_argument("--top-k", type=int, default=3)
    route.add_argument("--output-dir", type=Path)
    route.set_defaults(func=run_routing_dry_run)
    dry = subparsers.add_parser("dry-run", help="Generate full/active prompts without executing them.")
    dry.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS_PATH)
    dry.add_argument("--top-k", type=int, default=3)
    dry.add_argument("--context-chars", type=int, default=6000)
    dry.add_argument("--model", default=os.environ.get("PROMPT_COMPARE_MODEL", "gpt-5.5"))
    dry.add_argument("--output-dir", type=Path)
    dry.set_defaults(func=run_dry_run)
    contribution = subparsers.add_parser(
        "contribution-dry-run",
        help="Generate pattern-only first and keep active only after source contribution passes.",
    )
    contribution.add_argument("--requests", type=Path, default=HOLDOUT_REQUESTS_PATH)
    contribution.add_argument("--top-k", type=int, default=3)
    contribution.add_argument("--context-chars", type=int, default=6000)
    contribution.add_argument(
        "--model", default=os.environ.get("PROMPT_COMPARE_MODEL", "gpt-5.5")
    )
    contribution.add_argument("--output-dir", type=Path)
    contribution.set_defaults(func=run_contribution_dry_run)
    actual = subparsers.add_parser(
        "actual-usage-dry-run",
        help="Run the contribution gate against recorded real user requests, not holdouts.",
    )
    actual.add_argument("--requests", type=Path, default=ACTUAL_USAGE_REQUESTS_PATH)
    actual.add_argument("--top-k", type=int, default=3)
    actual.add_argument("--context-chars", type=int, default=6000)
    actual.add_argument(
        "--model", default=os.environ.get("PROMPT_COMPARE_MODEL", "gpt-5.5")
    )
    actual.add_argument("--output-dir", type=Path)
    actual.set_defaults(func=run_contribution_dry_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = build_parser().parse_args(argv)
        return args.func(args)
    except CompareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
