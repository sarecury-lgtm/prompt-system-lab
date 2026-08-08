import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PsosBlindRuntimeRuleTests(unittest.TestCase):
    def test_runtime_rules_cover_recommendation_chain_and_exact_option(self):
        text = (ROOT / "extensions" / "PSOS_BLIND_RUNTIME_RULES.md").read_text(encoding="utf-8")
        required = [
            "구체 후보를 최소 하나 검토",
            "정확한 옵션 또는 SKU",
            "옵션 추가금",
            "검색 가설",
            "새 조건과 충돌하는 기존 후보와 순위는 즉시 다시 평가",
        ]
        for needle in required:
            self.assertIn(needle, text)

    def test_setup_includes_runtime_rules_for_custom_gpt_instructions(self):
        text = (ROOT / "extensions" / "PSOS_BLIND_GITHUB_ACTION_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("PSOS_BLIND_RUNTIME_RULES.md", text)
        self.assertIn("PSOS_BLIND_GITHUB_ACTION_RULES.md", text)

    def test_shopping_fixture_catches_option_surcharge_and_correction(self):
        fixture = json.loads(
            (ROOT / "evaluation" / "psos-controller" / "shopping_recommendation_regression.json").read_text(
                encoding="utf-8"
            )
        )
        surcharge = next(
            item for item in fixture["fixed_product_fixtures"] if item["id"] == "page-with-option-surcharge"
        )
        unit_price = (surcharge["page_base_price_krw"] + surcharge["option_surcharge_krw"]) / surcharge["weight_g"] * 100
        self.assertEqual(unit_price, surcharge["verified_unit_price_krw_per_100g"])
        self.assertEqual(fixture["scenario"]["normalized_constraint_after_correction"]["default_cap_krw_per_100g"], 2000)
        self.assertTrue(any("Berkshire" in item for item in fixture["fail_conditions"]))
        self.assertTrue(any("search-results or category link" in item for item in fixture["fail_conditions"]))

    def test_active_goal_is_shopping_regression(self):
        active = json.loads((ROOT / "ACTIVE_GOAL.json").read_text(encoding="utf-8"))
        self.assertEqual(active["current_task"]["id"], "shopping-recommendation-regression-v1")
        self.assertNotIn("CORE", active["current_task"]["allowed_change_classes"])


if __name__ == "__main__":
    unittest.main()
