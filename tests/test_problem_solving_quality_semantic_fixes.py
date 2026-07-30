import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_os_quality_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "psos_quality_semantic_test_runtime", MODULE_PATH
)
QUALITY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = QUALITY
SPEC.loader.exec_module(QUALITY)
OS = QUALITY.OS
CONTRACT = QUALITY.CONTRACT_RUNTIME.CONTRACT
ENFORCEMENT = QUALITY.CONTRACT_RUNTIME.ENFORCEMENT
EVIDENCE = QUALITY.EVIDENCE


def route_payload(route="PROMPT"):
    return {
        "goal_ledger": {
            "parent_goal": "재사용 결과 만들기",
            "current_goal_hypothesis": "재사용 프롬프트를 만든다.",
            "fixed_constraints": [],
            "current_position": "시작",
            "selected_route": route,
            "secondary_route": None,
            "route_reason": "프롬프트 자체가 산출물이다.",
            "current_step": "최종 프롬프트를 만든다.",
            "why_this_step_matters": "반복 사용이 목적이다.",
            "completion_condition": "바로 복사할 프롬프트가 완성된다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": route,
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "프롬프트 자체가 산출물이다.",
        },
    }


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def capabilities(self):
        return OS.EngineCapabilities(True, True, True, False, "fixture")

    def execute(self, prompt, run_dir, invocation):
        self.calls.append(invocation)
        if not self.responses:
            raise AssertionError("unexpected model call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.loads(json.dumps(response))

    def trace(self):
        return [
            {"name": call.name, "phase": call.phase, "route": call.route}
            for call in self.calls
        ]


class QualitySemanticFixTests(unittest.TestCase):
    def test_result_contract_accepts_empty_preserved_constraints(self):
        payload = {
            "version": 1,
            "route": "PROMPT",
            "result_type": "reusable_prompt",
            "must_preserve": [],
            "required_outputs": [
                {
                    "id": "goal-completion",
                    "description": "프롬프트 완성",
                    "verification": "text",
                }
            ],
            "evidence_requirements": {
                "minimum_sources": 0,
                "source_roles": [],
                "claim_source_mapping": False,
            },
            "user_review": {"needed": False, "evidence_types": []},
            "failure_policy": "partial",
        }
        self.assertEqual(
            CONTRACT.validate_result_contract(payload)["must_preserve"], []
        )

    def test_assessment_rejects_invented_evidence_reference(self):
        contract = {
            "required_outputs": [
                {
                    "id": "direct-url",
                    "description": "직접 URL",
                    "verification": "url",
                }
            ],
            "evidence_requirements": {
                "minimum_sources": 1,
                "source_roles": ["target"],
                "claim_source_mapping": True,
            },
        }
        execution = {
            "result_markdown": "후보",
            "evidence": [
                {
                    "source": "https://example.test/item",
                    "finding": "대상",
                    "kind": "web",
                }
            ],
            "artifacts": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            observations = ENFORCEMENT.collect_observations(
                Path(directory), execution
            )
        assessment = {
            "version": 1,
            "contract_sha256": "a" * 64,
            "overall_status": "satisfied",
            "requirements": [
                {
                    "id": "direct-url",
                    "status": "satisfied",
                    "finding": "URL 확인",
                    "evidence_refs": ["evidence:999"],
                }
            ],
            "evidence_check": {
                "status": "satisfied",
                "finding": "출처 연결",
            },
            "missing_requirement_ids": [],
            "missing_conditions": [],
        }
        with self.assertRaises(ENFORCEMENT.ContractEnforcementError):
            ENFORCEMENT.validate_assessment(
                assessment, contract, "a" * 64, observations
            )

    def test_missing_requirement_does_not_show_unrelated_fallback_evidence(self):
        contract = {
            "required_outputs": [
                {
                    "id": "direct-url",
                    "description": "직접 URL",
                    "verification": "url",
                }
            ],
            "user_review": {"needed": False, "evidence_types": []},
        }
        assessment = {
            "requirements": [
                {
                    "id": "direct-url",
                    "status": "missing",
                    "finding": "직접 URL 부족",
                    "evidence_refs": [],
                }
            ]
        }
        execution = {
            "status": "partial",
            "result_markdown": "참고 링크 https://example.test/general",
            "evidence": [],
            "artifacts": [],
        }
        ledger = {
            "current_goal_hypothesis": "결과",
            "parent_goal": "결과",
        }
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "result.md").write_text("결과", encoding="utf-8")
            bundle = EVIDENCE.build_evidence_bundle(
                run_dir,
                "결과",
                ledger,
                contract,
                "b" * 64,
                execution,
                assessment,
            )
        self.assertEqual(bundle["requirements"][0]["evidence_item_ids"], [])

    def test_workspace_relative_local_evidence_gets_integrity_hash(self):
        contract = {
            "required_outputs": [
                {
                    "id": "asset",
                    "description": "자산",
                    "verification": "evidence",
                }
            ],
            "user_review": {"needed": False, "evidence_types": []},
        }
        ledger = {
            "current_goal_hypothesis": "자산 검토",
            "parent_goal": "자산 검토",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            run_dir = root / "runs" / "one"
            workspace.mkdir()
            run_dir.mkdir(parents=True)
            (run_dir / "result.md").write_text("결과", encoding="utf-8")
            (workspace / "asset.txt").write_text("verified", encoding="utf-8")
            engine = type("Engine", (), {"workspace": workspace})()
            QUALITY.QUALITY_FIXES.set_workspace_root(EVIDENCE, engine)
            execution = {
                "status": "completed",
                "result_markdown": "자산 검토",
                "evidence": [
                    {
                        "source": "asset.txt",
                        "finding": "읽은 자산",
                        "kind": "local",
                    }
                ],
                "artifacts": [],
            }
            bundle = EVIDENCE.build_evidence_bundle(
                run_dir,
                "자산 검토",
                ledger,
                contract,
                "c" * 64,
                execution,
                None,
            )
        local = next(
            item for item in bundle["items"] if item["source"] == "asset.txt"
        )
        self.assertIsNotNone(local["integrity"]["sha256"])

    def test_post_router_failure_preserves_accepted_goal_and_route(self):
        engine = FakeEngine([route_payload("PROMPT")])
        policy = OS.load_model_policy()
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            OS,
            "prepare_prompt_compiler_baseline",
            side_effect=OS.ProblemSolvingError("compiler failed"),
        ):
            _run_dir, payload = QUALITY.CONTRACT_RUNTIME.run_request(
                "재사용 프롬프트를 만들어줘",
                output_root=Path(directory),
                engine=engine,
                model_policy=policy,
                run_id="preserve-route",
            )
        self.assertEqual(payload["route"]["selected_route"], "PROMPT")
        self.assertEqual(payload["goal_ledger"]["fixed_constraints"], [])
        self.assertEqual(
            payload["execution"]["status"], "blocked_by_capability"
        )
        self.assertIn("실행 중 오류", payload["execution"]["result_markdown"])


if __name__ == "__main__":
    unittest.main()
