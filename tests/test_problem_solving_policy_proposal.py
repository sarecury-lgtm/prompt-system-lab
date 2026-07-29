import hashlib
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
import problem_solving_review as REVIEW


MODULE_PATH = SCRIPTS_DIR / "problem_solving_policy_proposal.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_policy_proposal",
    MODULE_PATH,
)
PROPOSAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = PROPOSAL
SPEC.loader.exec_module(PROPOSAL)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProblemSolvingPolicyProposalTests(unittest.TestCase):
    def make_promoted_run(
        self,
        runs_root: Path,
        run_id: str,
        *,
        route: str = "REUSE",
        result: str | None = None,
        decision: str = "promote",
    ) -> str:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.txt").write_text(
            f"request for {run_id}\n",
            encoding="utf-8",
        )
        (run_dir / "goal_ledger.json").write_text(
            json.dumps({"parent_goal": f"goal for {run_id}"}),
            encoding="utf-8",
        )
        (run_dir / "route.json").write_text(
            json.dumps(
                {
                    "selected_route": route,
                    "execution_status": "completed",
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "result.md").write_text(
            result or f"verified result for {run_id}\n",
            encoding="utf-8",
        )
        _, learning, _ = FEEDBACK.record_feedback(
            run_id,
            "execution_succeeded",
            f"The target execution for {run_id} completed successfully.",
            [f"receipt for {run_id} verified with zero issues"],
            runs_root=runs_root,
        )
        event_id = learning["events"][0]["event_id"]
        REVIEW.record_review(
            run_id,
            event_id,
            decision,
            "owner",
            f"The evidence for {run_id} supports this review decision.",
            [f"manually inspected receipt for {run_id}"],
            runs_root=runs_root,
        )
        return event_id

    def make_policy(self, root: Path) -> Path:
        policy_path = root / "model-policy.json"
        policy_path.write_text(
            json.dumps(
                {
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
            ),
            encoding="utf-8",
        )
        return policy_path

    def proposal_arguments(
        self,
        runs_root: Path,
        policy_path: Path,
        output_dir: Path,
        candidates: list[tuple[str, str]],
        *,
        target: str = "routes.REUSE.primary.reasoning_effort",
        proposed_value: object = "high",
    ):
        return (
            "Increase reviewed REUSE reasoning effort",
            target,
            proposed_value,
            "Two independent reviewed executions indicate the current setting is insufficient.",
            candidates,
        ), {
            "runs_root": runs_root,
            "policy_path": policy_path,
            "output_dir": output_dir,
        }

    def test_builds_draft_from_two_independent_promoted_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")
            policy_path = self.make_policy(root)
            policy_before = sha256(policy_path)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
            )

            path, proposal, created = PROPOSAL.build_proposal(*args, **kwargs)
            policy_after = sha256(policy_path)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(created)
        self.assertEqual(proposal, saved)
        self.assertEqual("draft", saved["status"])
        self.assertEqual(2, saved["evidence_summary"]["independent_run_count"])
        self.assertFalse(saved["safeguards"]["automatic_application_allowed"])
        self.assertTrue(saved["safeguards"]["requires_evaluation"])
        self.assertTrue(saved["safeguards"]["requires_human_approval"])
        self.assertFalse(saved["safeguards"]["default_policy_changed"])
        self.assertEqual(policy_before, policy_after)

    def test_identical_proposal_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-002", second), ("run-001", first)],
            )

            _, first_record, first_created = PROPOSAL.build_proposal(
                *args,
                **kwargs,
            )
            _, second_record, second_created = PROPOSAL.build_proposal(
                *args,
                **kwargs,
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_record, second_record)

    def test_repository_policy_path_is_stored_portably(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")

            _, proposal, _ = PROPOSAL.build_proposal(
                "Increase reviewed REUSE reasoning effort",
                "routes.REUSE.primary.reasoning_effort",
                "high",
                "Two independent reviewed executions support evaluation.",
                [("run-001", first), ("run-002", second)],
                runs_root=runs_root,
                policy_path=PROPOSAL.POLICY_PATH,
                output_dir=root / "proposals",
            )

        self.assertEqual(
            "problem-solving-project/model-policy.json",
            proposal["target"]["policy_path"],
        )

    def test_one_candidate_is_insufficient(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first)],
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_duplicate_candidate_is_not_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-001", first)],
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_cloned_source_hashes_are_not_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(
                runs_root,
                "run-001",
                result="same result\n",
            )
            second = self.make_promoted_run(
                runs_root,
                "run-002",
                result="same result\n",
            )
            first_run = runs_root / "run-001"
            second_run = runs_root / "run-002"
            (second_run / "goal_ledger.json").write_bytes(
                (first_run / "goal_ledger.json").read_bytes()
            )
            second_learning = json.loads(
                (second_run / "learning_record.json").read_text(encoding="utf-8")
            )
            second_learning["source"]["goal_ledger_sha256"] = sha256(
                second_run / "goal_ledger.json"
            )
            (second_run / "learning_record.json").write_text(
                json.dumps(second_learning),
                encoding="utf-8",
            )
            second_review = json.loads(
                (second_run / "learning_review.json").read_text(encoding="utf-8")
            )
            second_review["source"] = second_learning["source"]
            (second_run / "learning_review.json").write_text(
                json.dumps(second_review),
                encoding="utf-8",
            )
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_rejected_review_is_not_eligible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(
                runs_root,
                "run-002",
                decision="reject",
            )
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_route_specific_target_rejects_other_route_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(
                runs_root,
                "run-002",
                route="DIRECT",
            )
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_target_must_be_existing_policy_leaf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
                target="routes.REUSE.primary.unknown",
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_proposed_value_type_must_match_current_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
                target="routes.REUSE.primary.web_search",
                proposed_value="true",
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)

    def test_proposed_value_must_differ_from_current_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs_root = root / "runs"
            first = self.make_promoted_run(runs_root, "run-001")
            second = self.make_promoted_run(runs_root, "run-002")
            policy_path = self.make_policy(root)
            args, kwargs = self.proposal_arguments(
                runs_root,
                policy_path,
                root / "proposals",
                [("run-001", first), ("run-002", second)],
                proposed_value="medium",
            )

            with self.assertRaises(PROPOSAL.ProposalError):
                PROPOSAL.build_proposal(*args, **kwargs)


if __name__ == "__main__":
    unittest.main()
