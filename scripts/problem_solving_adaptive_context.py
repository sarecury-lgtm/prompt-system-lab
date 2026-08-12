#!/usr/bin/env python3
"""Extract decision-relevant user context while preserving exact source evidence."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as OS


ROOT = SCRIPT_DIR.parent
CONTEXT_SCHEMA = ROOT / "schemas" / "problem-solving-adaptive-context-evidence.schema.json"
MAX_CONTEXT_CHARS = 100_000
CATEGORIES = {
    "goal",
    "preference",
    "avoidance",
    "prior_experience",
    "constraint",
    "other",
}


class AdaptiveContextError(ValueError):
    """Raised when context evidence is missing its source grounding."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdaptiveContextError(f"{label}이 비어 있습니다.")
    return value.strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _quote_exists(context: str, quote: str) -> bool:
    return _normalize(quote) in _normalize(context)


def _subject_terms_from_quote(quote: str) -> list[str]:
    """Extract only a conservative sentence-initial subject for hard negatives."""

    cleaned = re.sub(r"^[\s>*•\-]+", "", quote).strip()
    match = re.match(
        r"^([가-힣A-Za-z0-9][가-힣A-Za-z0-9 _+\-]{0,40}?)(?:은|는|이|가|을|를)\s",
        cleaned,
    )
    if not match:
        return []
    subject = match.group(1).strip()
    if not subject or len(subject) > 30:
        return []
    return [subject]


def _strong_context_lines(context: str) -> list[dict[str, Any]]:
    """Keep explicit user claims even when the model fails to select them."""

    negative = (
        "별로",
        "싫",
        "불호",
        "안 먹",
        "안먹",
        "제외",
        "재추천 금지",
        "사지 않",
        "원하지 않",
    )
    experience = ("먹어봤", "써봤", "사용해봤", "사봤", "해봤", "경험")
    preference = ("좋아", "선호", "중요", "원해", "무조건", "최우선")
    constraint = ("이하", "이상", "예산", "최대", "최소", "반드시", "조건")
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in context.splitlines():
        quote = raw.strip()
        if not quote or len(quote) > 600:
            continue
        normalized = _normalize(quote)
        if normalized in seen:
            continue
        category = None
        subject_terms: list[str] = []
        if any(marker in quote for marker in negative):
            category = (
                "prior_experience"
                if any(marker in quote for marker in experience)
                else "avoidance"
            )
            subject_terms = _subject_terms_from_quote(quote)
        elif any(marker in quote for marker in preference):
            category = "preference"
        elif any(marker in quote for marker in constraint):
            category = "constraint"
        if category is None:
            continue
        seen.add(normalized)
        selected.append(
            {
                "id": f"context-auto-{len(selected) + 1:03d}",
                "category": category,
                "statement": quote,
                "source_quote": quote,
                "subject_terms": subject_terms,
                "must_preserve": True,
            }
        )
        if len(selected) >= 20:
            break
    return selected


def context_evidence_prompt(request: str, context: str) -> str:
    return f"""사용자 요청을 해결할 때 실제 행동이나 후보 선택을 바꿀 관련 맥락만 추출하세요.

[현재 요청]
{request}

[관련 대화 원문]
{context}

규칙:
- [현재 요청]은 관련성을 판단하는 기준일 뿐이며 fact나 source_quote의 출처로 사용하지 않습니다.
- 각 fact의 source_quote는 반드시 [관련 대화 원문]에서 그대로 복사합니다.
- source_quote는 요약하거나 교정하지 않습니다.
- 사용자가 이미 써보거나 먹어본 뒤 싫다고 한 대상은 prior_experience로 분류하고 must_preserve를 true로 둡니다.
- 명시적 제외, 금지와 불호는 avoidance로 분류합니다.
- subject_terms에는 그 인용 안에 실제로 적힌 제품명·대상명만 넣습니다.
- 현재 요청의 결과를 바꾸지 않는 일반 신상정보나 추측은 제외합니다.
- 관련 대화 원문에 근거가 부족하면 unresolved에 적고 빈 내용을 만들어내지 않습니다.
- summary는 추출된 사실의 용도를 한 문장으로 설명합니다.
"""


def _remove_request_only_facts(
    payload: Any,
    request: str,
    context: str,
) -> Any:
    """Drop redundant facts quoted from the request instead of failing the run.

    The current request is already preserved separately. It is shown to the model only
    to decide which prior context matters, so echoing it as a context fact is harmless
    but invalid. Quotes found in neither source are still rejected by the validator.
    """

    if not isinstance(payload, dict):
        return payload
    value = payload.get("context_evidence")
    if not isinstance(value, dict):
        return payload
    facts = value.get("facts")
    if not isinstance(facts, list):
        return payload

    filtered: list[Any] = []
    for fact in facts:
        quote = fact.get("source_quote") if isinstance(fact, dict) else None
        request_only = (
            isinstance(quote, str)
            and _quote_exists(request, quote)
            and not _quote_exists(context, quote)
        )
        if not request_only:
            filtered.append(fact)
    value["facts"] = filtered
    return payload


def validate_context_evidence(payload: Any, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"context_evidence"}:
        raise AdaptiveContextError("context_evidence 최상위 형식이 올바르지 않습니다.")
    value = payload["context_evidence"]
    if not isinstance(value, dict) or set(value) != {"summary", "facts", "unresolved"}:
        raise AdaptiveContextError("context_evidence 필드가 올바르지 않습니다.")

    summary = _text(value["summary"], "context_evidence.summary")
    unresolved = value["unresolved"]
    if not isinstance(unresolved, list) or not all(
        isinstance(item, str) and item.strip() for item in unresolved
    ):
        raise AdaptiveContextError("context_evidence.unresolved가 문자열 배열이 아닙니다.")
    if len(unresolved) > 10:
        raise AdaptiveContextError("context_evidence.unresolved는 최대 10개입니다.")

    facts = value["facts"]
    if not isinstance(facts, list) or len(facts) > 40:
        raise AdaptiveContextError("context_evidence.facts가 올바른 배열이 아닙니다.")
    required = {
        "id",
        "category",
        "statement",
        "source_quote",
        "subject_terms",
        "must_preserve",
    }
    normalized_facts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_quotes: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != required:
            raise AdaptiveContextError("context fact 형식이 올바르지 않습니다.")
        identifier = _text(fact["id"], "context fact id")
        if identifier in seen_ids:
            raise AdaptiveContextError("context fact ID가 중복되었습니다.")
        seen_ids.add(identifier)
        category = fact["category"]
        if category not in CATEGORIES:
            raise AdaptiveContextError("지원하지 않는 context fact category입니다.")
        statement = _text(fact["statement"], "context fact statement")
        quote = _text(fact["source_quote"], "context fact source_quote")
        if not _quote_exists(context, quote):
            raise AdaptiveContextError(
                f"원문에 없는 context 인용을 사용할 수 없습니다: {quote[:80]}"
            )
        terms = fact["subject_terms"]
        if not isinstance(terms, list) or len(terms) > 8 or not all(
            isinstance(term, str) and term.strip() for term in terms
        ):
            raise AdaptiveContextError("context fact subject_terms가 올바르지 않습니다.")
        for term in terms:
            if _normalize(term) not in _normalize(quote):
                raise AdaptiveContextError(
                    f"인용 안에 없는 대상명을 사용할 수 없습니다: {term}"
                )
        if not isinstance(fact["must_preserve"], bool):
            raise AdaptiveContextError("context fact must_preserve는 boolean이어야 합니다.")
        normalized_quote = _normalize(quote)
        seen_quotes.add(normalized_quote)
        normalized_facts.append(
            {
                "id": identifier,
                "category": category,
                "statement": statement,
                "source_quote": quote,
                "subject_terms": [term.strip() for term in terms],
                "must_preserve": fact["must_preserve"],
            }
        )

    for fact in _strong_context_lines(context):
        if _normalize(fact["source_quote"]) in seen_quotes:
            continue
        fact["id"] = f"context-auto-{len(normalized_facts) + 1:03d}"
        normalized_facts.append(fact)
        seen_quotes.add(_normalize(fact["source_quote"]))
        if len(normalized_facts) >= 40:
            break

    return {
        "summary": summary,
        "facts": normalized_facts,
        "unresolved": [item.strip() for item in unresolved],
    }


def extract_context_evidence(
    request: str,
    context: str,
    *,
    engine: OS.ProblemSolvingEngine,
    run_dir: Path,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned_request = request.strip()
    cleaned_context = context.strip()
    if not cleaned_request:
        raise AdaptiveContextError("현재 요청이 비어 있습니다.")
    if len(cleaned_context) > MAX_CONTEXT_CHARS:
        raise AdaptiveContextError("관련 대화 맥락은 100,000자 이하여야 합니다.")
    if not cleaned_context:
        return {
            "summary": "관련 대화 맥락이 제공되지 않아 현재 요청만 사용합니다.",
            "facts": [],
            "unresolved": ["관련 대화 맥락이 제공되지 않음"],
        }

    model_policy = dict(policy or OS.load_model_policy())
    profile = model_policy["router_fallback"]
    invocation = OS.InvocationSpec(
        name="adaptive-context-evidence",
        phase="adaptive-context",
        route=None,
        profile=profile,
        schema_path=CONTEXT_SCHEMA,
    )
    raw = engine.execute(
        context_evidence_prompt(cleaned_request, cleaned_context),
        run_dir,
        invocation,
    )
    raw = _remove_request_only_facts(raw, cleaned_request, cleaned_context)
    evidence = validate_context_evidence(raw, cleaned_context)
    (run_dir / "context-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return evidence
