import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_contract_enforcement.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_contract_enforcement",
    MODULE_PATH,
)
ENFORCEMENT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ENFORCEMENT
SPEC.loader.exec_module(ENFORCEMENT)


def contract(*, failure_policy="partial", verification="url", minimum_sources=1):
    return {
        "version": 1,
        "route": "RESEARCH",
        "result_type": "research",
        "must_preserve": ["조건 보존"],
        "required_outputs": [
            {
                "id": "goal-completion",
                "description": "사용 가능한 결과",
                "verification": "text",
            },
            {
                "id": "required-target",
                "description": "직접 대상 근거",
                "verification": verification,
            },
        ],
        "evidence_requirements": {
            "minimum_sources": minimum_sources,
            "source_roles": ["fact"] if minimum_sources else [],
            "claim_source_mapping": minimum_sources > 0,
        },
        "user_review": {"needed": False, "evidence_types": []},
        "failure_policy": failure_policy,
    }


def execution(*, url=False):
    source = "https://example.test/item" if url else "주소 없는 자료"
    return {
        "status": "completed",
        "summary": "결과",
        "result_markdown": "후보 A 추천"
        + ("\nhttps://example.test/item" if url else ""),
        "capabilities_used": [],
        "needed_capability": None,
        "handoff": None,
        "artifacts": [],
        "evidence": [
            {
                "source": source,
                "finding": "현재 상태 확인",
                "kind": "web",
            }
        ],
        "limitations": [],
    }


def assessment_payload(contract_sha, *, satisfied=True):
    status = "satisfied" if satisfied else "missing"
    return {
        "version": 1,
        "contract_sha256": contract_sha,
        "overall_status": status,
        "requirements": [
            {
                "id": "goal-completion",
                "status": "satisfied",
                "finding": "결과 본문 확인",
                "evidence_refs": ["result_markdown"],
            },
            {
                "id": "required-target",
                "status": status,
                "finding": "직접 대상 확인" if satisfied else "직접 대상 누락",
                "evidence_refs": ["result_markdown"] if satisfied else [],
            },
        ],
        "evidence_check": {
            "status": "satisfied",
            "finding": "출처 확인",
        },
        "missing_requirement_ids": [] if satisfied else ["required-target"],
        "missing_conditions": [] if satisfied else ["직접 대상 누락"],
    }


class ContractEnforcementTests(unittest.TestCase):
    def test_observations_collect_urls_artifacts_visuals_and_receipts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "primary-workspace-receipt.json").write_text(
                json.dumps({"verified": True}),
                encoding="utf-8",
            )
            current = execution(url=True)
            current["result_markdown"] += (
                "\n![후기 사진](https://example.test/photo.jpg)"
            )
            current["artifacts"] = [
                {
                    "path": "result.txt",
                    "action": "created",
                    "verification": "fixture",
                }
            ]
            observations = ENFORCEMENT.collect_observations(run_dir, current)

        self.assertGreaterEqual(observations["url_count"], 2)
        self.assertEqual(1, observations["evidence_source_count"])
        self.assertEqual(["result.txt"], observations["artifact_paths"])
        self.assertEqual(
            ["primary-workspace-receipt.json"],
            observations["verified_receipts"],
        )
        self.assertEqual(1, observations["visual_reference_count"])

    def test_url_hard_gate_overrides_false_satisfied_claim(self):
        current_contract = contract()
        current_execution = execution(url=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            observations = ENFORCEMENT.collect_observations(
                Path(temp_dir),
                current_execution,
            )
        validated = ENFORCEMENT.validate_assessment(
            assessment_payload("a" * 64, satisfied=True),
            current_contract,
            "a" * 64,
            observations,
        )

        self.assertEqual("missing", validated["overall_status"])
        self.assertIn("required-target", validated["missing_requirement_ids"])
        target = next(
            item
            for item in validated["requirements"]
            if item["id"] == "required-target"
        )
        self.assertEqual("missing", target["status"])
        self.assertIn("URL", target["finding"])

    def test_minimum_source_count_is_enforced_mechanically(self):
        current_contract = contract(verification="text", minimum_sources=2)
        current_execution = execution(url=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            observations = ENFORCEMENT.collect_observations(
                Path(temp_dir),
                current_execution,
            )
        validated = ENFORCEMENT.validate_assessment(
            assessment_payload("b" * 64, satisfied=True),
            current_contract,
            "b" * 64,
            observations,
        )

        self.assertEqual("missing", validated["overall_status"])
        self.assertEqual("missing", validated["evidence_check"]["status"])
        self.assertIn("2개", validated["evidence_check"]["finding"])

    def test_no_winner_policy_removes_unverified_winner(self):
        current_contract = contract(failure_policy="no_winner")
        current_assessment = {
            "missing_requirement_ids": ["required-target"],
            "missing_conditions": ["직접 URL 누락"],
        }
        result = ENFORCEMENT.apply_failure_policy(
            execution(url=False),
            current_contract,
            current_assessment,
        )

        self.assertEqual("partial", result["status"])
        self.assertNotIn("후보 A 추천", result["result_markdown"])
        self.assertIn("확정할 수 없습니다", result["result_markdown"])

    def test_deterministic_fallback_never_marks_semantic_text_satisfied(self):
        current_contract = contract(verification="text", minimum_sources=0)
        current_execution = execution(url=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            observations = ENFORCEMENT.collect_observations(
                Path(temp_dir),
                current_execution,
            )
        result = ENFORCEMENT.deterministic_fallback_assessment(
            current_contract,
            "c" * 64,
            observations,
            "assessment failed",
        )

        self.assertEqual("missing", result["overall_status"])
        self.assertTrue(
            all(item["status"] != "satisfied" for item in result["requirements"])
        )
        self.assertIn("assessment failed", result["missing_conditions"])


if __name__ == "__main__":
    unittest.main()
