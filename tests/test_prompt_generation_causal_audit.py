import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_causal_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_causal_audit_test",
    MODULE_PATH,
)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)

from tests.test_prompt_generation_chart_case import make_chart_run  # noqa: E402


class PromptGenerationCausalAuditTests(unittest.TestCase):
    def test_chart_case_uses_parallel_branches_not_a_false_linear_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit = AUDIT.build_prompt_generation_causal_audit(
                make_chart_run(temp_dir)
            )

        self.assertEqual(
            [
                "parallel_transformation",
                "parallel_transformation",
                "model_generation",
            ],
            [edge["kind"] for edge in audit["topology"]["edges"]],
        )
        self.assertEqual(2, audit["convergence"]["exact_request_occurrences"])
        self.assertTrue(audit["convergence"]["contains_goal_ledger"])
        self.assertTrue(audit["convergence"]["contains_raw_request"])
        self.assertTrue(audit["convergence"]["contains_compiler_baseline"])

        codes = {item["code"] for item in audit["causal_findings"]}
        self.assertIn("parallel-branches-converge-uncompressed", codes)
        self.assertIn("raw-request-duplicated-at-convergence", codes)
        self.assertIn("baseline-embeds-request", codes)
        self.assertIn("executor-amplifies-converged-input", codes)
        self.assertIn("formatting-is-output-amplifier", codes)

    def test_causal_audit_reports_components_without_changing_the_prompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_chart_run(temp_dir)
            original = json.loads(
                (run_dir / "primary-prompt-output.json").read_text(encoding="utf-8")
            )["execution"]["result_markdown"]
            audit = AUDIT.build_prompt_generation_causal_audit(run_dir)
            record = AUDIT.write_prompt_generation_causal_audit(run_dir, audit)
            after = json.loads(
                (run_dir / "primary-prompt-output.json").read_text(encoding="utf-8")
            )["execution"]["result_markdown"]
            markdown = (run_dir / record["markdown_path"]).read_text(encoding="utf-8")

        self.assertEqual(original, after)
        self.assertIn("병렬 산출물", markdown)
        self.assertIn("동일한 원문 포함 횟수", markdown)
        self.assertGreater(record["finding_count"], 0)


if __name__ == "__main__":
    unittest.main()
