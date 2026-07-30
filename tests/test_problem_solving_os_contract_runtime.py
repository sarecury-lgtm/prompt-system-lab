import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_os_contract_runtime.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_os_contract_runtime", MODULE_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)
OS = RUNTIME.OS


def route_result(route="DIRECT"):
    reason = f"{route}가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과 확보",
            "current_goal_hypothesis": "요청을 그대로 해결",
            "fixed_constraints": ["요청의 범위를 바꾸지 않음"],
            "current_position": "첫 실행",
            "selected_route": route,
            "secondary_route": None,
            "route_reason": reason,
            "current_step": "가장 가까운 결과 생성",
            "why_this_step_matters": "계획이 아니라 실제 결과가 필요함",
            "completion_condition": "사용 가능한 결과가 생성됨",
            "important_uncertainties": [] if route == "DIRECT" else ["최신 사실"],
        },
        "route": {
            "selected_route": route,
            "primary_route": None,
            "secondary_route": None,
            "route_reason": reason,
        },
    }


def execution_result(route="DIRECT"):
    evidence = []
    if route == "RESEARCH":
        evidence = [
            {
                "source": "https://example.test/source",
                "finding": "현재 사실 확인",
                "kind": "web",
            }
        ]
    return {
        "execution": {
            "status": "completed",
            "summary": "결과 생성",
            "result_markdown": "실제로 생성된 결과입니다.",
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": evidence,
            "limitations": [],
        }
    }


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self._capabilities = OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fixture",
        )

    def capabilities(self):
        return self._capabilities

    def execute(self, prompt, run_dir, invocation):
        self.calls.append({"prompt": prompt, "invocation": invocation})
        return json.loads(json.dumps(self.responses.pop(0)))

    def trace(self):
        return [
            {
                "name": call["invocation"].name,
                "phase": call["invocation"].phase,
                "route": call["invocation"].route,
            }
            for call in self.calls
        ]


class ContractRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy = OS.load_model_policy()

    def test_research_contract_is_written_delivered_and_anchored(self):
        engine = FakeEngine([route_result("RESEARCH"), execution_result("RESEARCH")])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "현재 사실을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="research-contract",
            )
            contract_path = run_dir / "result_contract.json"
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()

        self.assertTrue(contract_path.is_file())
        self.assertEqual("RESEARCH", contract["route"])
        self.assertEqual("research", contract["result_type"])
        self.assertIn("[Result Contract]", engine.calls[1]["prompt"])
        self.assertIn("사용 가능한 결과가 생성됨", engine.calls[1]["prompt"])
        self.assertEqual(digest, route_record["result_contract"]["sha256"])
        self.assertEqual(
            "prompt_only_phase_a",
            payload["result_contract"]["enforcement"],
        )
        self.assertTrue(payload["result_contract"]["delivered_to_executor"])

    def test_simple_direct_keeps_existing_flow_without_contract(self):
        engine = FakeEngine([route_result("DIRECT"), execution_result("DIRECT")])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "캐시가 무엇인지 설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="simple-direct",
            )
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )

        self.assertFalse((run_dir / "result_contract.json").exists())
        self.assertNotIn("[Result Contract]", engine.calls[1]["prompt"])
        self.assertNotIn("result_contract", payload)
        self.assertNotIn("result_contract", route_record)

    def test_invalid_first_router_attempt_does_not_create_stale_contract(self):
        engine = FakeEngine(
            [{}, route_result("RESEARCH"), execution_result("RESEARCH")]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, _payload = RUNTIME.run_request(
                "최근 사실을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="router-fallback-contract",
            )
            contract = json.loads(
                (run_dir / "result_contract.json").read_text(encoding="utf-8")
            )

        self.assertEqual(3, len(engine.calls))
        self.assertEqual("RESEARCH", contract["route"])
        self.assertIn("[Result Contract]", engine.calls[2]["prompt"])


if __name__ == "__main__":
    unittest.main()
