import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_session as BASE
import problem_solving_controller_session_verified as VERIFIED
import problem_solving_request_contract as REQUEST
import problem_solving_selection_profiles as PROFILES


class SelectionProfileTests(unittest.TestCase):
    def test_explicit_profiles_become_domain_neutral_winner_slots(self):
        contract = REQUEST.build_request_contract(
            "후보들을 비교해서 안정성픽 1, 속도픽 1을 골라 줘"
        )
        policy = contract["selection_policy"]
        obligations = REQUEST.build_evidence_obligations(contract)

        self.assertEqual("multi_profile", policy["mode"])
        self.assertEqual(["안정성", "속도"], [item["label"] for item in policy["profiles"]])
        self.assertEqual(2, contract["selection_count"])
        self.assertIn("profiled_selection", {item["id"] for item in obligations})
        self.assertEqual("generic", contract["domain_hint"])

    def test_context_can_add_profiles_without_rewriting_original_request(self):
        contract = REQUEST.build_request_contract(
            "후보를 추천해 줘",
            context="한 종합 1등으로 뭉개지 말고 가성비픽 1, 품질픽 1로 나눠 줘",
        )

        self.assertEqual("후보를 추천해 줘", contract["original_request"])
        self.assertEqual("multi_profile", contract["selection_policy"]["mode"])
        self.assertEqual("context", contract["selection_policy"]["source"])
        self.assertEqual(2, contract["selection_count"])

    def test_non_selection_request_does_not_gain_fake_profiles(self):
        contract = REQUEST.build_request_contract("이 댓글의 논리적 비약을 분석해 줘")
        obligations = REQUEST.build_evidence_obligations(contract)

        self.assertEqual("single_winner", contract["selection_policy"]["mode"])
        self.assertEqual([], contract["selection_policy"]["profiles"])
        self.assertNotIn("profiled_selection", {item["id"] for item in obligations})

    def test_profile_verifier_requires_every_requested_purpose(self):
        contract = REQUEST.build_request_contract(
            "후보를 추천해 줘. 가성비픽 1, 품질픽 1"
        )
        result = {
            "coverage": {
                "selection": {
                    "selected_ids": ["A", "B"],
                    "action": "Choose A for value and B for quality.",
                    "reason": "They win different purposes.",
                    "profile_winners": [
                        {
                            "profile_id": contract["selection_policy"]["profiles"][0]["id"],
                            "label": "가성비",
                            "selected_ids": ["A"],
                            "action": "Choose A.",
                            "reason": "Best value.",
                        }
                    ],
                }
            }
        }

        verdict = PROFILES.verify_result(contract, result)
        self.assertFalse(verdict["satisfied"])
        self.assertIn("품질", "\n".join(verdict["missing_conditions"]))

    def test_verified_session_accepts_two_purpose_specific_winners(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = VERIFIED.create_session(
                "제품 후보를 추천해 줘. 가성비픽 1, 품질픽 1",
                output_root=Path(temp_dir),
                session_id="profile-pass-session",
            )
            packet = state["current_action"]["packet"]
            profiles = packet["request_contract"]["selection_policy"]["profiles"]
            evidence = [{"id": "screen", "source": "candidate list"}]
            result = {
                "version": 1,
                "session_id": state["session_id"],
                "action_id": packet["action_id"],
                "route": packet["route"],
                "status": "completed",
                "completion": {"met": True, "missing": []},
                "evidence": evidence,
                "coverage": {
                    "search_scope": {
                        "description": "Compared the supplied market candidates.",
                        "universe": "Relevant available products",
                        "screened_count": 3,
                        "filters": ["price", "quality"],
                        "finalist_ids": ["A", "B"],
                        "evidence_refs": ["screen"],
                    },
                    "comparison": {
                        "criteria": ["price", "quality"],
                        "candidate_ids": ["A", "B"],
                        "records": [
                            {"candidate_id": "A", "summary": "lower price, adequate quality"},
                            {"candidate_id": "B", "summary": "higher quality, higher price"},
                        ],
                    },
                    "selection": {
                        "selected_ids": ["A", "B"],
                        "selected_id": "A",
                        "action": "Use A for value and B for quality.",
                        "reason": "The tradeoff has two legitimate winners.",
                        "profile_winners": [
                            {
                                "profile_id": profiles[0]["id"],
                                "label": profiles[0]["label"],
                                "selected_ids": ["A"],
                                "action": "Choose A for the value purpose.",
                                "reason": "It clears the quality floor at the lowest price.",
                            },
                            {
                                "profile_id": profiles[1]["id"],
                                "label": profiles[1]["label"],
                                "selected_ids": ["B"],
                                "action": "Choose B for the quality purpose.",
                                "reason": "It provides the strongest quality evidence.",
                            },
                        ],
                    },
                    "assumptions": [],
                    "obligation_evidence": [],
                    "domain": {},
                },
                "artifacts": [],
                "limitations": [],
                "continuation": {
                    "objective": "",
                    "suggested_route": None,
                    "changed_dimension": "none",
                    "question": "",
                },
            }
            raw = (
                "A is the value winner and B is the quality winner."
                + "\n\n"
                + BASE.START_MARKER
                + "\n```json\n"
                + json.dumps(result, ensure_ascii=False)
                + "\n```\n"
                + BASE.END_MARKER
            )

            state = VERIFIED.submit_action_result(session_dir, raw)
            public = VERIFIED.public_session(state, session_dir=session_dir)

            self.assertTrue(public["last_verification"]["satisfied"], public["last_verification"])
            self.assertEqual("completed", state["status"])
            self.assertIn("profile_winners", packet["execution_prompt"])


if __name__ == "__main__":
    unittest.main()
