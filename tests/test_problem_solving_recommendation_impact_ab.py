import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_goal_aware_behavior_ab as AB  # noqa: E402
import problem_solving_recommendation_impact_ab as RI  # noqa: E402


class RecommendationImpactABTests(unittest.TestCase):
    def test_fixture_focuses_on_decisions_and_preference_sensitivity(self):
        cases = AB.load_cases(RI.CASES_PATH)
        self.assertEqual(6, len(cases))
        self.assertEqual(
            {
                "food-decision",
                "shopping-decision",
                "financial-product-decision",
                "trading-decision",
                "housing-decision",
            },
            {case["domain"] for case in cases},
        )
        peach_ids = {
            case["id"] for case in cases if case["domain"] == "food-decision"
        }
        self.assertEqual(
            {"peach-highest-taste-peak", "peach-lowest-regret"},
            peach_ids,
        )
        self.assertTrue(all(len(case["turns"]) == 1 for case in cases))
        self.assertTrue(all(case["criteria"] for case in cases))
        self.assertTrue(all(case["critical_failures"] for case in cases))

    def test_compare_page_places_candidates_side_by_side_and_delays_reveal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_id = "sample"
            case_dir = root / case_id
            (case_dir / "baseline").mkdir(parents=True)
            (case_dir / "goal_aware").mkdir(parents=True)
            (case_dir / "case.json").write_text(
                json.dumps(
                    {
                        "id": case_id,
                        "title": "샘플 선택",
                        "context_markdown": "후보를 비교할 자료다.",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (case_dir / "baseline" / "transcript.md").write_text(
                "**user**\n\n하나 골라줘.\n\n**assistant**\n\n기존 답변",
                encoding="utf-8",
            )
            (case_dir / "goal_aware" / "transcript.md").write_text(
                "**user**\n\n하나 골라줘.\n\n**assistant**\n\n새 답변",
                encoding="utf-8",
            )
            manifest = {
                "cases": [
                    {
                        "id": case_id,
                        "title": "샘플 선택",
                        "candidate_mapping": {"A": "goal_aware", "B": "baseline"},
                        "variants": {
                            "baseline": {
                                "transcript_path": f"{case_id}/baseline/transcript.md"
                            },
                            "goal_aware": {
                                "transcript_path": f"{case_id}/goal_aware/transcript.md"
                            },
                        },
                    }
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            output = RI.build_compare_html(
                {
                    "output_dir": str(root),
                    "manifest_path": str(manifest_path),
                }
            )
            text = output.read_text(encoding="utf-8")

            self.assertIn("후보 A", text)
            self.assertIn("후보 B", text)
            self.assertIn("실제로 더 따르고 싶은 답변", text)
            self.assertIn("추천·행동이 달라짐", text)
            self.assertIn("실제 선택이나 행동이 달라질 정도", text)
            self.assertIn("정체 공개", text)
            self.assertIn("disabled", text)
            self.assertIn("goal-aware", text)


if __name__ == "__main__":
    unittest.main()
