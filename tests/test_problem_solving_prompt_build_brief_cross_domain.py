import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_build_brief.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "prompt-build-brief-cross-domain.json"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_build_brief_cross_domain",
    MODULE_PATH,
)
BRIEF = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = BRIEF
SPEC.loader.exec_module(BRIEF)

from tests.test_problem_solving_os_contract_runtime import OS  # noqa: E402


class PromptBuildBriefCrossDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.cases = cls.fixture["cases"]
        cls.profile = OS.load_model_policy()["routes"]["PROMPT"]["primary"]
        cls.capabilities = OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="cross-domain fixture",
        )

    def test_fixture_briefs_preserve_each_domain_without_cross_contamination(self):
        contamination_markers = {
            "chart-decision": ["상대 댓글 원문", "현재 판매 상태"],
            "comment-reply": ["피보나치", "현재 판매 후보"],
            "product-research": ["손절 위험", "상대 댓글의 실제 주장"],
        }
        procedure_sets = []

        for case in self.cases:
            with self.subTest(case=case["id"]):
                ledger = case["ledger"]
                brief = BRIEF.validate_prompt_build_brief(case["brief"], ledger)
                baseline = {
                    "version": "0.1",
                    "request": case["request"],
                    "final_prompt": (
                        "[사용자 요청]\n"
                        + case["request"]
                        + "\n\n[수행 및 출력 규칙]\n- 목표와 조건을 보존한다."
                    ),
                }
                compiler_prompt = BRIEF.build_prompt_build_brief_prompt(
                    case["request"],
                    ledger,
                    baseline,
                    None,
                )
                invocation = OS.InvocationSpec(
                    name=f"cross-domain-{case['id']}",
                    phase="executor",
                    route="PROMPT",
                    profile=self.profile,
                    schema_path=OS.EXECUTION_SCHEMA_PATH,
                )
                executor_prompt = BRIEF.build_prompt_executor_from_brief(
                    brief,
                    invocation,
                    self.capabilities,
                    "",
                )

                self.assertIn(case["request"], compiler_prompt)
                self.assertNotIn(case["request"], executor_prompt)
                self.assertNotIn("[사용자 요청]", executor_prompt)
                self.assertNotIn("[Goal Ledger]", executor_prompt)
                self.assertNotIn(BRIEF.BASELINE_MARKER, executor_prompt)
                self.assertIn(BRIEF.BRIEF_MARKER, executor_prompt)
                self.assertIn(BRIEF.PROMPT_OUTPUT_START, executor_prompt)
                self.assertIn(BRIEF.PROMPT_OUTPUT_END, executor_prompt)
                for item in brief["core_procedure"]:
                    self.assertIn(item, executor_prompt)
                self.assertEqual(
                    ledger["fixed_constraints"],
                    brief["fixed_constraints"],
                )
                self.assertEqual(
                    ledger["completion_condition"],
                    brief["output_contract"][0],
                )
                for marker in contamination_markers[case["id"]]:
                    self.assertNotIn(marker, executor_prompt)
                procedure_sets.append(tuple(brief["core_procedure"]))

        self.assertEqual(len(procedure_sets), len(set(procedure_sets)))

    def test_explicit_constraints_are_not_dropped_by_an_arbitrary_count_limit(self):
        case = self.cases[0]
        ledger = dict(case["ledger"])
        ledger["fixed_constraints"] = [f"고정 조건 {index}" for index in range(1, 21)]
        brief = dict(case["brief"])
        brief["fixed_constraints"] = list(ledger["fixed_constraints"])

        validated = BRIEF.validate_prompt_build_brief(brief, ledger)

        self.assertEqual(20, len(validated["fixed_constraints"]))
        self.assertEqual(ledger["fixed_constraints"], validated["fixed_constraints"])


if __name__ == "__main__":
    unittest.main()
