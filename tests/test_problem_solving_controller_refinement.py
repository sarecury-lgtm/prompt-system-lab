import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_refinement as REFINEMENT
import problem_solving_controller_session as BASE
import problem_solving_controller_session_verified as VERIFIED
import problem_solving_evidence_verifier as VERIFIER


def completed_result(state, answer="기존 결과입니다."):
    packet = state["current_action"]["packet"]
    payload = {
        "version": 1,
        "session_id": state["session_id"],
        "action_id": packet["action_id"],
        "route": packet["route"],
        "status": "completed",
        "completion": {"met": True, "missing": []},
        "evidence": [],
        "coverage": VERIFIER.empty_coverage(),
        "artifacts": [],
        "limitations": [],
        "continuation": {
            "objective": "",
            "suggested_route": None,
            "changed_dimension": "none",
            "question": "",
        },
    }
    return (
        answer
        + "\n\n"
        + BASE.START_MARKER
        + "\n```json\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```\n"
        + BASE.END_MARKER
    )


class ControllerRefinementTests(unittest.TestCase):
    def test_terminal_result_reopens_from_user_reason_and_direction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = VERIFIED.create_session(
                "주어진 문장을 간단히 분석해 줘.",
                output_root=Path(temp_dir),
                session_id="user-refinement-session",
            )
            state = VERIFIED.submit_action_result(
                session_dir,
                completed_result(state),
            )
            self.assertEqual("completed", state["status"])
            self.assertEqual("기존 결과입니다.", state["best_answer"])
            before_changes = state["budget"]["used_method_changes"]

            state = REFINEMENT.submit_user_refinement(
                session_dir,
                reason="핵심은 맞지만 왜 그런지 설명이 약하다.",
                direction="기존 결론은 유지하고 원인과 반례를 더 분명하게 설명해 줘.",
            )

            self.assertEqual("awaiting_execution", state["status"])
            self.assertEqual("기존 결과입니다.", state["best_answer"])
            self.assertEqual(before_changes, state["budget"]["used_method_changes"])
            self.assertEqual(2, len(state["actions"]))
            self.assertEqual("interaction", state["current_action"]["packet"]["changed_dimension"])
            self.assertIn("원인과 반례", state["current_action"]["packet"]["objective"])
            self.assertIn("핵심은 맞지만", state["context"])
            self.assertIn("다음 방향", state["context"])
            self.assertIn(
                "기존 결과입니다.",
                state["current_action"]["packet"]["known_state"]["previous_answer"],
            )

            public = VERIFIED.public_session(state, session_dir=session_dir)
            context_constraints = [
                item["text"]
                for item in public["request_contract"]["user_constraints"]
                if item["source"] == "context"
            ]
            self.assertTrue(any("사용자 결과 피드백" in text for text in context_constraints))

    def test_refinement_requires_terminal_state_and_direction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, _state = VERIFIED.create_session(
                "주어진 문장을 분석해 줘.",
                output_root=Path(temp_dir),
                session_id="invalid-refinement-session",
            )
            with self.assertRaisesRegex(BASE.ControllerSessionError, "완료"):
                REFINEMENT.submit_user_refinement(
                    session_dir,
                    direction="다르게 설명해 줘.",
                )


if __name__ == "__main__":
    unittest.main()
