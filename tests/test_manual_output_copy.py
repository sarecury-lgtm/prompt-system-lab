import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual_web.py"
SPEC = importlib.util.spec_from_file_location("manual_output_copy_test_web", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


def route_result():
    return {
        "goal_ledger": {
            "parent_goal": "사용 가능한 답변 만들기",
            "current_goal_hypothesis": "최종 답변을 만든다.",
            "fixed_constraints": [],
            "current_position": "시작",
            "selected_route": "DIRECT",
            "secondary_route": None,
            "route_reason": "추가 조사 없이 바로 답할 수 있다.",
            "current_step": "최종 답변을 만든다.",
            "why_this_step_matters": "사용자가 답변을 필요로 한다.",
            "completion_condition": "복사 가능한 답변이 완성된다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": "DIRECT",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "추가 조사 없이 바로 답할 수 있다.",
        },
    }


def execution_result():
    return {
        "execution": {
            "status": "completed",
            "summary": "답변 완성",
            "result_markdown": "# 실제 복사할 결과\n\n차트만 분석한다.",
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [],
            "limitations": [],
        }
    }


class ManualOutputCopyTests(unittest.TestCase):
    def test_public_session_exposes_actual_output_separately_from_audit_result(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = WEB.deep_manual.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                WEB.problem_os,
                "make_run_id",
                return_value="output-copy",
            ):
                bridge.start("짧은 답변을 만들어줘", research_mode="none")
            bridge.submit(
                "output-copy",
                json.dumps(route_result(), ensure_ascii=False),
            )
            session = bridge.submit(
                "output-copy",
                json.dumps(execution_result(), ensure_ascii=False),
            )

            self.assertEqual(
                session["output_markdown"],
                "# 실제 복사할 결과\n\n차트만 분석한다.\n",
            )
            self.assertIn("현재 목표:", session["result_markdown"])
            self.assertTrue((runs / "output-copy" / "output.md").is_file())
            self.assertTrue((runs / "output-copy" / "result.md").is_file())


if __name__ == "__main__":
    unittest.main()
