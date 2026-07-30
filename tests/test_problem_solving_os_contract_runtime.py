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


def compiled_contract(route="RESEARCH", *, detailed=True):
    outputs = [
        {
            "id": "goal-completion",
            "description": "사용 가능한 결과가 생성됨",
            "verification": "evidence" if route == "RESEARCH" else "text",
        }
    ]
    if detailed:
        outputs.extend(
            [
                {
                    "id": "target-identity",
                    "description": "각 최종 후보를 정확히 식별할 수 있음",
                    "verification": "evidence",
                },
                {
                    "id": "direct-target-url",
                    "description": "각 최종 후보의 직접 대상 URL이 있음",
                    "verification": "url",
                },
                {
                    "id": "current-state",
                    "description": "확인 시점의 상태와 비용 조건이 표시됨",
                    "verification": "evidence",
                },
                {
                    "id": "decision-evidence",
                    "description": "사용자 판단 기준별 근거가 후보에 연결됨",
                    "verification": "evidence",
                },
            ]
        )
    return {
        "version": 1,
        "route": route,
        "result_type": "research" if route == "RESEARCH" else "answer",
        "must_preserve": ["요청의 범위를 바꾸지 않음"],
        "required_outputs": outputs,
        "evidence_requirements": {
            "minimum_sources": 3 if detailed else 1,
            "source_roles": (
                ["current_target", "independent_fact", "user_experience"]
                if detailed
                else ["fact"]
            ),
            "claim_source_mapping": True,
        },
        "user_review": {
            "needed": detailed,
            "evidence_types": ["web"] if detailed else [],
        },
        "failure_policy": "no_winner" if detailed else "partial",
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.loads(json.dumps(response))

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

    def test_contract_prompt_is_domain_neutral_and_transaction_capable(self):
        prompt = RUNTIME.build_contract_prompt(
            "현재 구매 가능한 개별 대상을 비교해 줘.",
            route_result("RESEARCH"),
        )
        self.assertIn("직접 대상 URL", prompt)
        self.assertIn("시각 정보가 판단을 바꾸면", prompt)
        self.assertIn("실제 수정된 전체본", prompt)
        self.assertNotIn("복숭아", prompt)

    def test_research_contract_is_compiled_written_delivered_and_anchored(self):
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                compiled_contract("RESEARCH"),
                execution_result("RESEARCH"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "현재 구매 가능한 개별 대상을 비교해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="research-contract",
            )
            contract_path = run_dir / "result_contract.json"
            contract_exists = contract_path.is_file()
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()

        self.assertTrue(contract_exists)
        self.assertEqual("RESEARCH", contract["route"])
        self.assertIn(
            "direct-target-url",
            [item["id"] for item in contract["required_outputs"]],
        )
        self.assertEqual("contract", engine.calls[1]["invocation"].phase)
        self.assertIn("[Result Contract]", engine.calls[2]["prompt"])
        self.assertIn("direct-target-url", engine.calls[2]["prompt"])
        self.assertEqual(digest, route_record["result_contract"]["sha256"])
        self.assertEqual("model_compiled", payload["result_contract"]["generation"])
        self.assertEqual(
            "prompt_only_phase_a",
            payload["result_contract"]["enforcement"],
        )

    def test_invalid_compiled_contract_uses_second_profile(self):
        invalid = compiled_contract("RESEARCH")
        invalid["must_preserve"] = ["모델이 임의로 만든 제약"]
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                invalid,
                compiled_contract("RESEARCH"),
                execution_result("RESEARCH"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, payload = RUNTIME.run_request(
                "최근 사실을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="contract-fallback-profile",
            )

        trace = payload["result_contract"]["generation_trace"]
        self.assertEqual(4, len(engine.calls))
        self.assertEqual(["rejected", "accepted"], [item["outcome"] for item in trace])
        self.assertEqual("model_compiled", payload["result_contract"]["generation"])

    def test_two_invalid_contracts_fall_back_to_minimal_contract(self):
        invalid_one = compiled_contract("RESEARCH")
        invalid_one["route"] = "DIRECT"
        invalid_one["result_type"] = "answer"
        invalid_two = compiled_contract("RESEARCH")
        invalid_two["required_outputs"][0]["description"] = "다른 완료 조건"
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                invalid_one,
                invalid_two,
                execution_result("RESEARCH"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "최근 사실을 조사해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="minimal-contract-fallback",
            )
            contract = json.loads(
                (run_dir / "result_contract.json").read_text(encoding="utf-8")
            )

        self.assertEqual("minimal_fallback", payload["result_contract"]["generation"])
        self.assertEqual(
            ["goal-completion"],
            [item["id"] for item in contract["required_outputs"]],
        )
        self.assertIn("[Result Contract]", engine.calls[3]["prompt"])

    def test_simple_direct_keeps_existing_flow_without_contract_compiler(self):
        engine = FakeEngine([route_result("DIRECT"), execution_result("DIRECT")])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "캐시가 무엇인지 설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="simple-direct",
            )
            contract_exists = (run_dir / "result_contract.json").exists()
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )

        self.assertEqual(2, len(engine.calls))
        self.assertFalse(contract_exists)
        self.assertNotIn("[Result Contract]", engine.calls[1]["prompt"])
        self.assertNotIn("result_contract", payload)
        self.assertNotIn("result_contract", route_record)

    def test_invalid_first_router_attempt_does_not_create_stale_contract(self):
        engine = FakeEngine(
            [
                {},
                route_result("RESEARCH"),
                compiled_contract("RESEARCH", detailed=False),
                execution_result("RESEARCH"),
            ]
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

        self.assertEqual(4, len(engine.calls))
        self.assertEqual("RESEARCH", contract["route"])
        self.assertEqual("contract", engine.calls[2]["invocation"].phase)
        self.assertIn("[Result Contract]", engine.calls[3]["prompt"])


if __name__ == "__main__":
    unittest.main()
