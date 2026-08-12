import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_session as SESSION


def raw_result(state, *, status="completed", met=True, missing=None, continuation=None, answer="final answer"):
    packet = state["current_action"]["packet"]
    payload = {
        "version": 1,
        "session_id": state["session_id"],
        "action_id": packet["action_id"],
        "route": packet["route"],
        "status": status,
        "completion": {"met": met, "missing": list(missing or [])},
        "evidence": [],
        "artifacts": [],
        "limitations": [],
        "continuation": {
            "objective": "",
            "suggested_route": None,
            "changed_dimension": "none",
            "question": "",
            **(continuation or {}),
        },
    }
    return (
        answer
        + "\n\n"
        + SESSION.START_MARKER
        + "\n```json\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n```\n"
        + SESSION.END_MARKER
    )


class ControllerSessionTests(unittest.TestCase):
    def create(self, root, request, session_id):
        session_dir, state = SESSION.create_session(
            request,
            output_root=Path(root),
            session_id=session_id,
        )
        return session_dir, state

    def test_direct_completion_stops_after_one_manual_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "주어진 댓글의 논리를 분석해 줘", "direct-session")
            self.assertEqual("DIRECT", state["current_action"]["packet"]["route"])

            state = SESSION.submit_action_result(session_dir, raw_result(state))

            self.assertEqual("completed", state["status"])
            self.assertEqual(1, state["budget"]["used_actions"])
            self.assertEqual(0, state["budget"]["used_method_changes"])
            self.assertEqual("final answer", (session_dir / "result.md").read_text(encoding="utf-8"))

    def test_research_gap_creates_new_same_route_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(
                temp_dir,
                "현재 Python 버전 중 무엇을 써야 하는지 조사해 줘",
                "research-session",
            )
            self.assertEqual("RESEARCH", state["current_action"]["packet"]["route"])
            state = SESSION.submit_action_result(
                session_dir,
                raw_result(
                    state,
                    status="partial",
                    met=False,
                    missing=["공식 지원 문서의 현재 확인 시점 필요"],
                    continuation={
                        "objective": "공식 지원 문서에서 현재 지원 상태를 확인한다.",
                        "suggested_route": "RESEARCH",
                        "changed_dimension": "information_source",
                    },
                    answer="partial research",
                ),
            )

            self.assertEqual("awaiting_execution", state["status"])
            self.assertEqual("RESEARCH", state["current_action"]["packet"]["route"])
            self.assertEqual(2, len(state["actions"]))
            self.assertEqual(0, state["budget"]["used_method_changes"])
            self.assertEqual("information_source", state["current_action"]["packet"]["changed_dimension"])

    def test_missing_current_evidence_changes_direct_to_research_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "이 주장의 타당성을 분석해 줘", "route-change")
            state = SESSION.submit_action_result(
                session_dir,
                raw_result(
                    state,
                    status="partial",
                    met=False,
                    missing=["최신 공식 근거와 출처 확인 필요"],
                    continuation={
                        "objective": "최신 공식 근거를 검색해 결론을 검증한다.",
                        "suggested_route": "RESEARCH",
                        "changed_dimension": "route",
                    },
                    answer="analysis without evidence",
                ),
            )

            self.assertEqual("RESEARCH", state["current_action"]["packet"]["route"])
            self.assertEqual(1, state["budget"]["used_method_changes"])
            self.assertEqual("route", state["current_action"]["packet"]["changed_dimension"])

    def test_duplicate_objective_is_stopped_as_honest_partial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "이 글을 요약해 줘", "duplicate-session")
            duplicate = state["current_action"]["packet"]["objective"]
            state = SESSION.submit_action_result(
                session_dir,
                raw_result(
                    state,
                    status="partial",
                    met=False,
                    missing=["요약이 아직 부족함"],
                    continuation={
                        "objective": duplicate,
                        "suggested_route": "DIRECT",
                        "changed_dimension": "interaction",
                    },
                    answer="partial summary",
                ),
            )

            self.assertEqual("partial", state["status"])
            self.assertIsNone(state["current_action"])
            self.assertTrue(any("objective" in item for item in state["limitations"]))

    def test_user_question_is_resumed_as_interaction_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "조건에 맞는 선택을 해 줘", "user-input-session")
            state = SESSION.submit_action_result(
                session_dir,
                raw_result(
                    state,
                    status="needs_user_input",
                    met=False,
                    missing=["예산 확인 필요"],
                    continuation={
                        "question": "최대 예산은 얼마인가요?",
                        "changed_dimension": "interaction",
                    },
                    answer="예산이 필요합니다.",
                ),
            )
            self.assertEqual("awaiting_user_input", state["status"])

            state = SESSION.submit_user_input(session_dir, "10만원")

            self.assertEqual("awaiting_execution", state["status"])
            self.assertEqual("interaction", state["current_action"]["packet"]["changed_dimension"])
            self.assertTrue(any("10만원" in item for item in state["goal"]["fixed_constraints"]))

    def test_session_persists_and_public_view_hides_full_action_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "현재 정책을 확인해 줘", "persist-session")
            loaded = SESSION.load_session(session_dir)
            public = SESSION.public_session(loaded)

            self.assertEqual(state["session_id"], loaded["session_id"])
            self.assertIn("execution_prompt", public["current_action"])
            self.assertNotIn("answer", public["actions"][0])
            self.assertTrue((session_dir / SESSION.STATE_FILENAME).is_file())
            self.assertTrue((session_dir / "current_action_prompt.txt").is_file())

    def test_missing_action_result_stops_without_pretending_completion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = self.create(temp_dir, "설명해 줘", "missing-envelope")
            state = SESSION.submit_action_result(session_dir, "구조화 결과가 없는 일반 답변")

            self.assertEqual("partial", state["status"])
            self.assertTrue(any("Action Result" in item for item in state["limitations"]))


if __name__ == "__main__":
    unittest.main()
