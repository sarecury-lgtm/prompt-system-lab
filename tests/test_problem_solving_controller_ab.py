import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_ab as AB


class ControllerABTests(unittest.TestCase):
    def setUp(self):
        self.suite = AB.load_suite()

    def test_suite_preregisters_four_distinct_domains(self):
        self.assertEqual(4, len(self.suite["cases"]))
        self.assertEqual(4, len({case["domain"] for case in self.suite["cases"]}))
        self.assertEqual(
            ["direct-argument-analysis", "current-python-version-decision"],
            self.suite["pilot_policy"]["default_case_ids"],
        )

    def test_default_live_selection_is_bounded_to_two_cases(self):
        selected = AB.select_cases(
            self.suite,
            None,
            allow_more_cases=False,
        )
        self.assertEqual(2, len(selected))
        with self.assertRaisesRegex(AB.EvaluationError, "최대 2개"):
            AB.select_cases(
                self.suite,
                [case["id"] for case in self.suite["cases"]],
                allow_more_cases=False,
            )

    def test_prepare_writes_all_four_cases_without_live_results(self):
        selected = AB.select_cases(
            self.suite,
            [case["id"] for case in self.suite["cases"]],
            allow_more_cases=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "prepared"
            AB.prepare_experiment(self.suite, selected, output, seed=17)
            plan = json.loads((output / "experiment_plan.json").read_text(encoding="utf-8"))
            packet = json.loads((output / "blind_review_packet.json").read_text(encoding="utf-8"))
            self.assertFalse(plan["live_model_calls_started"])
            self.assertEqual(4, len(plan["case_ids"]))
            self.assertEqual("prepared_awaiting_live_results", packet["status"])
            self.assertTrue((output / "evaluation_report.md").is_file())
            self.assertFalse((output / "arm_key.json").exists())

    def test_blind_packet_hides_arm_identity(self):
        selected = self.suite["cases"][:1]
        case_id = selected[0]["id"]
        results = {
            case_id: {
                "baseline": {"result_markdown": "첫 번째 실제 답변"},
                "controller": {"result_markdown": "두 번째 실제 답변"},
            }
        }
        packet, key = AB.build_blind_packet(
            self.suite,
            selected,
            results,
            seed=99,
        )
        serialized = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn('"baseline"', serialized)
        self.assertNotIn('"controller"', serialized)
        self.assertEqual({"baseline", "controller"}, set(key["cases"][case_id].values()))
        self.assertEqual("ready_for_blind_review", packet["status"])

    def test_mocked_live_run_records_metrics_without_model_runtime(self):
        selected = AB.select_cases(self.suite, None, allow_more_cases=False)
        calls = []

        def fake_executor(case, arm, **kwargs):
            calls.append((case["id"], arm))
            return {
                "arm": arm,
                "result_markdown": f"{case['id']} {arm} output",
                "result_path": f"/{case['id']}/{arm}/result.md",
                "workspace": "/fake",
                "route": case["expected_primary_route"],
                "expected_route": case["expected_primary_route"],
                "expected_route_match": True,
                "execution_status": "completed",
                "outcome": "completed",
                "contract_status": "satisfied",
                "method_changes": 1 if arm == "controller" else 0,
                "attempt_count": 2 if arm == "controller" else 1,
                "elapsed_seconds": 2.0 if arm == "controller" else 1.0,
                "model_call_count": 4 if arm == "controller" else 2,
                "web_search_call_count": 0,
                "models": ["fake"],
                "trace_routes": [case["expected_primary_route"]],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "live"
            AB.run_live_experiment(
                self.suite,
                selected,
                output,
                seed=23,
                model_policy_path=Path("unused.json"),
                arm_executor=fake_executor,
            )
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            packet = json.loads((output / "blind_review_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(4, len(calls))
            self.assertEqual(2, metrics["cases"][selected[0]["id"]]["baseline"]["model_call_count"])
            self.assertEqual("ready_for_blind_review", packet["status"])
            self.assertTrue((output / "arm_key.json").is_file())

    def test_report_unblinds_only_after_complete_review(self):
        selected = self.suite["cases"][:1]

        def fake_executor(case, arm, **kwargs):
            return {
                "arm": arm,
                "result_markdown": f"{arm} result",
                "result_path": f"/{arm}/result.md",
                "workspace": "/fake",
                "route": case["expected_primary_route"],
                "expected_route": case["expected_primary_route"],
                "expected_route_match": True,
                "execution_status": "completed",
                "outcome": "completed",
                "contract_status": "satisfied",
                "method_changes": 0,
                "attempt_count": 1,
                "elapsed_seconds": 1.0,
                "model_call_count": 2,
                "web_search_call_count": 0,
                "models": ["fake"],
                "trace_routes": [case["expected_primary_route"]],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "live"
            AB.run_live_experiment(
                self.suite,
                selected,
                output,
                seed=1,
                model_policy_path=Path("unused.json"),
                arm_executor=fake_executor,
            )
            packet = json.loads((output / "blind_review_packet.json").read_text(encoding="utf-8"))
            criterion_ids = [item["id"] for item in packet["rubric"]["criteria"]]
            scores = {criterion_id: 3 for criterion_id in criterion_ids}
            response = {
                "version": 1,
                "reviews": [
                    {
                        "case_id": selected[0]["id"],
                        "scores": {"A": scores, "B": scores},
                        "winner": "A",
                        "critical_failures": {"A": [], "B": []},
                        "notes": "blind review complete",
                    }
                ],
            }
            review_path = output / "blind_review_response.json"
            review_path.write_text(json.dumps(response), encoding="utf-8")
            report_path = AB.generate_report(output, review_path)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("blind review completed and unblinded", report)
            self.assertIn("pilot evidence only", report)


if __name__ == "__main__":
    unittest.main()
