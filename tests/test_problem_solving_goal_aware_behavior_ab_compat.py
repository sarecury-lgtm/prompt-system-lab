import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_goal_aware_behavior_ab_compat as COMPAT  # noqa: E402


class GoalAwareBehaviorABCompatTests(unittest.TestCase):
    def test_model_echoed_case_id_is_replaced_by_harness_case_id(self):
        payload = {
            "version": 1,
            "case_id": "wrong-or-inferred-value",
            "candidates": [
                {
                    "candidate_id": "A",
                    "goal_fit": 5,
                    "clarification_calibration": 5,
                    "initiative": 5,
                    "independent_judgment": 5,
                    "evidence_priority": 5,
                    "scope_control": 5,
                    "tone": 5,
                    "critical_failures": [],
                    "finding": "필요한 질문을 했다.",
                },
                {
                    "candidate_id": "B",
                    "goal_fit": 3,
                    "clarification_calibration": 2,
                    "initiative": 2,
                    "independent_judgment": 3,
                    "evidence_priority": 3,
                    "scope_control": 3,
                    "tone": 4,
                    "critical_failures": [],
                    "finding": "근거 없이 바로 추천했다.",
                },
            ],
            "preferred_candidate_ids": ["A"],
            "conclusion": "후보 A가 더 적합하다.",
        }

        validated = COMPAT._validate_assessment_with_harness_case_id(
            payload,
            "ask-when-goal-is-unclear",
        )

        self.assertEqual("ask-when-goal-is-unclear", validated["case_id"])


if __name__ == "__main__":
    unittest.main()
