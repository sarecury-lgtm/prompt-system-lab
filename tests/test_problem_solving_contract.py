import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_contract.py"
SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-result-contract.schema.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "result-contract-cases.json"
SPEC = importlib.util.spec_from_file_location("problem_solving_contract", MODULE_PATH)
CONTRACT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CONTRACT
SPEC.loader.exec_module(CONTRACT)


class ResultContractTests(unittest.TestCase):
    def load_cases(self):
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def build_case(self, case):
        return CONTRACT.build_result_contract(
            case["route"],
            case["ledger"],
            additional_outputs=case.get("additional_outputs", []),
            evidence=case.get("evidence"),
            review=case.get("review"),
            failure_policy=case.get("failure_policy"),
        )

    def test_schema_and_dataclass_share_the_same_top_level_contract(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        expected = {
            "version",
            "route",
            "result_type",
            "must_preserve",
            "required_outputs",
            "evidence_requirements",
            "user_review",
            "failure_policy",
        }
        self.assertEqual(expected, set(schema["required"]))
        self.assertEqual(expected, set(CONTRACT.ResultContract.__dataclass_fields__))

    def test_all_representative_cases_build_and_validate(self):
        seen = set()
        for case in self.load_cases():
            with self.subTest(case=case["id"]):
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                contract = self.build_case(case)
                expected = case["expected"]
                if not expected["contract"]:
                    self.assertIsNone(contract)
                    continue
                self.assertIsNotNone(contract)
                payload = CONTRACT.validate_result_contract(contract.to_dict())
                self.assertEqual(expected["result_type"], payload["result_type"])
                self.assertGreaterEqual(
                    len(payload["required_outputs"]),
                    expected["minimum_outputs"],
                )
                self.assertEqual(
                    case["ledger"]["fixed_constraints"],
                    payload["must_preserve"],
                )

    def test_simple_direct_is_not_forced_through_a_contract(self):
        case = next(
            item
            for item in self.load_cases()
            if item["id"] == "simple-direct-explanation"
        )
        self.assertIsNone(self.build_case(case))
        forced = CONTRACT.build_result_contract(
            case["route"],
            case["ledger"],
            skip_simple_direct=False,
        )
        self.assertEqual("answer", forced.result_type)
        self.assertEqual("text", forced.required_outputs[0].verification)

    def test_route_defaults_are_generic_and_research_requires_mapping(self):
        contract = CONTRACT.build_result_contract(
            "RESEARCH",
            {
                "fixed_constraints": ["원래 목적 보존"],
                "completion_condition": "근거가 연결된 결과 제공",
                "important_uncertainties": [],
            },
        )
        self.assertEqual(1, contract.evidence_requirements.minimum_sources)
        self.assertEqual(("fact",), contract.evidence_requirements.source_roles)
        self.assertTrue(contract.evidence_requirements.claim_source_mapping)
        self.assertEqual("evidence", contract.required_outputs[0].verification)

    def test_domain_requirements_are_declarative_not_keyword_rules(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("복숭아", source)
        self.assertNotIn("쿠팡", source)
        visual = next(
            item
            for item in self.load_cases()
            if item["id"] == "visual-evidence-decision"
        )
        contract = self.build_case(visual)
        self.assertTrue(contract.user_review.needed)
        self.assertIn("image", contract.user_review.evidence_types)
        self.assertIn(
            "visual",
            {item.verification for item in contract.required_outputs},
        )

    def test_duplicate_requirement_ids_are_rejected(self):
        ledger = {
            "fixed_constraints": ["목적 보존"],
            "completion_condition": "결과 제공",
            "important_uncertainties": [],
        }
        with self.assertRaises(CONTRACT.ResultContractError):
            CONTRACT.build_result_contract(
                "PROMPT",
                ledger,
                additional_outputs=[
                    {"id": "same", "description": "첫 항목", "verification": "text"},
                    {"id": "same", "description": "둘째 항목", "verification": "text"},
                ],
            )

    def test_user_review_requires_a_reviewable_evidence_type(self):
        ledger = {
            "fixed_constraints": ["목적 보존"],
            "completion_condition": "결과 제공",
            "important_uncertainties": [],
        }
        with self.assertRaises(CONTRACT.ResultContractError):
            CONTRACT.build_result_contract(
                "RESEARCH",
                ledger,
                review={"needed": True, "evidence_types": []},
            )

    def test_contract_is_written_atomically_and_round_trips(self):
        contract = CONTRACT.build_result_contract(
            "CODE",
            {
                "fixed_constraints": ["승인 범위 보존"],
                "completion_condition": "검증된 변경 제공",
                "important_uncertainties": ["재현 여부"],
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            destination = CONTRACT.write_result_contract(run_dir, contract)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            leftovers = list(run_dir.glob(".result-contract-*.tmp"))
        self.assertEqual(contract.to_dict(), payload)
        self.assertEqual([], leftovers)

    def test_cli_can_preview_a_contract_for_an_existing_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            run_dir.mkdir()
            (run_dir / "goal_ledger.json").write_text(
                json.dumps(
                    {
                        "fixed_constraints": ["최신 근거"],
                        "completion_condition": "근거가 있는 조사 결과 제공",
                        "important_uncertainties": ["현재 상태"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "route.json").write_text(
                json.dumps({"selected_route": "RESEARCH"}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(MODULE_PATH),
                    "--run-dir",
                    str(run_dir),
                ],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            contract_path = run_dir / "result_contract.json"
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertEqual("research", payload["result_type"])
        self.assertTrue(payload["evidence_requirements"]["claim_source_mapping"])


if __name__ == "__main__":
    unittest.main()
