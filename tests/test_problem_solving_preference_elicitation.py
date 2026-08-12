import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_session_verified as VERIFIED
import problem_solving_request_contract as REQUEST


class PreferenceElicitationTests(unittest.TestCase):
    def test_open_ended_subjective_recommendation_requires_direction(self):
        contract = REQUEST.build_request_contract("맛있는 삼겹살 추천해 줘")
        obligations = REQUEST.build_evidence_obligations(contract)

        self.assertEqual("select", contract["requested_action"])
        self.assertEqual("open_set", contract["target_scope"]["kind"])
        self.assertEqual(1, contract["selection_count"])
        self.assertTrue(REQUEST.preference_question_if_needed(contract))
        self.assertIn("preference_resolution", {item["id"] for item in obligations})

    def test_explicit_quality_maximization_does_not_force_question(self):
        contract = REQUEST.build_request_contract("가장 맛있는 삼겹살 하나 추천해 줘")

        self.assertEqual("open_set", contract["target_scope"]["kind"])
        self.assertEqual("", REQUEST.preference_question_if_needed(contract))

    def test_multi_profile_request_already_resolves_tradeoff_shape(self):
        contract = REQUEST.build_request_contract("제품을 추천해 줘. 가성비픽 1, 품질픽 1")

        self.assertEqual("multi_profile", contract["selection_policy"]["mode"])
        self.assertEqual("", REQUEST.preference_question_if_needed(contract))

    def test_session_asks_before_spending_first_ai_action_and_reuses_action_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = VERIFIED.create_session(
                "맛있는 삼겹살 추천해 줘",
                output_root=Path(temp_dir),
                session_id="preference-gate-session",
            )

            self.assertEqual("awaiting_user_input", state["status"])
            self.assertEqual(0, state["budget"]["used_actions"])
            self.assertIsNone(state["current_action"])
            self.assertIn("무엇을 가장 우선", state["awaiting_user_question"])
            self.assertEqual(1, len(state["actions"]))

            state = VERIFIED.submit_user_input(
                session_dir,
                "가성비를 우선하되 너무 질기거나 잡내가 나는 제품은 싫어. 품질픽도 하나 같이 보여줘.",
            )
            public = VERIFIED.public_session(state, session_dir=session_dir)

            self.assertEqual("awaiting_execution", state["status"])
            self.assertEqual(0, state["budget"]["used_actions"])
            self.assertEqual(1, state["current_action"]["packet"]["action_number"])
            self.assertNotIn(
                "preference_resolution",
                {item["id"] for item in public["evidence_obligations"]},
            )
            self.assertIn("가성비를 우선", state["current_action"]["execution_prompt"])

    def test_bounded_comparison_does_not_force_preference_question(self):
        contract = REQUEST.build_request_contract("A와 B 둘 중 뭐가 더 나은지 비교해 줘")

        self.assertEqual("specified_or_bounded", contract["target_scope"]["kind"])
        self.assertEqual("", REQUEST.preference_question_if_needed(contract))


if __name__ == "__main__":
    unittest.main()
