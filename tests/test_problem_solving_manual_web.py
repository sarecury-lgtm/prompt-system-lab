import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_manual", MODULE_PATH)
MANUAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MANUAL
SPEC.loader.exec_module(MANUAL)


def route_result(route="DIRECT", *, primary=None, secondary=None):
    reason = f"{route}가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과 확보",
            "current_goal_hypothesis": "요청을 그대로 해결",
            "fixed_constraints": ["요청 범위를 바꾸지 않음"],
            "current_position": "첫 실행",
            "selected_route": route,
            "secondary_route": secondary,
            "route_reason": reason,
            "current_step": "가장 가까운 결과 생성",
            "why_this_step_matters": "계획이 아니라 실제 결과가 필요함",
            "completion_condition": "사용 가능한 결과가 생성됨",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": route,
            "primary_route": primary,
            "secondary_route": secondary,
            "route_reason": reason,
        },
    }


def execution_result(*, result="실제로 생성된 결과입니다.", artifacts=None):
    return {
        "execution": {
            "status": "completed",
            "summary": "결과 생성",
            "result_markdown": result,
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": artifacts or [],
            "evidence": [],
            "limitations": [],
        }
    }


class ManualBridgeTests(unittest.TestCase):
    def test_parse_response_accepts_json_fence(self):
        payload, normalized = MANUAL.parse_response('```json\n{"ok": true}\n```')
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(json.loads(normalized), payload)

    def test_start_writes_pending_router_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(MANUAL.problem_os, "make_run_id", return_value="manual-start"):
                session = bridge.start("요청을 해결해줘")
            self.assertEqual(session["state"], "awaiting_router")
            self.assertIn("반환 계약: router", session["prompt"])
            self.assertTrue((runs / "manual-start" / "manual-handoff.json").is_file())
            self.assertTrue((runs / "manual-start" / "request.txt").is_file())

    def test_direct_run_resumes_and_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(MANUAL.problem_os, "make_run_id", return_value="manual-direct"):
                bridge.start("직접 답변해줘")
            routed = bridge.submit("manual-direct", json.dumps(route_result(), ensure_ascii=False))
            self.assertEqual(routed["state"], "awaiting_primary")
            self.assertEqual(routed["route"], "DIRECT")
            finished = bridge.submit(
                "manual-direct",
                json.dumps(execution_result(result="완성된 답변"), ensure_ascii=False),
            )
            self.assertEqual(finished["state"], "completed")
            self.assertIn("완성된 답변", finished["result_markdown"])
            route_record = json.loads(
                (runs / "manual-direct" / "route.json").read_text(encoding="utf-8")
            )
            self.assertEqual(route_record["execution_status"], "completed")
            self.assertFalse(
                route_record["manual_bridge"]["independent_browser_tool_receipts"]
            )

    def test_manual_bridge_rejects_claimed_local_write(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(MANUAL.problem_os, "make_run_id", return_value="manual-write"):
                bridge.start("파일을 만들어줘")
            bridge.submit(
                "manual-write",
                json.dumps(route_result("CODE"), ensure_ascii=False),
            )
            payload = execution_result(
                artifacts=[
                    {
                        "path": "output.txt",
                        "action": "created",
                        "verification": "만들었다고 주장",
                    }
                ]
            )
            with self.assertRaises(MANUAL.ManualBridgeError):
                bridge.submit("manual-write", json.dumps(payload, ensure_ascii=False))
            session = bridge.get("manual-write")
            self.assertEqual(session["state"], "awaiting_primary")
            self.assertIn("쓰기 capability 없이", session["error"])

    def test_active_returns_latest_pending_run(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                side_effect=["manual-one", "manual-two"],
            ):
                bridge.start("첫 요청")
                bridge.start("둘째 요청")
            self.assertEqual(bridge.active()["run_id"], "manual-two")


if __name__ == "__main__":
    unittest.main()
