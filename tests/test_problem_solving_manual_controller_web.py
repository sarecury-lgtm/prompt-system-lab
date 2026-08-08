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
import problem_solving_evidence_verifier as VERIFIER
import problem_solving_manual_controller_web as WEB


def completed_answer(public_state):
    packet = public_state["current_action"]["packet"]
    payload = {
        "version": 1,
        "session_id": public_state["session_id"],
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
        "usable result\n\n"
        + SESSION.START_MARKER
        + "\n```json\n"
        + json.dumps(payload)
        + "\n```\n"
        + SESSION.END_MARKER
    )


class ManualControllerWebTests(unittest.TestCase):
    def test_manager_creates_reads_completes_and_refines_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WEB.ManualControllerManager(Path(temp_dir))
            created = manager.create({"request": "주어진 글을 분석해 줘"})
            loaded = manager.get(created["session_id"])
            completed = manager.submit_result(
                created["session_id"],
                {"answer": completed_answer(created)},
            )
            refined = manager.submit_refinement(
                created["session_id"],
                {
                    "reason": "결론은 맞지만 이유가 약하다.",
                    "direction": "결론은 유지하고 반례와 이유를 보강해 줘.",
                },
            )

            self.assertEqual(created["session_id"], loaded["session_id"])
            self.assertEqual("completed", completed["status"])
            self.assertEqual("usable result", completed["display_data"]["result_markdown"])
            self.assertTrue(completed["last_verification"]["satisfied"])
            self.assertEqual("awaiting_execution", refined["status"])
            self.assertIn("반례와 이유", refined["current_action"]["packet"]["objective"])
            self.assertEqual(0, refined["budget"]["used_method_changes"])
            self.assertIn("request_contract", created)
            self.assertIn("evidence_obligations", created)

    def test_manager_rejects_unsafe_session_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = WEB.ManualControllerManager(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "session_id"):
                manager.get("../outside")

    def test_install_wraps_current_handler_and_returns_manager(self):
        class BaseHandler:
            pass

        class DummyWeb:
            ROOT = Path(tempfile.gettempdir()) / "psos-manual-controller-web-test"
            NextLoopQualityRequestHandler = BaseHandler

        manager = WEB.install(DummyWeb)
        self.assertIsInstance(manager, WEB.ManualControllerManager)
        self.assertTrue(issubclass(DummyWeb.NextLoopQualityRequestHandler, BaseHandler))
        self.assertEqual("PSOSManualControllerWeb/3", DummyWeb.NextLoopQualityRequestHandler.server_version)

    def test_script_exposes_session_result_input_and_refine_endpoints(self):
        source = (SCRIPTS / "problem_solving_manual_controller_web.py").read_text(encoding="utf-8")
        for marker in (
            "/api/manual-controller/sessions",
            'action == "result"',
            'action == "input"',
            'action == "refine"',
            "SESSION.submit_action_result",
            "SESSION.submit_user_input",
            "REFINEMENT.submit_user_refinement",
            "problem_solving_controller_session_verified",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
