import hashlib
import importlib.util
import json
import re
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


def route_result(route="DIRECT", *, primary=None, secondary=None):
    reason = f"{route}가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "사용자의 실제 결과 확보",
            "current_goal_hypothesis": "요청을 그대로 해결",
            "fixed_constraints": ["요청의 범위를 바꾸지 않음"],
            "current_position": "첫 실행",
            "selected_route": route,
            "secondary_route": secondary,
            "route_reason": reason,
            "current_step": "가장 가까운 결과 생성",
            "why_this_step_matters": "계획이 아니라 실제 결과가 필요함",
            "completion_condition": "사용 가능한 결과가 생성됨",
            "important_uncertainties": [] if route == "DIRECT" else ["최신 사실"],
        },
        "route": {
            "selected_route": route,
            "primary_route": primary,
            "secondary_route": secondary,
            "route_reason": reason,
        },
    }


def compiled_contract(route="RESEARCH", *, failure_policy=None, detailed=True):
    result_types = {
        "DIRECT": "answer",
        "RESEARCH": "research",
        "REUSE": "asset_reuse",
        "PROMPT": "reusable_prompt",
        "CODE": "code_change",
        "PROJECT": "project_step",
        "HYBRID": "hybrid",
    }
    outputs = [
        {
            "id": "goal-completion",
            "description": "사용 가능한 결과가 생성됨",
            "verification": "text",
        }
    ]
    evidence = {
        "minimum_sources": 0,
        "source_roles": [],
        "claim_source_mapping": False,
    }
    review = {"needed": False, "evidence_types": []}
    if route == "RESEARCH" and detailed:
        outputs.extend(
            [
                {
                    "id": "direct-target-url",
                    "description": "직접 대상 URL이 있음",
                    "verification": "url",
                },
                {
                    "id": "current-state",
                    "description": "현재 상태가 근거와 연결됨",
                    "verification": "evidence",
                },
            ]
        )
        evidence = {
            "minimum_sources": 1,
            "source_roles": ["current_listing"],
            "claim_source_mapping": True,
        }
    if route in {"CODE", "PROJECT"}:
        outputs.append(
            {
                "id": "verified-change",
                "description": "실제 변경 receipt가 검증됨",
                "verification": "receipt",
            }
        )
    return {
        "version": 1,
        "route": route,
        "result_type": result_types[route],
        "must_preserve": ["요청의 범위를 바꾸지 않음"],
        "required_outputs": outputs,
        "evidence_requirements": evidence,
        "user_review": review,
        "failure_policy": failure_policy
        or (
            "no_winner"
            if route == "RESEARCH"
            else "blocked" if route in {"CODE", "PROJECT"} else "partial"
        ),
    }


def execution_result(
    route="DIRECT",
    *,
    result="실제로 생성된 결과입니다.",
    url=False,
    status="completed",
    artifacts=None,
):
    evidence = []
    if route == "RESEARCH":
        source = (
            "https://example.test/listing"
            if url
            else "판매 페이지를 확인했지만 주소 누락"
        )
        evidence = [
            {
                "source": source,
                "finding": "현재 사실 확인",
                "kind": "web",
            }
        ]
    return {
        "execution": {
            "status": status,
            "summary": "결과 생성",
            "result_markdown": result
            + ("\n\nhttps://example.test/listing" if url else ""),
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": artifacts or [],
            "evidence": evidence,
            "limitations": [],
        }
    }


def _hash_from_prompt(prompt):
    match = re.search(r"\[Result Contract SHA-256\]\n([a-f0-9]{64})", prompt)
    if not match:
        raise AssertionError("assessment prompt has no contract hash")
    return match.group(1)


def assessment_response(statuses, *, evidence_status="satisfied"):
    def build(prompt, _run_dir, _invocation):
        contract_match = re.search(
            r"\[Result Contract\]\n(\{.*?\})\n\n\[실행 결과\]",
            prompt,
            re.S,
        )
        if not contract_match:
            raise AssertionError("assessment prompt has no contract")
        contract = json.loads(contract_match.group(1))
        requirements = []
        missing = []
        conditions = []
        for item in contract["required_outputs"]:
            status = statuses.get(item["id"], "satisfied")
            finding = (
                "결과에서 확인됨"
                if status == "satisfied"
                else f"{item['description']}이 부족함"
            )
            refs = ["result_markdown"] if status == "satisfied" else []
            requirements.append(
                {
                    "id": item["id"],
                    "status": status,
                    "finding": finding,
                    "evidence_refs": refs,
                }
            )
            if status != "satisfied":
                missing.append(item["id"])
                conditions.append(finding)
        return {
            "version": 1,
            "contract_sha256": _hash_from_prompt(prompt),
            "overall_status": (
                "satisfied"
                if not missing and evidence_status == "satisfied"
                else "missing"
            ),
            "requirements": requirements,
            "evidence_check": {
                "status": evidence_status,
                "finding": (
                    "출처 요구 충족"
                    if evidence_status == "satisfied"
                    else "출처 요구 부족"
                ),
            },
            "missing_requirement_ids": missing,
            "missing_conditions": conditions,
        }

    return build


class FakeEngine:
    def __init__(self, responses, capabilities=None):
        self.responses = list(responses)
        self.calls = []
        self._capabilities = capabilities or OS.EngineCapabilities(
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
        if callable(response):
            response = response(prompt, run_dir, invocation)
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

    def test_collection_contract_preserves_verified_partial_results(self):
        routed = route_result("RESEARCH")
        routed["goal_ledger"]["fixed_constraints"] = ["서로 다른 상품 최소 5개"]
        routed["goal_ledger"]["completion_condition"] = (
            "검증된 상품 최소 5개를 제시한다."
        )
        contract = compiled_contract("RESEARCH", failure_policy="no_winner")
        contract["must_preserve"] = ["서로 다른 상품 최소 5개"]
        contract["required_outputs"][0]["description"] = (
            "검증된 상품 최소 5개를 제시한다."
        )

        validated = RUNTIME.validate_compiled_contract(contract, routed)

        self.assertEqual("partial", validated["failure_policy"])

    def test_satisfied_research_is_validated_and_anchored(self):
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                compiled_contract("RESEARCH"),
                execution_result("RESEARCH", url=True),
                assessment_response({}),
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
            assessment_exists = (run_dir / "result_contract_assessment.json").is_file()
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()

        self.assertTrue(assessment_exists)
        self.assertEqual("completed", payload["execution"]["status"])
        self.assertEqual("validated_phase_b", payload["result_contract"]["enforcement"])
        self.assertEqual(
            "satisfied_initially",
            payload["result_contract"]["validation"]["outcome"],
        )
        self.assertEqual(digest, route_record["result_contract"]["sha256"])
        self.assertEqual(
            ["router", "contract", "executor", "assessment"],
            [call["invocation"].phase for call in engine.calls],
        )

    def test_current_purchase_state_requires_live_browser(self):
        routed = route_result("RESEARCH")
        routed["goal_ledger"]["fixed_constraints"] = ["현재 구매 가능해야 함"]
        routed["goal_ledger"]["completion_condition"] = (
            "현재 구매 가능한 상품을 제시한다."
        )
        contract = compiled_contract("RESEARCH", failure_policy="partial")
        contract["must_preserve"] = ["현재 구매 가능해야 함"]
        contract["required_outputs"][0]["description"] = (
            "현재 구매 가능한 상품을 제시한다."
        )
        contract["required_outputs"][2]["description"] = (
            "현재 판매 상태를 직접 검증한다."
        )
        engine = FakeEngine(
            [
                routed,
                contract,
                execution_result("RESEARCH", url=True),
                assessment_response({}),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, payload = RUNTIME.run_request(
                "현재 구매 가능한 상품을 찾아 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="live-browser-required",
            )

        validation = payload["result_contract"]["validation"]
        self.assertFalse(validation["repair_attempted"])
        self.assertEqual("downgraded_without_repair", validation["outcome"])
        self.assertEqual("partial", payload["execution"]["status"])
        self.assertIn("실시간 브라우저", payload["execution"]["result_markdown"])

    def test_missing_url_is_repaired_once_and_revalidated(self):
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                compiled_contract("RESEARCH"),
                execution_result("RESEARCH", result="후보 A를 추천합니다.", url=False),
                assessment_response({}),
                execution_result("RESEARCH", result="후보 A를 추천합니다.", url=True),
                assessment_response({}),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = RUNTIME.run_request(
                "현재 구매 가능한 개별 대상을 비교해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="repair-success",
            )
            original_exists = (
                run_dir / "result_contract_original_execution.json"
            ).is_file()
            after_exists = (
                run_dir / "result_contract_assessment-after-repair.json"
            ).is_file()

        validation = payload["result_contract"]["validation"]
        self.assertTrue(original_exists)
        self.assertTrue(after_exists)
        self.assertTrue(validation["repair_attempted"])
        self.assertEqual("satisfied_after_repair", validation["outcome"])
        self.assertEqual("completed", payload["execution"]["status"])
        self.assertIn(
            "https://example.test/listing",
            payload["execution"]["result_markdown"],
        )
        self.assertEqual(
            ["router", "contract", "executor", "assessment", "repair", "assessment"],
            [call["invocation"].phase for call in engine.calls],
        )

    def test_partial_research_is_assessed_and_repaired(self):
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                compiled_contract("RESEARCH"),
                execution_result(
                    "RESEARCH",
                    result="조사가 부족합니다.",
                    url=False,
                    status="partial",
                ),
                assessment_response({"direct-target-url": "missing"}),
                execution_result("RESEARCH", result="후보 A를 확인했습니다.", url=True),
                assessment_response({}),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, payload = RUNTIME.run_request(
                "현재 구매 가능한 개별 대상을 비교해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="repair-partial-research",
            )

        validation = payload["result_contract"]["validation"]
        self.assertTrue(validation["repair_attempted"])
        self.assertEqual("satisfied_after_repair", validation["outcome"])
        self.assertEqual("completed", payload["execution"]["status"])
        self.assertEqual(
            ["router", "contract", "executor", "assessment", "repair", "assessment"],
            [call["invocation"].phase for call in engine.calls],
        )

    def test_failed_repair_uses_no_winner_policy(self):
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                compiled_contract("RESEARCH", failure_policy="no_winner"),
                execution_result(
                    "RESEARCH",
                    result="후보 A가 확실한 우승자입니다.",
                    url=False,
                ),
                assessment_response({}),
                execution_result(
                    "RESEARCH",
                    result="후보 A가 확실한 우승자입니다.",
                    url=False,
                ),
                assessment_response({}),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, payload = RUNTIME.run_request(
                "현재 구매 가능한 개별 대상을 비교해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="repair-no-winner",
            )

        self.assertEqual("partial", payload["execution"]["status"])
        self.assertNotIn("확실한 우승자", payload["execution"]["result_markdown"])
        self.assertIn("확정할 수 없습니다", payload["execution"]["result_markdown"])
        self.assertEqual(
            "downgraded_after_repair",
            payload["result_contract"]["validation"]["outcome"],
        )

    def test_code_contract_is_downgraded_without_second_write_attempt(self):
        capabilities = OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=True,
            detail="fixture",
        )
        engine = FakeEngine(
            [
                route_result("CODE"),
                compiled_contract("CODE", failure_policy="blocked"),
                execution_result(
                    "CODE",
                    artifacts=[
                        {
                            "path": "answer.txt",
                            "action": "generated_in_result",
                            "verification": "코드 제시",
                        }
                    ],
                ),
                assessment_response({}),
            ],
            capabilities=capabilities,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, payload = RUNTIME.run_request(
                "파일을 수정해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="code-no-repair",
            )

        validation = payload["result_contract"]["validation"]
        self.assertFalse(validation["repair_allowed"])
        self.assertFalse(validation["repair_attempted"])
        self.assertEqual("blocked_by_capability", payload["execution"]["status"])
        self.assertEqual(4, len(engine.calls))

    def test_invalid_compiled_contract_uses_second_profile(self):
        invalid = compiled_contract("RESEARCH")
        invalid["must_preserve"] = ["모델이 임의로 만든 제약"]
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                invalid,
                compiled_contract("RESEARCH"),
                execution_result("RESEARCH", url=True),
                assessment_response({}),
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
                execution_result("RESEARCH", url=False),
                assessment_response({}),
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
        self.assertEqual("completed", payload["execution"]["status"])

    def test_simple_direct_keeps_existing_flow_without_contract_or_assessment(self):
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
        self.assertNotIn("result_contract", payload)
        self.assertNotIn("result_contract", route_record)


if __name__ == "__main__":
    unittest.main()
