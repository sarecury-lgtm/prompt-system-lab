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
import problem_solving_policy_evaluation as EVALUATION
import problem_solving_policy_proposal as PROPOSAL
import problem_solving_review as REVIEW


MODULE_PATH = SCRIPTS_DIR / "problem_solving_policy_change.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_policy_change",
    MODULE_PATH,
)
CHANGE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CHANGE
SPEC.loader.exec_module(CHANGE)


class ProblemSolvingPolicyChangeTests(unittest.TestCase):
    def make_policy(self, root: Path) -> tuple[Path, dict]:
        policy = json.loads(
            (
                ROOT / "problem-solving-project" / "model-policy.json"
            ).read_text(encoding="utf-8")
        )
        path = root / "model-policy.json"
        path.write_text(
            json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path, policy

    def make_run(
        self,
        runs_root: Path,
        run_id: str,
        request: str,
        result: str,
        policy: dict,
        *,
        status: str = "completed",
    ) -> None:
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
                    "selected_route": "REUSE",
                    "execution_status": status,
                    "run": {
                        "run_id": run_id,
                        "model_policy": policy,
                    },
                }
            ),
            encoding="utf-8",
        )

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
            f"The evidence for {run_id} supports a policy proposal.",
            [f"manually reviewed evidence for {run_id}"],
            runs_root=runs_root,
        )
        return event_id

    def setup_evaluation(
        self,
        root: Path,
        *,
        proposed_value: str = "high",
        judgments: list[str] | None = None,
    ):
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
            proposed_value,
            "Two independent outcomes support held-out policy evaluation.",
            [("training-001", first), ("training-002", second)],
            runs_root=runs_root,
            policy_path=policy_path,
            output_dir=root / "proposals",
        )
        candidate_policy = copy.deepcopy(baseline_policy)
        candidate_policy["routes"]["REUSE"]["primary"][
            "reasoning_effort"
        ] = proposed_value
        judgments = judgments or [
            "candidate_better",
            "equivalent",
            "equivalent",
        ]
        cases = []
        for index, judgment in enumerate(judgments, start=1):
            baseline_id = f"baseline-{index:03d}"
            candidate_id = f"candidate-{index:03d}"
            request = f"fixed evaluation request {index}"
            baseline_result = f"baseline result {index}"
            candidate_result = (
                f"candidate improvement {index}"
                if judgment == "candidate_better"
                else baseline_result
            )
            self.make_run(
                runs_root,
                baseline_id,
                request,
                baseline_result,
                baseline_policy,
            )
            self.make_run(
                runs_root,
                candidate_id,
                request,
                candidate_result,
                candidate_policy,
            )
            cases.append(
                {
                    "case_id": f"case-{index:03d}",
                    "baseline_run_id": baseline_id,
                    "candidate_run_id": candidate_id,
                    "judgment": judgment,
                    "evidence": [
                        f"manually compared paired outputs for case {index}"
                    ],
                }
            )
        judgment_path = root / "judgments.json"
        judgment_path.write_text(
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
        evaluation_path, evaluation_record, _ = (
            EVALUATION.evaluate_policy_proposal(
                proposal_path,
                judgment_path,
                runs_root=runs_root,
                output_dir=root / "evaluations",
            )
        )
        return (
            runs_root,
            policy_path,
            proposal_path,
            evaluation_path,
            evaluation_record,
            baseline_policy,
            candidate_policy,
        )

    def approve(self, root: Path, setup):
        runs_root, _, proposal_path, evaluation_path, _, _, _ = setup
        return CHANGE.approve_policy_change(
            proposal_path,
            evaluation_path,
            "repository-owner",
            "The held-out evaluation passed without a quality regression.",
            ["reviewed the proposal and all paired evaluation cases"],
            runs_root=runs_root,
            output_dir=root / "approvals",
        )

    def test_approval_is_idempotent_and_does_not_change_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            policy_path = setup[1]
            before = FEEDBACK.file_sha256(policy_path)

            path, first, first_created = self.approve(root, setup)
            _, second, second_created = self.approve(root, setup)
            after = FEEDBACK.file_sha256(policy_path)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)
        self.assertEqual(path.name, f"{first['approval_id']}.json")
        self.assertFalse(first["safeguards"]["policy_applied"])
        self.assertEqual(before, after)

    def test_failed_evaluation_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(
                root,
                judgments=[
                    "candidate_better",
                    "candidate_worse",
                    "equivalent",
                ],
            )

            with self.assertRaises(CHANGE.PolicyChangeError):
                self.approve(root, setup)

    def test_invalid_candidate_policy_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(
                root,
                proposed_value="unsupported-effort",
            )

            with self.assertRaises(CHANGE.PolicyChangeError):
                self.approve(root, setup)

    def test_apply_creates_backup_receipt_and_changes_only_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            before = json.loads(policy_path.read_text(encoding="utf-8"))

            receipt_path, receipt, changed = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )
            after = json.loads(policy_path.read_text(encoding="utf-8"))
            backup = receipt_path.parent / f"{receipt['change_id']}.before.json"
            backup_exists = backup.is_file()
            backup_sha256 = (
                FEEDBACK.file_sha256(backup) if backup_exists else None
            )

        self.assertTrue(changed)
        self.assertEqual("applied", receipt["status"])
        self.assertEqual(
            "high",
            after["routes"]["REUSE"]["primary"]["reasoning_effort"],
        )
        after["routes"]["REUSE"]["primary"]["reasoning_effort"] = "medium"
        self.assertEqual(before, after)
        self.assertTrue(backup_exists)
        self.assertEqual(receipt["before_sha256"], backup_sha256)

    def test_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            arguments = {
                "runs_root": runs_root,
                "changes_dir": root / "changes",
            }

            _, first, first_changed = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                **arguments,
            )
            _, second, second_changed = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                **arguments,
            )

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(first, second)

    def test_prepared_receipt_recovers_after_policy_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            receipt_path, receipt, _ = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )
            receipt["status"] = "prepared"
            receipt["applied_at"] = None
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            _, recovered, changed = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )

        self.assertTrue(changed)
        self.assertEqual("applied", recovered["status"])

    def test_wrong_explicit_policy_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            approval_path, _, _ = self.approve(root, setup)
            wrong_path = root / "wrong-policy.json"
            wrong_path.write_text("{}", encoding="utf-8")

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.apply_policy_change(
                    approval_path,
                    wrong_path,
                    runs_root=setup[0],
                    changes_dir=root / "changes",
                )

    def test_active_policy_change_after_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["router"]["reasoning_effort"] = "medium"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.apply_policy_change(
                    approval_path,
                    policy_path,
                    runs_root=runs_root,
                    changes_dir=root / "changes",
                )

    def test_missing_active_policy_after_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            policy_path.unlink()

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.apply_policy_change(
                    approval_path,
                    policy_path,
                    runs_root=runs_root,
                    changes_dir=root / "changes",
                )

    def test_tampered_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            approval_path, approval, _ = self.approve(root, setup)
            approval["reason"] = "tampered approval"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.apply_policy_change(
                    approval_path,
                    setup[1],
                    runs_root=setup[0],
                    changes_dir=root / "changes",
                )

    def test_rollback_restores_policy_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            before = policy_path.read_bytes()
            approval_path, _, _ = self.approve(root, setup)
            receipt_path, _, _ = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )

            _, first, first_changed = CHANGE.rollback_policy_change(
                receipt_path,
                policy_path,
                runs_root=runs_root,
            )
            _, second, second_changed = CHANGE.rollback_policy_change(
                receipt_path,
                policy_path,
                runs_root=runs_root,
            )
            restored = policy_path.read_bytes()

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual("rolled_back", first["status"])
        self.assertEqual(first, second)
        self.assertEqual(before, restored)

    def test_rollback_refuses_unrelated_post_apply_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            receipt_path, _, _ = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["router"]["reasoning_effort"] = "medium"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.rollback_policy_change(
                    receipt_path,
                    policy_path,
                    runs_root=runs_root,
                )

    def test_tampered_receipt_is_rejected_before_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup = self.setup_evaluation(root)
            runs_root, policy_path = setup[0], setup[1]
            approval_path, _, _ = self.approve(root, setup)
            receipt_path, receipt, _ = CHANGE.apply_policy_change(
                approval_path,
                policy_path,
                runs_root=runs_root,
                changes_dir=root / "changes",
            )
            receipt["after_sha256"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            with self.assertRaises(CHANGE.PolicyChangeError):
                CHANGE.rollback_policy_change(
                    receipt_path,
                    policy_path,
                    runs_root=runs_root,
                )


if __name__ == "__main__":
    unittest.main()
