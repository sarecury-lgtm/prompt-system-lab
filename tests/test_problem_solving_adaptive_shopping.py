import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_adaptive_shopping as SHOPPING
import problem_solving_os as OS


class FakeEngine:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def capabilities(self):
        return OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
        )

    def execute(self, prompt, run_dir, invocation):
        self.calls.append(invocation.name)
        if invocation.name not in self.responses:
            raise AssertionError(f"unexpected invocation: {invocation.name}")
        return copy.deepcopy(self.responses[invocation.name])

    def trace(self):
        return [{"name": name} for name in self.calls]


def profile(*, search=False):
    return OS.ModelProfile(
        model="fake",
        reasoning_effort="low",
        web_search=search,
        sandbox="read-only",
    )


def policy():
    return {
        "router_fallback": profile(search=False),
        "routes": {
            "RESEARCH": {"primary": profile(search=True), "fallback": None},
            "DIRECT": {"primary": profile(search=False), "fallback": None},
        },
    }


def product(
    product_id,
    name,
    seller,
    storage,
    *,
    price=15000,
    shipping=0,
    grams=1000,
    availability="available",
    duplicate_key=None,
    evidence_fields=("price", "weight", "availability", "storage"),
):
    url = f"https://shop.example/{product_id}"
    return {
        "product_id": product_id,
        "name": name,
        "seller": seller,
        "url": url,
        "option": f"{grams}g 기본 옵션",
        "total_grams": grams,
        "item_price_krw": price,
        "shipping_krw": shipping,
        "availability": availability,
        "storage": storage,
        "origin": "국산",
        "cut": "삼겹살",
        "thickness": "구이용 15mm",
        "duplicate_key": duplicate_key or f"{name}-{grams}",
        "evidence": [
            {
                "field": field,
                "finding": f"{field} 직접 확인",
                "source_url": url,
            }
            for field in evidence_fields
        ],
    }


def collection(products, strategy="상품 페이지 직접 확인"):
    return {
        "collection": {
            "strategy": strategy,
            "checked_at": "2026-08-04T20:00:00+09:00",
            "products": products,
            "gaps": [],
        }
    }


def context_response():
    return {
        "context_evidence": {
            "summary": "기존 불호와 두께 선호를 구매 판단에 보존한다.",
            "facts": [
                {
                    "id": "fact-1",
                    "category": "prior_experience",
                    "statement": "템포크 재추천 금지",
                    "source_quote": "템포크를 실제로 먹어봤는데 매우 별로였다.",
                    "subject_terms": ["템포크"],
                    "must_preserve": True,
                },
                {
                    "id": "fact-2",
                    "category": "preference",
                    "statement": "두꺼운 구이용 선호",
                    "source_quote": "두꺼운 삼겹살을 선호한다.",
                    "subject_terms": ["삼겹살"],
                    "must_preserve": True,
                },
            ],
            "unresolved": [],
        }
    }


def decision_response():
    return {
        "decision": {
            "winner_id": "product-004",
            "ranked": [
                {
                    "product_id": "product-004",
                    "rank": 1,
                    "reasons": ["냉장이고 국산이며 총액과 중량이 직접 확인됨"],
                    "risks": ["실제 지방 편차는 상품 페이지에서 확정할 수 없음"],
                },
                {
                    "product_id": "product-002",
                    "rank": 2,
                    "reasons": ["판매 상태와 가격이 직접 확인됨"],
                    "risks": ["냉동 상품"],
                },
                {
                    "product_id": "product-003",
                    "rank": 3,
                    "reasons": ["다른 판매처의 비교 가능한 옵션"],
                    "risks": ["냉동 상품"],
                },
            ],
            "summary": "냉장 품질 프리미엄과 확인 가능한 실구매가를 함께 보면 1순위가 가장 적합하다.",
            "no_winner_reason": None,
            "decision_change_conditions": ["판매 중단 또는 배송비 변경"],
        }
    }


class AdaptiveShoppingTests(unittest.TestCase):
    def test_collection_calculates_total_and_unit_price(self):
        payload = collection(
            [product("p1", "국산 삼겹", "판매처 A", "chilled", price=12000, shipping=3000, grams=600)]
        )
        normalized = SHOPPING.validate_collection(payload)
        item = normalized["products"][0]
        self.assertEqual(15000, item["total_price_krw"])
        self.assertEqual(2500, item["price_per_100g_krw"])
        self.assertEqual("available", item["availability"])

    def test_available_product_without_critical_evidence_is_downgraded(self):
        payload = collection(
            [
                product(
                    "p1",
                    "근거 부족 삼겹",
                    "판매처 A",
                    "frozen",
                    evidence_fields=("price", "availability"),
                )
            ]
        )
        normalized = SHOPPING.validate_collection(payload)
        item = normalized["products"][0]
        self.assertEqual("unknown", item["availability"])
        self.assertTrue(item["validation_issues"])

    def test_gate_filters_prior_dislike_and_requires_real_coverage(self):
        context = SHOPPING.CONTEXT.validate_context_evidence(
            context_response(),
            "템포크를 실제로 먹어봤는데 매우 별로였다.\n두꺼운 삼겹살을 선호한다.",
        )
        normalized = SHOPPING.validate_collection(
            collection(
                [
                    product("p1", "템포크 삼겹살", "판매처 X", "frozen"),
                    product("p2", "국산 냉동 삼겹 A", "판매처 A", "frozen"),
                    product("p3", "국산 냉동 삼겹 B", "판매처 B", "frozen"),
                    product("p4", "국산 냉장 삼겹 C", "판매처 C", "chilled"),
                ]
            )
        )
        merged = SHOPPING.merge_collections([normalized])
        gate = SHOPPING.collection_gate(
            "냉장과 냉동 모두 포함해 온라인 삼겹살을 추천해 줘. 3kg 이하.",
            context,
            merged,
            minimum_available=3,
        )
        self.assertTrue(gate["passed"])
        self.assertEqual(3, len(gate["eligible_products"]))
        self.assertIn("템포크", gate["excluded_products"][0]["reason"])

    def test_controller_changes_collection_method_once_then_completes(self):
        first = collection(
            [
                product("p1", "템포크 삼겹살", "판매처 X", "frozen"),
                product("p2", "국산 냉동 삼겹 A", "판매처 A", "frozen", price=13000),
                product("p3", "국산 냉동 삼겹 B", "판매처 B", "frozen", price=14000),
            ],
            strategy="넓은 상품 페이지 수집",
        )
        second = collection(
            [
                product("p4", "국산 냉장 삼겹 C", "판매처 C", "chilled", price=18000),
            ],
            strategy="냉장·판매처 결손 보완",
        )
        engine = FakeEngine(
            {
                "adaptive-context-evidence": context_response(),
                "adaptive-product-collection-1": first,
                "adaptive-product-collection-2": second,
                "adaptive-product-decision": decision_response(),
            }
        )
        request = "냉장과 냉동 모두 포함해 온라인 삼겹살을 추천해 줘. 총 구매량 3kg 이하."
        context = "템포크를 실제로 먹어봤는데 매우 별로였다.\n두꺼운 삼겹살을 선호한다."
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = SHOPPING.run_adaptive_shopping(
                request,
                context=context,
                engine=engine,
                output_root=Path(temp_dir),
                policy=policy(),
                run_id="adaptive-test",
                minimum_available=3,
                max_changes=1,
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("completed", state["state"])
        self.assertEqual(1, state["changes_used"])
        self.assertEqual(2, len(state["attempts"]))
        self.assertEqual("product-004", state["decision"]["winner_id"])
        self.assertIn("# 최종 추천", result)
        self.assertNotIn("템포크 삼겹살", result)
        self.assertEqual(
            [
                "adaptive-context-evidence",
                "adaptive-product-collection-1",
                "adaptive-product-collection-2",
                "adaptive-product-decision",
            ],
            engine.calls,
        )

    def test_incomplete_collection_is_not_rendered_as_recommendation(self):
        engine = FakeEngine(
            {
                "adaptive-product-collection-1": collection(
                    [product("p1", "국산 냉동 삼겹", "판매처 A", "frozen")]
                )
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = SHOPPING.run_adaptive_shopping(
                "온라인 삼겹살 상품을 추천해 줘.",
                context="",
                engine=engine,
                output_root=Path(temp_dir),
                policy=policy(),
                run_id="adaptive-partial",
                minimum_available=2,
                max_changes=0,
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("partial", state["state"])
        self.assertIsNone(state["decision"])
        self.assertIn("# 미완료", result)
        self.assertNotIn("# 최종 추천", result)
        self.assertEqual(["adaptive-product-collection-1"], engine.calls)


if __name__ == "__main__":
    unittest.main()
