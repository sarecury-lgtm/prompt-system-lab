import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


APPROVED = load(
    "approved_prompt_baseline_integration",
    ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py",
)
REVIEW = load(
    "approved_prompt_patch_review_integration",
    ROOT / "scripts" / "problem_solving_prompt_approved_patch_review.py",
)


class ApprovedPromptIntegrationTests(unittest.TestCase):
    def test_repository_chart_asset_is_selected(self):
        selected = APPROVED.select_approved_prompt(
            "여러 시간대 차트에서 진입과 손절·분할익절을 판단하는 매매 프롬프트를 만들어줘."
        )
        self.assertIsNotNone(selected)
        self.assertEqual("chart-trade-plan", selected["id"])
        self.assertTrue(selected["prompt"].startswith("# 다중 시간대 차트 매매 피드백 프롬프트"))
        self.assertIn("실행 가능한 매매 계획", selected["prompt"])

    def test_manual_review_starts_from_approved_chart_asset(self):
        case = REVIEW.REVIEW.load_cases()["chart-trade-plan"]
        prompt = REVIEW.approved_baseline_prompt(case)
        self.assertTrue(prompt.startswith("# 다중 시간대 차트 매매 피드백 프롬프트"))
        self.assertNotIn("다음 사용자 요청을 수행하세요.", prompt)

    def test_unapproved_product_case_keeps_generic_baseline(self):
        case = REVIEW.REVIEW.load_cases()["product-evidence-choice"]
        prompt = REVIEW.approved_baseline_prompt(case)
        self.assertTrue(prompt.startswith("다음 사용자 요청을 수행하세요."))
        self.assertNotIn("다중 시간대 차트", prompt)


if __name__ == "__main__":
    unittest.main()
