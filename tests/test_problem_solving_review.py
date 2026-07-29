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


MODULE_PATH = SCRIPTS_DIR / "problem_solving_review.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_review", MODULE_PATH)
REVIEW = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProblemSolvingReviewTests(unittest.TestCase):
    def make_run(self, runs_root: Path, run_id: str = "run-001") -> Path:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.txt").write_text("request\n", encoding="utf-8")
        (run_dir / "goal_ledger.json").write_text(
            json.dumps({"parent_goal": "obtain a real result"}),
            encoding="utf-8",
        )
        (run_dir / "route.json").write_text(
            json.dumps(
                {
                    "selected_route": "REUSE",
                    "execution_status": "completed",
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "result.md").write_text("verified result\n", encoding="utf-8")
        return run_dir

    def add_feedback(
        self,
        runs_root: Path,
        *,
        note: str = "The result completed successfully in the target environment.",
    ) -> str:
        _, record, _ = FEEDBACK.record_feedback(
            "run-001",
            "execution_succeeded",
            note,
            ["exit code 0 and expected artifact verified"],
            runs_root=runs_root,
        )
        return record["events"][-1]["event_id"]

    def test_promotes_reviewed_candidate_without_changing_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)
            policy_path = ROOT / "problem-solving-project" / "model-policy.json"
            policy_before = sha256(policy_path)

            path, record, created = REVIEW.record_review(
                "run-001",
                event_id,
                "promote",
                "owner",
                "The receipt and produced artifact agree with the success claim.",
                ["manually inspected the receipt and output artifact"],
                runs_root=runs_root,
            )

            saved = json.loads(path.read_text(encoding="utf-8"))
            policy_after = sha256(policy_path)

        self.assertTrue(created)
        self.assertEqual(record, saved)
        self.assertEqual(1, saved["summary"]["promoted"])
        self.assertTrue(saved["decisions"][0]["eligible_for_policy_proposal"])
        self.assertFalse(saved["decisions"][0]["policy_applied"])
        self.assertFalse(saved["default_policy_changed"])
        self.assertEqual(policy_before, policy_after)

    def test_rejects_candidate_without_policy_eligibility(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)

            _, record, created = REVIEW.record_review(
                "run-001",
                event_id,
                "reject",
                "owner",
                "The evidence does not establish that the output was adopted.",
                ["receipt proves execution only, not downstream adoption"],
                runs_root=runs_root,
            )

        self.assertTrue(created)
        self.assertEqual(1, record["summary"]["rejected"])
        self.assertFalse(record["decisions"][0]["eligible_for_policy_proposal"])

    def test_identical_review_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)
            arguments = (
                "run-001",
                event_id,
                "promote",
                "owner",
                "The execution receipt directly supports this outcome.",
                ["receipt verified true with zero issues"],
            )

            _, first, first_created = REVIEW.record_review(
                *arguments,
                runs_root=runs_root,
            )
            _, second, second_created = REVIEW.record_review(
                *arguments,
                runs_root=runs_root,
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)
        self.assertEqual(1, len(second["decisions"]))

    def test_existing_decision_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)
            REVIEW.record_review(
                "run-001",
                event_id,
                "promote",
                "owner",
                "The execution evidence is sufficient for this candidate.",
                ["receipt verified true with zero issues"],
                runs_root=runs_root,
            )

            with self.assertRaises(REVIEW.ReviewError):
                REVIEW.record_review(
                    "run-001",
                    event_id,
                    "reject",
                    "owner",
                    "A later opinion should not overwrite an audit decision.",
                    ["attempted decision replacement"],
                    runs_root=runs_root,
                )

    def test_review_requires_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)

            with self.assertRaises(REVIEW.ReviewError):
                REVIEW.record_review(
                    "run-001",
                    event_id,
                    "promote",
                    "owner",
                    "The candidate appears correct but has no review evidence.",
                    runs_root=runs_root,
                )

    def test_unknown_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            self.add_feedback(runs_root)

            with self.assertRaises(REVIEW.ReviewError):
                REVIEW.record_review(
                    "run-001",
                    "feedback-does-not-exist",
                    "reject",
                    "owner",
                    "The referenced candidate cannot be found.",
                    ["checked the run learning record"],
                    runs_root=runs_root,
                )

    def test_new_feedback_can_be_reviewed_after_an_earlier_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            first_event = self.add_feedback(runs_root)
            REVIEW.record_review(
                "run-001",
                first_event,
                "promote",
                "owner",
                "The first event is supported by its receipt.",
                ["first receipt manually verified"],
                runs_root=runs_root,
            )
            second_event = self.add_feedback(
                runs_root,
                note="A second independent execution also completed successfully.",
            )

            _, record, created = REVIEW.record_review(
                "run-001",
                second_event,
                "promote",
                "owner",
                "The second event has independent execution evidence.",
                ["second receipt manually verified"],
                runs_root=runs_root,
            )

        self.assertTrue(created)
        self.assertEqual(2, record["summary"]["decision_count"])
        self.assertEqual(2, record["summary"]["promoted"])

    def test_tampered_learning_event_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)
            learning_path = run_dir / "learning_record.json"
            learning = json.loads(learning_path.read_text(encoding="utf-8"))
            learning["events"][0]["note"] = "tampered outcome"
            learning_path.write_text(json.dumps(learning), encoding="utf-8")

            with self.assertRaises(REVIEW.ReviewError):
                REVIEW.record_review(
                    "run-001",
                    event_id,
                    "promote",
                    "owner",
                    "Tampered source events cannot be promoted.",
                    ["event ID no longer matches event content"],
                    runs_root=runs_root,
                )

    def test_tampered_review_policy_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)
            event_id = self.add_feedback(runs_root)
            path, record, _ = REVIEW.record_review(
                "run-001",
                event_id,
                "promote",
                "owner",
                "The execution evidence supports this candidate.",
                ["receipt verified true with zero issues"],
                runs_root=runs_root,
            )
            record["decisions"][0]["policy_applied"] = True
            path.write_text(json.dumps(record), encoding="utf-8")

            with self.assertRaises(REVIEW.ReviewError):
                REVIEW.record_review(
                    "run-001",
                    event_id,
                    "promote",
                    "owner",
                    "The execution evidence supports this candidate.",
                    ["receipt verified true with zero issues"],
                    runs_root=runs_root,
                )


if __name__ == "__main__":
    unittest.main()
