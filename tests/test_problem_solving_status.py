import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import problem_solving_feedback as FEEDBACK
import problem_solving_review as REVIEW


MODULE_PATH = SCRIPTS_DIR / "problem_solving_status.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_status",
    MODULE_PATH,
)
STATUS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = STATUS
SPEC.loader.exec_module(STATUS)


class ProblemSolvingStatusTests(unittest.TestCase):
    def roots(self, root: Path) -> dict:
        return {
            "runs_root": root / "runs",
            "proposals_dir": root / "proposals",
            "evaluations_dir": root / "evaluations",
            "approvals_dir": root / "approvals",
            "changes_dir": root / "changes",
        }

    def make_run(
        self,
        runs_root: Path,
        run_id: str,
        *,
        route: str | None = "REUSE",
        status: str = "completed",
    ) -> Path:
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
                    "execution_status": status,
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "result.md").write_text(
            f"result for {run_id}\n",
            encoding="utf-8",
        )
        return run_dir

    def test_empty_roots_are_healthy_and_request_more_outcomes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status = STATUS.build_status(**self.roots(Path(temp_dir)))

        self.assertEqual("healthy", status["status"])
        self.assertEqual(0, status["summary"]["runs"]["total"])
        self.assertEqual(0, status["summary"]["invalid_count"])
        self.assertIn("collect_more_real_outcomes", status["next_actions"])

    def test_blocked_run_without_selected_route_is_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            self.make_run(
                roots["runs_root"],
                "blocked-run",
                route=None,
                status="blocked_by_capability",
            )

            status = STATUS.build_status(**roots)

        self.assertEqual("healthy", status["status"])
        self.assertEqual(1, status["summary"]["runs"]["valid"])
        self.assertEqual(1, status["summary"]["runs"]["not_completed"])

    def test_completed_run_without_selected_route_needs_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            self.make_run(
                roots["runs_root"],
                "broken-run",
                route=None,
                status="completed",
            )

            status = STATUS.build_status(**roots)

        self.assertEqual("attention", status["status"])
        self.assertEqual(1, status["summary"]["runs"]["invalid"])
        self.assertIn("inspect_invalid_records", status["next_actions"])

    def test_learning_and_review_counts_are_revalidated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            self.make_run(roots["runs_root"], "run-001")
            _, learning, _ = FEEDBACK.record_feedback(
                "run-001",
                "execution_succeeded",
                "The result completed successfully in the target environment.",
                ["receipt verified with zero issues"],
                runs_root=roots["runs_root"],
            )
            event_id = learning["events"][0]["event_id"]
            REVIEW.record_review(
                "run-001",
                event_id,
                "promote",
                "owner",
                "The receipt supports the recorded execution outcome.",
                ["manually inspected the receipt and output"],
                runs_root=roots["runs_root"],
            )

            status = STATUS.build_status(**roots)

        runs = status["summary"]["runs"]
        self.assertEqual("healthy", status["status"])
        self.assertEqual(1, runs["learning_events"])
        self.assertEqual(1, runs["promoted"])
        self.assertEqual(0, runs["unreviewed"])
        self.assertIn("collect_more_real_outcomes", status["next_actions"])

    def test_unreviewed_learning_event_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            self.make_run(roots["runs_root"], "run-001")
            FEEDBACK.record_feedback(
                "run-001",
                "corrected",
                "The target audience should be a new operator.",
                runs_root=roots["runs_root"],
            )

            status = STATUS.build_status(**roots)

        self.assertEqual(1, status["summary"]["runs"]["unreviewed"])
        self.assertIn("review_learning_candidates", status["next_actions"])

    def test_tampered_learning_record_needs_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            run_dir = self.make_run(roots["runs_root"], "run-001")
            path, learning, _ = FEEDBACK.record_feedback(
                "run-001",
                "corrected",
                "The target audience should be a new operator.",
                runs_root=roots["runs_root"],
            )
            learning["events"][0]["note"] = "tampered"
            path.write_text(json.dumps(learning), encoding="utf-8")

            status = STATUS.build_status(**roots)

        self.assertEqual("attention", status["status"])
        self.assertEqual(1, status["summary"]["invalid_count"])
        self.assertFalse(status["items"]["runs"][0]["valid"])
        self.assertEqual(run_dir.name, status["items"]["runs"][0]["run_id"])

    def test_malformed_policy_artifact_needs_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roots = self.roots(root)
            roots["proposals_dir"].mkdir()
            (roots["proposals_dir"] / "broken.json").write_text(
                "{}",
                encoding="utf-8",
            )

            status = STATUS.build_status(**roots)

        self.assertEqual("attention", status["status"])
        self.assertEqual(1, status["summary"]["proposals"]["invalid"])

    def test_cli_supports_human_and_json_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            roots = self.roots(Path(temp_dir))
            common = [
                "--runs-root",
                str(roots["runs_root"]),
                "--proposals-dir",
                str(roots["proposals_dir"]),
                "--evaluations-dir",
                str(roots["evaluations_dir"]),
                "--approvals-dir",
                str(roots["approvals_dir"]),
                "--changes-dir",
                str(roots["changes_dir"]),
            ]
            human = StringIO()
            with redirect_stdout(human):
                human_exit = STATUS.main(common)
            machine = StringIO()
            with redirect_stdout(machine):
                json_exit = STATUS.main([*common, "--json"])
            payload = json.loads(machine.getvalue())

        self.assertEqual(0, human_exit)
        self.assertEqual(0, json_exit)
        self.assertIn("PSOS status: healthy", human.getvalue())
        self.assertEqual("healthy", payload["status"])


if __name__ == "__main__":
    unittest.main()
