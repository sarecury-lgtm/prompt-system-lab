import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import problem_solving_feedback as FEEDBACK
import problem_solving_policy_proposal as PROPOSAL
import problem_solving_review as REVIEW


MODULE_PATH = SCRIPTS_DIR / "problem_solving_policy_evaluation.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_policy_evaluation",
    MODULE_PATH,
)
EVALUATION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = EVALUATION
SPEC.loader.exec_module(EVALUATION)


class ProblemSolvingPolicyEvaluationTests(unittest.TestCase):
    def make_policy(self, root: Path) -> tuple[Path, dict]:
        policy = {
            "version": 1,
            "router": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "low",
                "web_search": False,
                "sandbox": "read-only",
            },
            "router_fallback": {
                "model": "gpt-5.6-sol",
                "reasoning_effort": "medium",
                "web_search": False,
                "sandbox": "read-only",
            },
            "routes": {
                "REUSE": {
                    "primary": {
                        "model": "gpt-5.6-terra",
                        "reasoning_effort": "medium",
                        "web_search": False,
                        "sandbox": "read-only",
                    },
                    "fallback": {
                        "model": "gpt-5.6-sol",
                        "reasoning_effort": "medium",
                        "web_search": False,
                        "sandbox": "read-only",
                    },
                }
            },
        }
        path = root / "model-policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        return path, policy

    def make_run(
        self,
        runs_root: Path,
        run_id: str,
        request: str,
        result: str,
        policy: dict,
        *,
        route: str = "REUSE",
        status: str = "completed",
    ) -> Path:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.txt").write_text(request, encoding="utf-8")
        (run_dir / "goal_ledger.json").write_text(
            json.dumps({"parent_goal": f"goal for {run_id}"}),
            encoding="utf-8",
        )
        (run_dir / "result.md").write_text(result, encoding="utf-8")
        (run_dir / "route.json").write_text(
            json.dumps(
                {
                    "selected_route": route,
                    "execution_status": status,
                    "run": {
                        "run_id": run_id,
                        "model_policy": policy,
                    },
                }
            ),
            encoding="utf-8",
        )
        return run_dir

    def promote_training_run(
        self,
        runs_root: Path,
        run_id: str,
        policy: dict,
    ) -> str:
        self.make_run(
            runs_root,
            run_id,
            f"training request {run_id}",
            f"training result {run_id}",
            policy,
        )
        _, learning, _ = FEEDBACK.record_feedback(
            run_id,
            "execution_succeeded",
            f"The training execution for {run_id} completed successfully.",
            [f"receipt for {run_id} verified"],
            runs_root=runs_root,
        )
        event_id = learning["events"][0]["event_id"]
        REVIEW.record_review(
            run_id,
            event_id,
            "promote",
            "owner",
            f"The evidence for {run_id} supports policy evaluation.",
            [f"manually reviewed evidence for {run_id}"],
            runs_root=runs_root,
        )
        return event_id

    def setup_evaluation(self, root: Path):
        runs_root = root / "runs"
        policy_path, baseline_policy = self.make_policy(root)
        first = self.promote_training_run(
            runs_root,
            "training-001",
            baseline_policy,
        )
        second = self.promote_training_run(
            runs_root,
            "training-002",
            baseline_policy,
        )
        proposal_path, proposal_record, _ = PROPOSAL.build_proposal(
            "Increase reviewed REUSE reasoning effort",
            "routes.REUSE.primary.reasoning_effort",
            "high",
            "Two independent reviewed executions support paired evaluation.",
            [("training-001", first), ("training-002", second)],
            runs_root=runs_root,
            policy_path=policy_path,
            output_dir=root / "proposals",
        )
        candidate_policy = copy.deepcopy(baseline_policy)
        candidate_policy["routes"]["REUSE"]["primary"][
            "reasoning_effort"
        ] = "high"
        return (
            runs_root,
            proposal_path,
            proposal_record,
            baseline_policy,
            candidate_policy,
        )

    def make_judgments(
        self,
        root: Path,
        proposal_record: dict,
        baseline_policy: dict,
        candidate_policy: dict,
        runs_root: Path,
        judgments: list[str] | None = None,
        *,
        candidate_statuses: list[str] | None = None,
    ) -> Path:
        judgments = judgments or [
            "candidate_better",
            "equivalent",
            "equivalent",
        ]
        candidate_statuses = candidate_statuses or ["completed"] * len(judgments)
        cases = []
        for index, judgment in enumerate(judgments, start=1):
            case_id = f"case-{index:03d}"
            request = f"fixed request {index}"
            baseline_id = f"baseline-{index:03d}"
            candidate_id = f"candidate-{index:03d}"
            self.make_run(
                runs_root,
                baseline_id,
                request,
                f"baseline result {index}",
                baseline_policy,
            )
            candidate_result = (
                f"candidate result {index}"
                if judgment == "candidate_better"
                else f"baseline result {index}"
            )
            self.make_run(
                runs_root,
                candidate_id,
                request,
                candidate_result,
                candidate_policy,
                status=candidate_statuses[index - 1],
            )
            cases.append(
                {
                    "case_id": case_id,
                    "baseline_run_id": baseline_id,
                    "candidate_run_id": candidate_id,
                    "judgment": judgment,
                    "evidence": [
                        f"manually compared fixed request outputs for {case_id}"
                    ],
                }
            )
        path = root / "judgments.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "proposal_id": proposal_record["proposal_id"],
                    "evaluator": "owner",
                    "cases": cases,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_passes_three_cases_with_improvement_and_no_regression(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (
                runs_root,
                proposal_path,
                proposal_record,
                baseline_policy,
                candidate_policy,
            ) = self.setup_evaluation(root)
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline_policy,
                candidate_policy,
                runs_root,
            )

            path, record, created = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(created)
        self.assertEqual(record, saved)
        self.assertEqual("passed", saved["status"])
        self.assertEqual(3, saved["summary"]["case_count"])
        self.assertEqual(1, saved["summary"]["candidate_better"])
        self.assertEqual([], saved["gate"]["failures"])
        self.assertFalse(saved["gate"]["automatic_application_allowed"])
        self.assertFalse(saved["gate"]["policy_applied"])

    def test_identical_evaluation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
            )

            _, first, first_created = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )
            _, second, second_created = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)

    def test_quality_regression_records_failed_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
                ["candidate_better", "candidate_worse", "equivalent"],
            )

            _, record, _ = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )

        self.assertEqual("failed", record["status"])
        self.assertIn("quality_regression:case-002", record["gate"]["failures"])

    def test_no_improvement_records_failed_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
                ["equivalent", "equivalent", "equivalent"],
            )

            _, record, _ = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )

        self.assertEqual("failed", record["status"])
        self.assertIn(
            "no_demonstrated_quality_improvement",
            record["gate"]["failures"],
        )

    def test_candidate_execution_failure_records_failed_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
                candidate_statuses=["completed", "blocked", "completed"],
            )

            _, record, _ = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )

        self.assertEqual("failed", record["status"])
        self.assertIn(
            "candidate_not_completed:case-002",
            record["gate"]["failures"],
        )

    def test_two_cases_are_recorded_as_insufficient(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
                ["candidate_better", "equivalent"],
            )

            _, record, _ = EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgments,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )

        self.assertEqual("failed", record["status"])
        self.assertIn("requires_at_least_3_cases", record["gate"]["failures"])

    def test_candidate_run_must_embed_candidate_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                baseline,
                runs_root,
            )

            with self.assertRaises(EVALUATION.EvaluationError):
                EVALUATION.evaluate_policy_proposal(
                    proposal_path,
                    judgments,
                    runs_root=runs_root,
                    output_dir=root / "evaluations",
                )

    def test_paired_requests_must_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
            )
            (runs_root / "candidate-002" / "request.txt").write_text(
                "different request",
                encoding="utf-8",
            )

            with self.assertRaises(EVALUATION.EvaluationError):
                EVALUATION.evaluate_policy_proposal(
                    proposal_path,
                    judgments,
                    runs_root=runs_root,
                    output_dir=root / "evaluations",
                )

    def test_training_runs_cannot_be_reused_for_evaluation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
            )
            payload = json.loads(judgments.read_text(encoding="utf-8"))
            payload["cases"][0]["baseline_run_id"] = "training-001"
            judgments.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(EVALUATION.EvaluationError):
                EVALUATION.evaluate_policy_proposal(
                    proposal_path,
                    judgments,
                    runs_root=runs_root,
                    output_dir=root / "evaluations",
                )

    def test_stale_policy_hash_rejects_evaluation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, proposal_path, proposal_record, baseline, candidate = setup
            judgments = self.make_judgments(
                root,
                proposal_record,
                baseline,
                candidate,
                runs_root,
            )
            policy_path = Path(proposal_record["target"]["policy_path"])
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["router"]["reasoning_effort"] = "medium"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            with self.assertRaises(EVALUATION.EvaluationError):
                EVALUATION.evaluate_policy_proposal(
                    proposal_path,
                    judgments,
                    runs_root=runs_root,
                    output_dir=root / "evaluations",
                )


if __name__ == "__main__":
    unittest.main()
