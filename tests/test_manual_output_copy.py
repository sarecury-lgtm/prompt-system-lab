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
            "parent_goal": "재사용 프롬프트 만들기",
            "current_goal_hypothesis": "최종 프롬프트를 만든다.",
            "fixed_constraints": [],
            "current_position": "시작",
            "selected_route": "PROMPT",
            "secondary_route": None,
            "route_reason": "프롬프트 자체가 산출물이다.",
            "current_step": "최종 프롬프트를 만든다.",
            "why_this_step_matters": "반복 사용이 목적이다.",
            "completion_condition": "복사 가능한 프롬프트가 완성된다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": "PROMPT",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "프롬프트 자체가 산출물이다.",
        },
    }


def execution_result():
    return {
        "execution": {
            "status": "completed",
            "summary": "프롬프트 완성",
            "result_markdown": "# 실제 복사할 프롬프트\n\n차트만 분석한다.",
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
                bridge.start("차트 분석 프롬프트를 만들어줘", research_mode="none")
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
                "# 실제 복사할 프롬프트\n\n차트만 분석한다.\n",
            )
            self.assertIn("현재 목표:", session["result_markdown"])
            self.assertTrue((runs / "output-copy" / "output.md").is_file())
            self.assertTrue((runs / "output-copy" / "result.md").is_file())


if __name__ == "__main__":
    unittest.main()
