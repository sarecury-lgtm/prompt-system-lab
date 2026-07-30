import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual_deep.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_manual_deep_test", MODULE_PATH)
DEEP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = DEEP
SPEC.loader.exec_module(DEEP)


def route_result():
    reason = "현재 판매 상품 확인이 필요한 단일 조사"
    return {
        "goal_ledger": {
            "parent_goal": "현재 온라인에서 구매 가능한 복숭아를 찾는다.",
            "current_goal_hypothesis": "매우 달고 탱탱하지만 아삭하지 않은 상품을 원한다.",
            "fixed_constraints": [
                "현재 온라인에서 실제 판매 중인 상품이어야 한다.",
                "당도가 매우 높아야 한다.",
                "아삭한 딱복은 제외한다.",
            ],
            "current_position": "상품과 판매 상태는 아직 확인되지 않았다.",
            "selected_route": "RESEARCH",
            "secondary_route": None,
            "route_reason": reason,
            "current_step": "온라인 판매 상품을 수집하고 비교한다.",
            "why_this_step_matters": "현재 가격과 판매 상태가 변하기 때문이다.",
            "completion_condition": "실제 주문 가능한 상품을 링크와 함께 추천한다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": "RESEARCH",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": reason,
        },
    }


def good_report():
    return """# 현재 판매 복숭아 조사

조사 기준: 2026년 7월 30일 오후 8시

## 후보 1
- 상품: A 제왕황도
- 판매자: A농원
- 현재 가격: 32,300원
- 구성: 3kg
- 판매 상태: 주문 가능
- 직접 URL: https://shop-a.example/product/peach-a

## 후보 2
- 상품: B 백도
- 판매처: B스토어
- 현재 가격: 41,000원
- 구성: 4kg
- 구매 가능 상태: 판매 중
- 직접 URL: https://shop-b.example/goods/peach-b

## 후보 3
- 상품: C 황도
- 판매자: C과수원
- 현재 가격: 29,900원
- 구성: 2kg
- 판매 상태: 구매 버튼 확인
- 직접 URL: https://shop-c.example/item/peach-c

확인 사실과 판매자 주장을 분리해 비교했으며 A를 최종 추천한다.
공식 품종 참고: https://official.example/research/peach-texture
"""


def weak_normalized_response():
    return json.dumps(
        {
            "execution": {
                "status": "completed",
                "summary": "보고서 정규화",
                "result_markdown": "신비복숭아와 납작복숭아가 유력하다.",
                "capabilities_used": ["analysis", "provided_context"],
                "needed_capability": None,
                "handoff": None,
                "artifacts": [],
                "evidence": [
                    {
                        "source": "provided_context",
                        "finding": "품종 설명이 제공되었다.",
                        "kind": "provided_context",
                    }
                ],
                "limitations": [],
            }
        },
        ensure_ascii=False,
    )


class DeepResearchBridgeTests(unittest.TestCase):
    def make_bridge(self, directory):
        return DEEP.ManualBridge(runs_dir=Path(directory) / "runs")

    def start_product_research(self, bridge, run_id):
        with mock.patch.object(
            DEEP.manual.problem_os,
            "make_run_id",
            return_value=run_id,
        ):
            bridge.start(
                "현재 온라인 판매 중인 복숭아 상품을 가격과 링크까지 조사해줘.",
                research_mode="deep",
            )
        return bridge.submit(run_id, json.dumps(route_result(), ensure_ascii=False))

    def test_prompt_fixes_unit_to_individual_listings(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = self.make_bridge(directory)
            stage = self.start_product_research(bridge, "deep-prompt")
            self.assertEqual(stage["response_kind"], "markdown")
            self.assertIn("개별 판매 상품", stage["prompt"])
            self.assertIn("직접 상품 URL", stage["prompt"])
            self.assertIn("검색 결과 요약문", stage["prompt"])
            self.assertNotIn("reasoning_effort", stage["prompt"])
            self.assertNotIn("현재 실행 프로필", stage["prompt"])

    def test_category_only_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = self.make_bridge(directory)
            self.start_product_research(bridge, "deep-bad")
            report = (
                "# 온라인 복숭아 조사\n\n"
                "신비복숭아와 납작복숭아는 일반적으로 달고 쫀득한 계열이다. "
                "쿠팡 등 여러 온라인몰에서 판매되는 것으로 보이며 품종 특성상 취향에 맞을 수 있다. "
                "다만 숙도와 배송 상태에 따라 차이가 있다."
            )
            with self.assertRaises(DEEP.manual.ManualBridgeError) as raised:
                bridge.submit("deep-bad", report)
            self.assertIn("실제 출처 URL", str(raised.exception))
            self.assertEqual(bridge.get("deep-bad")["response_kind"], "markdown")

    def test_listing_report_passes_to_normalizer_with_preservation_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = self.make_bridge(directory)
            self.start_product_research(bridge, "deep-good")
            stage = bridge.submit("deep-good", good_report())
            self.assertEqual(stage["state"], "awaiting_primary")
            self.assertEqual(stage["response_kind"], "json")
            self.assertIn("심층 리서치 결과 정규화기", stage["prompt"])
            self.assertIn("정규화 보존 계약", stage["prompt"])
            self.assertIn("provided_context", stage["prompt"])

    def test_normalizer_cannot_drop_product_links(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = self.make_bridge(directory)
            self.start_product_research(bridge, "deep-normalize-bad")
            bridge.submit("deep-normalize-bad", good_report())
            with self.assertRaises(DEEP.manual.ManualBridgeError) as raised:
                bridge.submit("deep-normalize-bad", weak_normalized_response())
            self.assertIn("구매 정보를 보존하지 못했습니다", str(raised.exception))
            session = bridge.get("deep-normalize-bad")
            self.assertEqual(session["response_kind"], "json")
            self.assertIn("직접 판매·상품 URL", session["error"])

    def test_legacy_bad_report_is_revalidated_and_rewound(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = self.make_bridge(directory)
            self.start_product_research(bridge, "deep-legacy")
            bridge.submit("deep-legacy", good_report())

            run_dir = Path(directory) / "runs" / "deep-legacy"
            state = DEEP.manual.read_state(run_dir)
            report_path = run_dir / state["deep_research_reports"]["primary"]
            report_path.write_text(
                "# 약한 보고서\n\n신비복숭아와 납작복숭아가 좋다고 알려져 있다.",
                encoding="utf-8",
            )

            rewound = bridge.submit("deep-legacy", weak_normalized_response())
            self.assertEqual(rewound["response_kind"], "markdown")
            self.assertIn("보고서 단계로 되돌렸습니다", rewound["error"])
            self.assertIn("개별 판매 상품", rewound["prompt"])


if __name__ == "__main__":
    unittest.main()
