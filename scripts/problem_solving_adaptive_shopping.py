#!/usr/bin/env python3
"""Run a bounded shopping workflow using grounded context and structured product data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_adaptive_context as CONTEXT
import problem_solving_os as OS


ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "adaptive-shopping-experiments"
COLLECTION_SCHEMA = ROOT / "schemas" / "problem-solving-adaptive-product-collection.schema.json"
DECISION_SCHEMA = ROOT / "schemas" / "problem-solving-adaptive-product-decision.schema.json"
MAX_REQUEST_CHARS = 10_000
MAX_CONTEXT_CHARS = CONTEXT.MAX_CONTEXT_CHARS
SHOPPING_TERMS = (
    "추천",
    "구매",
    "상품",
    "제품",
    "살 만",
    "살까",
    "온라인",
    "가격",
    "삼겹",
    "오겹",
    "고기",
)
NEGATIVE_CATEGORIES = {"avoidance", "prior_experience"}


class AdaptiveShoppingError(ValueError):
    """Raised when structured shopping evidence violates the adapter contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdaptiveShoppingError(f"{label}이 비어 있습니다.")
    return value.strip()


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _string_list(value: Any, label: str, *, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise AdaptiveShoppingError(f"{label}이 올바른 문자열 배열이 아닙니다.")
    return [item.strip() for item in value]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AdaptiveShoppingError(f"상품 URL이 올바르지 않습니다: {value}")
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _invoke(
    engine: OS.ProblemSolvingEngine,
    run_dir: Path,
    *,
    name: str,
    phase: str,
    route: str | None,
    profile: OS.ModelProfile,
    schema: Path,
    prompt: str,
) -> dict[str, Any]:
    invocation = OS.InvocationSpec(
        name=name,
        phase=phase,
        route=route,
        profile=profile,
        schema_path=schema,
    )
    return engine.execute(prompt, run_dir, invocation)


def supports_request(request: str) -> bool:
    text = request.strip()
    return bool(text) and any(term in text for term in SHOPPING_TERMS)


def _quantity_limit_grams(request: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*kg\s*이하", request, re.IGNORECASE)
    if match:
        return int(float(match.group(1)) * 1000)
    match = re.search(r"(\d+)\s*g\s*이하", request, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _requires_both_storage(request: str) -> bool:
    text = request.replace(" ", "")
    return "냉장" in text and "냉동" in text


def _excluded_terms(context_evidence: Mapping[str, Any]) -> list[str]:
    terms: list[str] = []
    for fact in context_evidence.get("facts", []):
        if not isinstance(fact, Mapping) or fact.get("category") not in NEGATIVE_CATEGORIES:
            continue
        for term in fact.get("subject_terms", []):
            cleaned = str(term).strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
    return terms


def product_collection_prompt(
    request: str,
    context_evidence: Mapping[str, Any],
    *,
    mode: str,
    prior_products: list[Mapping[str, Any]] | None = None,
    retry_instruction: str = "",
) -> str:
    prior = []
    for product in prior_products or []:
        prior.append(
            {
                "name": product.get("name"),
                "seller": product.get("seller"),
                "url": product.get("url"),
                "option": product.get("option"),
                "total_grams": product.get("total_grams"),
                "storage": product.get("storage"),
                "availability": product.get("availability"),
            }
        )
    return f"""온라인 구매 후보의 실제 상품 데이터를 수집하세요. 추천문이나 시장 설명을 쓰지 말고 지정된 JSON만 반환합니다.

[사용자 요청]
{request}

[원문 근거가 있는 사용자 맥락]
{json.dumps(context_evidence, ensure_ascii=False, indent=2)}

[수집 모드]
{mode}

[이미 수집된 상품]
{json.dumps(prior, ensure_ascii=False, indent=2)}

[이번에 보완할 점]
{retry_instruction or "서로 다른 판매처와 옵션을 넓게 수집"}

수집 규칙:
- 검색 결과 목록, 상품 가이드, 기사와 카테고리 페이지가 아니라 지금 주문할 수 있는 정확한 상품 옵션을 한 record로 만듭니다.
- 정확한 중량과 선택 옵션, 상품가, 배송비, 냉장·냉동, 원산지, 두께, 판매 상태를 상품 페이지에서 확인합니다.
- available은 실제 구매 버튼과 옵션이 확인된 경우에만 사용하고, 불명확하면 unknown으로 둡니다.
- 가격·중량·판매 상태에는 각각 evidence를 연결합니다. evidence.field는 price, weight, availability, storage, origin, thickness 중 하나를 사용합니다.
- 무료배송이면 shipping_krw는 0입니다. 조건부 배송비를 확정할 수 없으면 available로 만들지 않습니다.
- 동일 실물 상품의 같은 옵션을 판매처만 바꿔 반복하지 말고 duplicate_key를 같게 둡니다.
- 사용자가 이미 싫다고 한 상품이나 대상은 수집해도 되지만 추천 가능 후보로 해석하지 않습니다.
- 최대 20개까지 수집하고, 충분한 직접 상품 데이터가 모이면 멈춥니다.
- 계산된 총액이나 100g당 가격은 쓰지 않습니다. 실행기가 직접 계산합니다.
"""


def validate_collection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"collection"}:
        raise AdaptiveShoppingError("collection 최상위 형식이 올바르지 않습니다.")
    value = payload["collection"]
    if not isinstance(value, dict) or set(value) != {
        "strategy",
        "checked_at",
        "products",
        "gaps",
    }:
        raise AdaptiveShoppingError("collection 필드가 올바르지 않습니다.")
    strategy = _text(value["strategy"], "collection.strategy")
    checked_at = _text(value["checked_at"], "collection.checked_at")
    gaps = _string_list(value["gaps"], "collection.gaps", maximum=12)
    products = value["products"]
    if not isinstance(products, list) or len(products) > 30:
        raise AdaptiveShoppingError("collection.products가 올바른 배열이 아닙니다.")

    required = {
        "product_id",
        "name",
        "seller",
        "url",
        "option",
        "total_grams",
        "item_price_krw",
        "shipping_krw",
        "availability",
        "storage",
        "origin",
        "cut",
        "thickness",
        "duplicate_key",
        "evidence",
    }
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in products:
        if not isinstance(raw, dict) or set(raw) != required:
            raise AdaptiveShoppingError("product record 형식이 올바르지 않습니다.")
        identifier = _text(raw["product_id"], "product_id")
        if identifier in seen_ids:
            raise AdaptiveShoppingError("product_id가 중복되었습니다.")
        seen_ids.add(identifier)
        grams = raw["total_grams"]
        item_price = raw["item_price_krw"]
        shipping = raw["shipping_krw"]
        if not isinstance(grams, int) or grams <= 0:
            raise AdaptiveShoppingError("total_grams는 양의 정수여야 합니다.")
        if not isinstance(item_price, int) or item_price <= 0:
            raise AdaptiveShoppingError("item_price_krw는 양의 정수여야 합니다.")
        if not isinstance(shipping, int) or shipping < 0:
            raise AdaptiveShoppingError("shipping_krw는 0 이상의 정수여야 합니다.")
        availability = raw["availability"]
        if availability not in {"available", "out_of_stock", "unknown"}:
            raise AdaptiveShoppingError("availability가 올바르지 않습니다.")
        storage = raw["storage"]
        if storage not in {"chilled", "frozen", "unknown"}:
            raise AdaptiveShoppingError("storage가 올바르지 않습니다.")
        evidence = raw["evidence"]
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 12:
            raise AdaptiveShoppingError("product evidence가 올바른 배열이 아닙니다.")
        evidence_fields: set[str] = set()
        normalized_evidence: list[dict[str, str]] = []
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {"field", "finding", "source_url"}:
                raise AdaptiveShoppingError("product evidence 형식이 올바르지 않습니다.")
            field = _text(item["field"], "evidence.field").lower()
            finding = _text(item["finding"], "evidence.finding")
            source_url = _canonical_url(_text(item["source_url"], "evidence.source_url"))
            evidence_fields.add(field)
            normalized_evidence.append(
                {"field": field, "finding": finding, "source_url": source_url}
            )
        validation_issues: list[str] = []
        critical = {"price", "weight", "availability"}
        if availability == "available" and not critical.issubset(evidence_fields):
            availability = "unknown"
            validation_issues.append(
                "가격·중량·판매 상태의 직접 근거가 모두 없어 판매 확인 상태를 unknown으로 낮춤"
            )
        total_price = item_price + shipping
        normalized.append(
            {
                "product_id": identifier,
                "name": _text(raw["name"], "product.name"),
                "seller": _text(raw["seller"], "product.seller"),
                "url": _canonical_url(_text(raw["url"], "product.url")),
                "option": _text(raw["option"], "product.option"),
                "total_grams": grams,
                "item_price_krw": item_price,
                "shipping_krw": shipping,
                "total_price_krw": total_price,
                "price_per_100g_krw": round(total_price * 100 / grams),
                "availability": availability,
                "storage": storage,
                "origin": _optional_text(raw["origin"], "product.origin"),
                "cut": _optional_text(raw["cut"], "product.cut"),
                "thickness": _optional_text(raw["thickness"], "product.thickness"),
                "duplicate_key": _text(raw["duplicate_key"], "product.duplicate_key"),
                "evidence": normalized_evidence,
                "validation_issues": validation_issues,
            }
        )
    return {
        "strategy": strategy,
        "checked_at": checked_at,
        "products": normalized,
        "gaps": gaps,
    }


def _dedupe_key(product: Mapping[str, Any]) -> str:
    declared = _normalize(str(product.get("duplicate_key") or ""))
    if declared:
        return declared
    return "|".join(
        _normalize(str(product.get(key) or ""))
        for key in ("seller", "name", "option", "total_grams")
    )


def merge_collections(collections: list[Mapping[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    strategies: list[str] = []
    checked_at = ""
    gaps: list[str] = []
    for collection in collections:
        strategy = str(collection.get("strategy") or "").strip()
        if strategy and strategy not in strategies:
            strategies.append(strategy)
        checked_at = str(collection.get("checked_at") or checked_at)
        for gap in collection.get("gaps", []):
            text = str(gap).strip()
            if text and text not in gaps:
                gaps.append(text)
        for product in collection.get("products", []):
            key = _dedupe_key(product)
            if key not in merged:
                order.append(key)
            current = dict(product)
            previous = merged.get(key)
            if previous is not None:
                previous_quality = (
                    previous.get("availability") == "available",
                    len(previous.get("evidence", [])),
                )
                current_quality = (
                    current.get("availability") == "available",
                    len(current.get("evidence", [])),
                )
                if previous_quality > current_quality:
                    continue
            merged[key] = current
    products = [merged[key] for key in order]
    for index, product in enumerate(products, 1):
        product["product_id"] = f"product-{index:03d}"
    return {
        "strategy": " → ".join(strategies) or "unknown",
        "checked_at": checked_at,
        "products": products,
        "gaps": gaps[:12],
    }


def collection_gate(
    request: str,
    context_evidence: Mapping[str, Any],
    collection: Mapping[str, Any],
    *,
    minimum_available: int = 8,
) -> dict[str, Any]:
    limit_grams = _quantity_limit_grams(request)
    excluded_terms = _excluded_terms(context_evidence)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for product in collection.get("products", []):
        reason = None
        if product.get("availability") != "available":
            reason = "현재 판매를 직접 확인하지 못함"
        elif limit_grams is not None and int(product.get("total_grams", 0)) > limit_grams:
            reason = f"구매량 제한 {limit_grams}g 초과"
        else:
            haystack = _normalize(
                " ".join(
                    str(product.get(key) or "")
                    for key in ("name", "seller", "option")
                )
            )
            matched = next(
                (term for term in excluded_terms if _normalize(term) in haystack),
                None,
            )
            if matched:
                reason = f"사용자의 기존 제외·불호 대상과 일치: {matched}"
        if reason:
            excluded.append(
                {"product_id": str(product.get("product_id")), "reason": reason}
            )
        else:
            eligible.append(dict(product))

    issues: list[str] = []
    if len(eligible) < minimum_available:
        issues.append(
            f"판매 확인과 조건 검사를 통과한 상품이 {len(eligible)}개로 최소 {minimum_available}개보다 적음"
        )
    seller_count = len({_normalize(item["seller"]) for item in eligible})
    if eligible and seller_count < 3:
        issues.append(f"통과 상품의 판매처가 {seller_count}곳뿐이라 시장 범위가 좁음")
    if _requires_both_storage(request):
        storages = {item["storage"] for item in eligible}
        missing_storage = [
            label
            for key, label in (("chilled", "냉장"), ("frozen", "냉동"))
            if key not in storages
        ]
        if missing_storage:
            issues.append("요청 범위에서 빠진 보관 형태: " + ", ".join(missing_storage))
    if not any(item.get("origin") for item in eligible):
        issues.append("원산지가 확인된 통과 상품이 없음")

    retry_instruction = ""
    if issues:
        retry_instruction = (
            "기존 상품을 반복하지 말고 다음 결손만 보완하세요: " + " / ".join(issues)
        )
    return {
        "passed": not issues,
        "eligible_products": eligible,
        "excluded_products": excluded,
        "issues": issues,
        "retry_instruction": retry_instruction,
        "requirements": {
            "minimum_available": minimum_available,
            "quantity_limit_grams": limit_grams,
            "both_storage_required": _requires_both_storage(request),
            "excluded_terms": excluded_terms,
        },
    }


def product_decision_prompt(
    request: str,
    context_evidence: Mapping[str, Any],
    products: list[Mapping[str, Any]],
) -> str:
    visible_products = []
    for product in products:
        visible_products.append(
            {
                key: product.get(key)
                for key in (
                    "product_id",
                    "name",
                    "seller",
                    "url",
                    "option",
                    "total_grams",
                    "total_price_krw",
                    "price_per_100g_krw",
                    "storage",
                    "origin",
                    "cut",
                    "thickness",
                    "evidence",
                )
            }
        )
    return f"""검증을 통과한 실제 상품 데이터만 사용해 구매 결정을 내리세요. 웹 검색이나 새로운 후보 추가는 하지 않습니다.

[사용자 요청]
{request}

[원문 근거가 있는 사용자 맥락]
{json.dumps(context_evidence, ensure_ascii=False, indent=2)}

[검증 통과 상품]
{json.dumps(visible_products, ensure_ascii=False, indent=2)}

규칙:
- 목록에 없는 상품, 가격, 중량, 특성을 만들지 않습니다.
- 사용자 맥락의 must_preserve 사실을 보존합니다.
- 단순 최저가가 아니라 사용자의 명시 취향과 품질 프리미엄을 함께 판단합니다.
- 최대 5개만 순위를 매기고 실제 1순위 하나를 winner_id로 선택합니다.
- 통과 상품 중에서도 추천할 만한 것이 없으면 winner_id를 null로 두고 no_winner_reason을 씁니다.
- reasons와 risks는 이 데이터에서 확인 가능한 내용만 씁니다. 잡내나 실제 식감처럼 확인하지 못한 속성을 확정하지 않습니다.
"""


def validate_decision(payload: Any, eligible_products: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"decision"}:
        raise AdaptiveShoppingError("decision 최상위 형식이 올바르지 않습니다.")
    value = payload["decision"]
    if not isinstance(value, dict) or set(value) != {
        "winner_id",
        "ranked",
        "summary",
        "no_winner_reason",
        "decision_change_conditions",
    }:
        raise AdaptiveShoppingError("decision 필드가 올바르지 않습니다.")
    by_id = {str(item["product_id"]): item for item in eligible_products}
    ranked = value["ranked"]
    if not isinstance(ranked, list) or len(ranked) > 5:
        raise AdaptiveShoppingError("decision.ranked가 올바른 배열이 아닙니다.")
    required = {"product_id", "rank", "reasons", "risks"}
    normalized_ranked: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    for item in ranked:
        if not isinstance(item, dict) or set(item) != required:
            raise AdaptiveShoppingError("ranked item 형식이 올바르지 않습니다.")
        product_id = _text(item["product_id"], "ranked.product_id")
        if product_id not in by_id:
            raise AdaptiveShoppingError(f"검증 통과 목록에 없는 상품을 순위에 넣었습니다: {product_id}")
        rank = item["rank"]
        if not isinstance(rank, int) or not 1 <= rank <= 5:
            raise AdaptiveShoppingError("ranked.rank가 올바르지 않습니다.")
        if product_id in seen_ids or rank in seen_ranks:
            raise AdaptiveShoppingError("ranked 상품 또는 순위가 중복되었습니다.")
        seen_ids.add(product_id)
        seen_ranks.add(rank)
        normalized_ranked.append(
            {
                "product_id": product_id,
                "rank": rank,
                "reasons": _string_list(item["reasons"], "ranked.reasons", maximum=5),
                "risks": _string_list(item["risks"], "ranked.risks", maximum=5),
            }
        )
    normalized_ranked.sort(key=lambda item: item["rank"])
    expected_ranks = list(range(1, len(normalized_ranked) + 1))
    if [item["rank"] for item in normalized_ranked] != expected_ranks:
        raise AdaptiveShoppingError("ranked 순위는 1부터 연속되어야 합니다.")

    winner = value["winner_id"]
    no_winner_reason = value["no_winner_reason"]
    if winner is None:
        no_winner_reason = _text(no_winner_reason, "decision.no_winner_reason")
    else:
        winner = _text(winner, "decision.winner_id")
        if winner not in by_id or winner not in seen_ids:
            raise AdaptiveShoppingError("winner_id는 순위에 포함된 검증 통과 상품이어야 합니다.")
        if no_winner_reason is not None:
            raise AdaptiveShoppingError("winner가 있을 때 no_winner_reason은 null이어야 합니다.")
    return {
        "winner_id": winner,
        "ranked": normalized_ranked,
        "summary": _text(value["summary"], "decision.summary"),
        "no_winner_reason": no_winner_reason,
        "decision_change_conditions": _string_list(
            value["decision_change_conditions"],
            "decision.decision_change_conditions",
            maximum=6,
        ),
    }


def _money(value: int) -> str:
    return f"{value:,}원"


def render_result(
    state: Mapping[str, Any],
    *,
    completed: bool,
) -> str:
    collection = state.get("collection", {})
    gate = state.get("collection_gate", {})
    products = list(gate.get("eligible_products", []))
    by_id = {str(item["product_id"]): item for item in products}
    decision = state.get("decision")
    lines: list[str] = []
    if not completed or not isinstance(decision, Mapping):
        lines.extend(
            [
                "# 미완료 — 상품 데이터 검증 미통과",
                "",
                "현재 자료는 최종 추천으로 사용하면 안 됩니다.",
                "",
                "## 통과하지 못한 조건",
                "",
            ]
        )
        for issue in gate.get("issues", []):
            lines.append(f"- {issue}")
        lines.extend(["", "## 현재 확보된 판매 확인 상품", ""])
        for product in products[:12]:
            lines.append(
                f"- {product['name']} · {product['option']} · "
                f"{_money(product['total_price_krw'])} · "
                f"100g당 {_money(product['price_per_100g_krw'])} · {product['url']}"
            )
        return "\n".join(lines).rstrip() + "\n"

    winner_id = decision.get("winner_id")
    if winner_id is None:
        lines.extend(
            [
                "# 최종 판단 — 통과 상품 중 추천 없음",
                "",
                str(decision.get("no_winner_reason") or decision.get("summary")),
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    winner = by_id[str(winner_id)]
    lines.extend(
        [
            "# 최종 추천",
            "",
            f"**{winner['name']} — {winner['option']}**",
            "",
            f"총 {_money(winner['total_price_krw'])} · "
            f"{winner['total_grams']:,}g · 100g당 {_money(winner['price_per_100g_krw'])}",
            "",
            str(decision["summary"]),
            "",
            f"구매 링크: {winner['url']}",
            "",
            "## 압축 비교",
            "",
            "| 순위 | 상품 | 총액 | 100g당 | 보관 | 원산지 |",
            "|---:|---|---:|---:|---|---|",
        ]
    )
    for ranked in decision.get("ranked", []):
        product = by_id[ranked["product_id"]]
        lines.append(
            f"| {ranked['rank']} | {product['name']} · {product['option']} | "
            f"{_money(product['total_price_krw'])} | "
            f"{_money(product['price_per_100g_krw'])} | "
            f"{product['storage']} | {product.get('origin') or '미확인'} |"
        )
        lines.append("")
        lines.append("  - 추천 근거: " + " · ".join(ranked["reasons"]))
        if ranked["risks"]:
            lines.append("  - 위험·한계: " + " · ".join(ranked["risks"]))
    if decision.get("decision_change_conditions"):
        lines.extend(["", "## 판단이 바뀌는 조건", ""])
        for condition in decision["decision_change_conditions"]:
            lines.append(f"- {condition}")
    lines.extend(
        [
            "",
            f"확인 시점: {collection.get('checked_at') or '미기록'}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _save_state(run_dir: Path, state: Mapping[str, Any]) -> None:
    (run_dir / "adaptive-shopping-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    completed = state.get("state") == "completed"
    (run_dir / "result.md").write_text(
        render_result(state, completed=completed),
        encoding="utf-8",
    )


def run_adaptive_shopping(
    request: str,
    *,
    context: str,
    engine: OS.ProblemSolvingEngine,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    policy: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    minimum_available: int = 8,
    max_changes: int = 1,
) -> tuple[Path, dict[str, Any]]:
    cleaned = request.strip()
    if not cleaned or len(cleaned) > MAX_REQUEST_CHARS:
        raise AdaptiveShoppingError("요청은 1~10,000자여야 합니다.")
    if len(context) > MAX_CONTEXT_CHARS:
        raise AdaptiveShoppingError("관련 대화 맥락은 100,000자 이하여야 합니다.")
    if not supports_request(cleaned):
        raise AdaptiveShoppingError("현재 실험기는 온라인 상품 구매 요청만 지원합니다.")
    if not 1 <= minimum_available <= 20:
        raise AdaptiveShoppingError("minimum_available은 1~20이어야 합니다.")
    if max_changes not in {0, 1}:
        raise AdaptiveShoppingError("max_changes는 0 또는 1이어야 합니다.")
    chosen = run_id or f"adaptive-shopping-{OS.make_run_id().removeprefix('psos-')}"
    if re.fullmatch(r"[A-Za-z0-9._-]+", chosen) is None:
        raise AdaptiveShoppingError("run ID 형식이 올바르지 않습니다.")
    run_dir = output_root.expanduser().resolve() / chosen
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.txt").write_text(cleaned + "\n", encoding="utf-8")
    if context.strip():
        (run_dir / "context.txt").write_text(context.strip() + "\n", encoding="utf-8")

    model_policy = dict(policy or OS.load_model_policy())
    capabilities = engine.capabilities()
    if not capabilities.ai_reasoning:
        raise AdaptiveShoppingError(capabilities.detail or "AI 실행 capability가 없습니다.")
    if not capabilities.web_search:
        raise AdaptiveShoppingError("상품 수집에는 웹 검색 capability가 필요합니다.")

    context_evidence = CONTEXT.extract_context_evidence(
        cleaned,
        context,
        engine=engine,
        run_dir=run_dir,
        policy=model_policy,
    )
    state: dict[str, Any] = {
        "version": 1,
        "run_id": chosen,
        "domain": "shopping_product",
        "state": "collecting",
        "request": cleaned,
        "selected_action": "collect_structured_products",
        "context_evidence": context_evidence,
        "attempts": [],
        "changes_used": 0,
        "collection": None,
        "collection_gate": None,
        "decision": None,
        "engine_trace": [],
    }

    research_profile = replace(
        model_policy["routes"]["RESEARCH"]["primary"],
        reasoning_effort="medium",
        sandbox="read-only",
    )
    collections: list[dict[str, Any]] = []
    retry_instruction = ""
    for attempt_index in range(max_changes + 1):
        raw = _invoke(
            engine,
            run_dir,
            name=f"adaptive-product-collection-{attempt_index + 1}",
            phase="adaptive-acquisition",
            route="RESEARCH",
            profile=research_profile,
            schema=COLLECTION_SCHEMA,
            prompt=product_collection_prompt(
                cleaned,
                context_evidence,
                mode="coverage" if attempt_index == 0 else "targeted-gap-fill",
                prior_products=(
                    merge_collections(collections)["products"] if collections else []
                ),
                retry_instruction=retry_instruction,
            ),
        )
        collection = validate_collection(raw)
        collections.append(collection)
        merged = merge_collections(collections)
        gate = collection_gate(
            cleaned,
            context_evidence,
            merged,
            minimum_available=minimum_available,
        )
        state["attempts"].append(
            {
                "index": attempt_index + 1,
                "action": "collect_structured_products",
                "mode": "coverage" if attempt_index == 0 else "targeted-gap-fill",
                "collection": collection,
                "gate": gate,
            }
        )
        state["collection"] = merged
        state["collection_gate"] = gate
        if gate["passed"]:
            break
        if attempt_index < max_changes:
            state["changes_used"] = attempt_index + 1
            retry_instruction = gate["retry_instruction"]

    gate = state["collection_gate"]
    if not gate["passed"]:
        state["state"] = "partial"
        state["engine_trace"] = engine.trace()
        _save_state(run_dir, state)
        return run_dir, state

    decision_profile = replace(
        model_policy["routes"]["DIRECT"]["primary"],
        web_search=False,
        sandbox="read-only",
    )
    raw_decision = _invoke(
        engine,
        run_dir,
        name="adaptive-product-decision",
        phase="adaptive-decision",
        route="DIRECT",
        profile=decision_profile,
        schema=DECISION_SCHEMA,
        prompt=product_decision_prompt(
            cleaned,
            context_evidence,
            gate["eligible_products"],
        ),
    )
    decision = validate_decision(raw_decision, gate["eligible_products"])
    state["decision"] = decision
    state["state"] = "completed"
    state["engine_trace"] = engine.trace()
    _save_state(run_dir, state)
    return run_dir, state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--request-file", type=Path)
    parser.add_argument("--context-file", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--minimum-available", type=int, default=8)
    parser.add_argument("--max-changes", type=int, choices=(0, 1), default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    request = (
        args.request
        if args.request is not None
        else args.request_file.expanduser().read_text(encoding="utf-8")
    )
    context = (
        args.context_file.expanduser().read_text(encoding="utf-8")
        if args.context_file is not None
        else ""
    )
    engine = OS.CodexEngine(ROOT, enable_search=True)
    try:
        run_dir, state = run_adaptive_shopping(
            request,
            context=context,
            engine=engine,
            output_root=args.output_root,
            run_id=args.run_id,
            minimum_available=args.minimum_available,
            max_changes=args.max_changes,
        )
    except (AdaptiveShoppingError, CONTEXT.AdaptiveContextError, OS.ProblemSolvingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print((run_dir / "result.md").read_text(encoding="utf-8").rstrip())
    print(f"\n상태: {state['state']}")
    print(f"실행 기록: {run_dir}")
    return 0 if state["state"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
