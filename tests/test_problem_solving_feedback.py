import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_feedback.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_feedback", MODULE_PATH)
FEEDBACK = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = FEEDBACK
SPEC.loader.exec_module(FEEDBACK)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProblemSolvingFeedbackTests(unittest.TestCase):
    def make_run(self, runs_root: Path, run_id: str = "run-001") -> Path:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.txt").write_text("요청\n", encoding="utf-8")
        (run_dir / "goal_ledger.json").write_text(
            json.dumps({"parent_goal": "실제 결과 확보"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "route.json").write_text(
            json.dumps(
                {
                    "selected_route": "REUSE",
                    "execution_status": "completed",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (run_dir / "result.md").write_text("검증된 결과\n", encoding="utf-8")
        return run_dir

    def test_records_adoption_with_evidence_without_changing_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)
            policy_path = ROOT / "problem-solving-project" / "model-policy.json"
            policy_before = sha256(policy_path)

            record_path, record, created = FEEDBACK.record_feedback(
                "run-001",
                "adopted",
                "주간 운영 보고서에 이 결과를 그대로 채택했습니다.",
                ["2026-W31 팀 주간 보고서에 반영됨"],
                runs_root=runs_root,
            )

            policy_after = sha256(policy_path)
            saved = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertTrue(created)
        self.assertEqual(record, saved)
        self.assertEqual(1, saved["summary"]["event_count"])
        self.assertEqual({"adopted": 1}, saved["summary"]["signals"])
        self.assertFalse(saved["default_policy_changed"])
        self.assertFalse(saved["events"][0]["eligible_for_default_change"])
        self.assertEqual("candidate", saved["events"][0]["promotion_state"])
        self.assertEqual(policy_before, policy_after)

    def test_duplicate_feedback_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            arguments = (
                "run-001",
                "execution_succeeded",
                "생성 결과가 실제 운영 환경에서 정상 실행됐습니다.",
                ["exit code 0과 예상 출력 확인"],
            )

            _, first, first_created = FEEDBACK.record_feedback(
                *arguments,
                runs_root=runs_root,
            )
            _, second, second_created = FEEDBACK.record_feedback(
                *arguments,
                runs_root=runs_root,
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first, second)
        self.assertEqual(1, len(second["events"]))

    def test_cli_duplicate_reports_the_matching_older_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)
            first_arguments = (
                "run-001",
                "corrected",
                "첫 번째 구체적 정정 사항입니다.",
                [],
            )
            _, first_record, _ = FEEDBACK.record_feedback(
                *first_arguments,
                runs_root=runs_root,
            )
            first_id = first_record["events"][0]["event_id"]
            FEEDBACK.record_feedback(
                "run-001",
                "rejected",
                "두 번째 결과는 요청 범위를 벗어나 거부했습니다.",
                runs_root=runs_root,
            )

            from contextlib import redirect_stdout
            from io import StringIO

            output = StringIO()
            with redirect_stdout(output):
                status = FEEDBACK.main(
                    [
                        "--run-id",
                        "run-001",
                        "--signal",
                        "corrected",
                        "--note",
                        "첫 번째 구체적 정정 사항입니다.",
                        "--runs-root",
                        str(runs_root),
                    ]
                )

        self.assertEqual(0, status)
        self.assertIn("already_exists", output.getvalue())
        self.assertIn(first_id, output.getvalue())

    def test_weak_reaction_is_not_recorded_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)

            with self.assertRaises(FEEDBACK.FeedbackError):
                FEEDBACK.record_feedback(
                    "run-001",
                    "execution_succeeded",
                    "ㄱㄱ",
                    ["좋아"],
                    runs_root=runs_root,
                )

        self.assertFalse((run_dir / "learning_record.json").exists())

    def test_adoption_and_execution_success_require_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)

            for signal in ("adopted", "execution_succeeded"):
                with self.subTest(signal=signal):
                    with self.assertRaises(FEEDBACK.FeedbackError):
                        FEEDBACK.record_feedback(
                            "run-001",
                            signal,
                            "구체적인 결과 설명은 있지만 증거가 없습니다.",
                            runs_root=runs_root,
                        )

    def test_specific_correction_does_not_require_adoption_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            self.make_run(runs_root)

            _, record, created = FEEDBACK.record_feedback(
                "run-001",
                "corrected",
                "독자 수준을 전문가가 아니라 신규 입사자로 수정해야 합니다.",
                runs_root=runs_root,
            )

        self.assertTrue(created)
        self.assertEqual("corrected", record["events"][0]["signal"])
        self.assertEqual([], record["events"][0]["evidence"])

    def test_missing_run_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = runs_root / "broken-run"
            run_dir.mkdir()
            (run_dir / "request.txt").write_text("요청", encoding="utf-8")

            with self.assertRaises(FEEDBACK.FeedbackError):
                FEEDBACK.record_feedback(
                    "broken-run",
                    "rejected",
                    "결과가 요청 범위를 벗어나 명시적으로 거부했습니다.",
                    runs_root=runs_root,
                )

    def test_changed_run_artifact_invalidates_existing_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)
            FEEDBACK.record_feedback(
                "run-001",
                "corrected",
                "첫 번째 구체적 정정 사항입니다.",
                runs_root=runs_root,
            )
            (run_dir / "result.md").write_text("사후 변경된 결과\n", encoding="utf-8")

            with self.assertRaises(FEEDBACK.FeedbackError):
                FEEDBACK.record_feedback(
                    "run-001",
                    "rejected",
                    "변경된 결과를 명시적으로 거부했습니다.",
                    runs_root=runs_root,
                )

    def test_tampered_promotion_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = self.make_run(runs_root)
            record_path, record, _ = FEEDBACK.record_feedback(
                "run-001",
                "corrected",
                "첫 번째 구체적 정정 사항입니다.",
                runs_root=runs_root,
            )
            record["events"][0]["eligible_for_default_change"] = True
            record["events"][0]["promotion_state"] = "promoted"
            record_path.write_text(
                json.dumps(record, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(FEEDBACK.FeedbackError):
                FEEDBACK.record_feedback(
                    "run-001",
                    "rejected",
                    "조작된 승격 상태를 명시적으로 거부합니다.",
                    runs_root=runs_root,
                )


if __name__ == "__main__":
    unittest.main()
