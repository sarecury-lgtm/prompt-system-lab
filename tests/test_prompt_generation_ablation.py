import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_ablation.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_ablation_test",
    MODULE_PATH,
)
ABLATION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ABLATION
SPEC.loader.exec_module(ABLATION)

from tests.test_prompt_generation_chart_case import make_chart_run  # noqa: E402


class PromptGenerationAblationTests(unittest.TestCase):
    def test_chart_case_builds_four_controlled_executor_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment = ABLATION.build_prompt_ablation_variants(
                make_chart_run(temp_dir)
            )

        metadata = experiment["metadata"]
        self.assertEqual(
            {
                "current",
                "without_raw_request",
                "compact_ledger",
                "single_build_brief",
            },
            set(experiment["variants"]),
        )
        self.assertEqual(2, metadata["current"]["exact_request_occurrences"])
        self.assertEqual(
            1,
            metadata["without_raw_request"]["exact_request_occurrences"],
        )
        self.assertEqual(1, metadata["compact_ledger"]["exact_request_occurrences"])
        self.assertEqual(
            0,
            metadata["single_build_brief"]["exact_request_occurrences"],
        )
        self.assertLess(
            metadata["single_build_brief"]["characters"],
            metadata["current"]["characters"],
        )
        self.assertTrue(
            metadata["single_build_brief"]["contains_single_build_brief"]
        )
        self.assertFalse(
            metadata["single_build_brief"]["contains_full_goal_ledger"]
        )
        self.assertFalse(
            metadata["single_build_brief"]["contains_full_compiler_baseline"]
        )

    def test_ablation_files_do_not_modify_the_original_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_chart_run(temp_dir)
            output_path = run_dir / "primary-prompt-output.json"
            original = output_path.read_text(encoding="utf-8")
            experiment = ABLATION.build_prompt_ablation_variants(run_dir)
            record = ABLATION.write_prompt_ablation_variants(
                run_dir,
                experiment,
            )
            after = output_path.read_text(encoding="utf-8")
            manifest = json.loads(
                (run_dir / record["manifest_path"]).read_text(encoding="utf-8")
            )

        self.assertEqual(original, after)
        self.assertEqual(4, len(record["files"]))
        self.assertIn("experiment_contract", manifest)
        self.assertNotIn("variants", manifest)


if __name__ == "__main__":
    unittest.main()
