import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_product_prompt_promotion_gate.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "product-evidence-hard-cases.json"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_product_prompt_promotion_gate",
    MODULE_PATH,
)
GATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


CASE_IDS = [
    "product-option-price-mismatch",
    "product-review-scope-mismatch",
    "product-sale-status-mismatch",
]


def result(case_id, decision, *, patch_failures=None):
    return {
        "case_id": case_id,
        "mapping": {"A": "applied_baseline", "B": "patched"},
        "scores": {
            "A": {"critical_failures": []},
            "B": {"critical_failures": list(patch_failures or [])},
        },
        "preferred_candidate_ids": [],
        "decision": decision,
        "reason": "fixture",
    }


def payload(decisions, *, recorded=None):
    value = {
        "version": 1,
        "promotion_policy": {
            "required_case_ids": list(CASE_IDS),
            "minimum_patch_wins": 2,
            "maximum_patch_critical_failures": 0,
        },
        "method": {},
        "results": [
            result(case_id, decision)
            for case_id, decision in zip(CASE_IDS, decisions)
        ],
    }
    if recorded is not None:
        value["recorded_gate_decision"] = recorded
    return value


class ProductPromptPromotionGateTests(unittest.TestCase):
    def test_one_patch_win_retains_current_baseline(self):
        evaluated = GATE.evaluate_payload(
            payload(["no_winner", "promote_patch", "no_winner"])
        )
        self.assertFalse(evaluated["approved"])
        self.assertEqual("retain_current_baseline", evaluated["decision"])
        self.assertEqual(1, evaluated["patch_wins"])
        self.assertEqual(2, evaluated["ties"])

    def test_two_patch_wins_approve_when_no_critical_failure(self):
        evaluated = GATE.evaluate_payload(
            payload(["promote_patch", "promote_patch", "no_winner"])
        )
        self.assertTrue(evaluated["approved"])
        self.assertEqual("approve_product_baseline", evaluated["decision"])

    def test_patch_critical_failure_blocks_promotion(self):
        value = payload(["promote_patch", "promote_patch", "no_winner"])
        value["results"][0] = result(
            CASE_IDS[0],
            "promote_patch",
            patch_failures=["원하는 옵션의 가격을 잘못 연결함"],
        )
        evaluated = GATE.evaluate_payload(value)
        self.assertFalse(evaluated["approved"])
        self.assertEqual(1, evaluated["patch_critical_failure_count"])

    def test_missing_required_case_is_rejected(self):
        value = payload(["no_winner", "promote_patch", "no_winner"])
        value["results"].pop()
        with self.assertRaises(GATE.ProductPromptPromotionError):
            GATE.evaluate_payload(value)

    def test_repository_record_matches_calculated_gate(self):
        evaluated = GATE.evaluate_file()
        self.assertFalse(evaluated["approved"])
        self.assertEqual("retain_current_baseline", evaluated["decision"])
        self.assertEqual(1, evaluated["patch_wins"])

    def test_repository_fixture_matches_gate_case_set(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture_ids = [item["id"] for item in fixture["cases"]]
        self.assertEqual(CASE_IDS, fixture["promotion_policy"]["required_case_ids"])
        self.assertEqual(CASE_IDS, fixture_ids)
        self.assertEqual(2, fixture["promotion_policy"]["minimum_patch_wins"])
        self.assertTrue(
            all(item["application"]["critical_failures"] for item in fixture["cases"])
        )

    def test_declared_gate_mismatch_is_rejected(self):
        value = payload(
            ["no_winner", "promote_patch", "no_winner"],
            recorded="approve_product_baseline",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.json"
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(GATE.ProductPromptPromotionError):
                GATE.evaluate_file(path)


if __name__ == "__main__":
    unittest.main()
