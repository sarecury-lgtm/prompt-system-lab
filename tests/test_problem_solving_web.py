import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "problem_solving_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_web", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


class ProblemSolvingWebTests(unittest.TestCase):
    def wait_for_job(self, manager, job_id):
        for _ in range(100):
            job = manager.get(job_id)
            if job["state"] in {"completed", "failed"}:
                return job
            time.sleep(0.01)
        self.fail("job did not finish")

    def test_job_manager_completes_and_returns_public_result(self):
        def runner(request, search_enabled, run_id):
            return {
                "run_id": run_id,
                "route": "REUSE",
                "execution_status": "completed",
                "result_markdown": f"# 결과\n\n{request}",
                "artifacts": [{"path": "USAGE.md"}],
                "evidence": [{"finding": "verified"}],
                "limitations": [],
            }

        manager = WEB.JobManager(runner=runner)
        try:
            submitted = manager.submit("문서를 확인해 줘", False)
            job = self.wait_for_job(manager, submitted["job_id"])
        finally:
            manager.shutdown()

        self.assertEqual("completed", job["state"])
        self.assertEqual("REUSE", job["route"])
        self.assertTrue(job["run_id"].startswith("psos-"))
        self.assertNotIn("_runner", job)

    def test_job_manager_records_failure_without_traceback(self):
        def runner(_request, _search_enabled, _run_id):
            raise RuntimeError("engine unavailable")

        manager = WEB.JobManager(runner=runner)
        try:
            submitted = manager.submit("요청", False)
            job = self.wait_for_job(manager, submitted["job_id"])
        finally:
            manager.shutdown()

        self.assertEqual("failed", job["state"])
        self.assertEqual("engine unavailable", job["error"])
        self.assertIsNotNone(job["finished_at"])

    def test_job_manager_rejects_empty_and_invalid_search(self):
        manager = WEB.JobManager(runner=lambda *_: {})
        try:
            with self.assertRaisesRegex(ValueError, "요청"):
                manager.submit("  ", False)
            with self.assertRaisesRegex(ValueError, "검색"):
                manager.submit("요청", "yes")
            with self.assertRaisesRegex(ValueError, "10,000자"):
                manager.submit("요" * 10_001, False)
        finally:
            manager.shutdown()

    def test_active_run_id_is_visible_for_status_exclusion(self):
        release = WEB.threading.Event()

        def runner(_request, _search_enabled, run_id):
            release.wait(1)
            return {
                "run_id": run_id,
                "route": "DIRECT",
                "execution_status": "completed",
                "result_markdown": "완료",
                "artifacts": [],
                "evidence": [],
                "limitations": [],
            }

        manager = WEB.JobManager(runner=runner)
        try:
            submitted = manager.submit("요청", False)
            active = manager.active_run_ids()
            release.set()
            self.wait_for_job(manager, submitted["job_id"])
        finally:
            manager.shutdown()

        self.assertEqual({submitted["run_id"]}, active)
        self.assertEqual(set(), manager.active_run_ids())

    def test_load_run_returns_bounded_public_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = runs_root / "psos-test"
            run_dir.mkdir()
            (run_dir / "request.txt").write_text("실제 요청\n", encoding="utf-8")
            (run_dir / "result.md").write_text("# 결과\n", encoding="utf-8")
            (run_dir / "goal_ledger.json").write_text(
                json.dumps(
                    {
                        "parent_goal": "목표",
                        "current_step": "결과 확인",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "route.json").write_text(
                json.dumps(
                    {
                        "selected_route": "DIRECT",
                        "execution_status": "completed",
                        "route_reason": "즉답",
                        "artifacts": [],
                        "evidence": [],
                        "limitations": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = WEB.load_run("psos-test", runs_root)

        self.assertEqual("실제 요청", payload["request"])
        self.assertEqual("DIRECT", payload["route"])
        self.assertEqual("목표", payload["goal"])
        self.assertNotIn("engine_trace", payload)

    def test_safe_run_dir_rejects_traversal_and_missing_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "ID"):
                WEB.safe_run_dir("../outside", runs_root)
            with self.assertRaises(FileNotFoundError):
                WEB.safe_run_dir("missing", runs_root)

    def test_find_chrome_returns_only_existing_path(self):
        found = WEB.find_chrome()
        self.assertTrue(found is None or found.is_file())


if __name__ == "__main__":
    unittest.main()
