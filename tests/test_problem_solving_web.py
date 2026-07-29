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
        def runner(
            request,
            search_enabled,
            run_id,
            workspace_write,
            allowed_write_paths,
            approval,
        ):
            self.assertFalse(workspace_write)
            self.assertEqual([], allowed_write_paths)
            self.assertIsNone(approval)
            return {
                "run_id": run_id,
                "route": "REUSE",
                "execution_status": "completed",
                "result_markdown": f"# 결과\n\n{request}",
                "artifacts": [{"path": "USAGE.md"}],
                "evidence": [{"finding": "verified"}],
                "limitations": [],
                "workspace_receipt": None,
                "workspace_rollback": None,
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
        def runner(*_args):
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

        def runner(
            _request,
            _search_enabled,
            run_id,
            _workspace_write,
            _allowed_write_paths,
            _approval,
        ):
            release.wait(1)
            return {
                "run_id": run_id,
                "route": "DIRECT",
                "execution_status": "completed",
                "result_markdown": "완료",
                "artifacts": [],
                "evidence": [],
                "limitations": [],
                "workspace_receipt": None,
                "workspace_rollback": None,
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

    def test_job_manager_requires_scoped_approval_for_workspace_write(self):
        manager = WEB.JobManager(runner=lambda *_: {})
        try:
            with self.assertRaisesRegex(ValueError, "경로"):
                manager.submit(
                    "modify a file",
                    False,
                    workspace_write=True,
                    approval={"approval_id": "approval-test"},
                )
            with self.assertRaisesRegex(ValueError, "승인"):
                manager.submit(
                    "modify a file",
                    False,
                    workspace_write=True,
                    allowed_write_paths=["web/app.js"],
                )
        finally:
            manager.shutdown()

    def test_approval_is_one_time_and_starts_scoped_write_job(self):
        captured = {}

        def runner(
            request,
            search_enabled,
            run_id,
            workspace_write,
            allowed_write_paths,
            approval,
        ):
            captured.update(
                {
                    "request": request,
                    "search_enabled": search_enabled,
                    "workspace_write": workspace_write,
                    "allowed_write_paths": allowed_write_paths,
                    "approval": approval,
                }
            )
            return {
                "run_id": run_id,
                "route": "CODE",
                "execution_status": "completed",
                "result_markdown": "변경 완료",
                "artifacts": [{"path": "web/app.js", "action": "modified"}],
                "evidence": [],
                "limitations": [],
                "workspace_receipt": {"verified": True},
                "workspace_rollback": None,
            }

        jobs = WEB.JobManager(runner=runner)
        approvals = WEB.ApprovalManager(jobs)
        try:
            pending = approvals.create(
                "web/app.js를 수정해 줘",
                False,
                ["web/app.js"],
            )
            approved, submitted = approvals.approve(pending["approval_id"])
            job = self.wait_for_job(jobs, submitted["job_id"])
            with self.assertRaisesRegex(ValueError, "상태"):
                approvals.approve(pending["approval_id"])
        finally:
            jobs.shutdown()

        self.assertEqual("approved", approved["status"])
        self.assertEqual("completed", job["state"])
        self.assertTrue(captured["workspace_write"])
        self.assertEqual(["web/app.js"], captured["allowed_write_paths"])
        self.assertEqual(
            "local_web_explicit_click",
            captured["approval"]["approval_method"],
        )

    def test_rejected_approval_cannot_execute(self):
        jobs = WEB.JobManager(runner=lambda *_: {})
        approvals = WEB.ApprovalManager(jobs)
        try:
            pending = approvals.create(
                "문서를 수정해 줘",
                False,
                ["USAGE.md"],
            )
            rejected = approvals.reject(pending["approval_id"])
            with self.assertRaisesRegex(ValueError, "상태"):
                approvals.approve(pending["approval_id"])
        finally:
            jobs.shutdown()

        self.assertEqual("rejected", rejected["status"])

    def test_approval_records_job_submission_failure(self):
        jobs = WEB.JobManager(runner=lambda *_: {})
        approvals = WEB.ApprovalManager(jobs)
        pending = approvals.create(
            "문서를 수정해 줘",
            False,
            ["USAGE.md"],
        )
        original_submit = jobs.submit

        def fail_submit(*_args, **_kwargs):
            raise RuntimeError("queue unavailable")

        jobs.submit = fail_submit
        try:
            with self.assertRaisesRegex(RuntimeError, "queue unavailable"):
                approvals.approve(pending["approval_id"])
            failed = approvals.get(pending["approval_id"])
        finally:
            jobs.submit = original_submit
            jobs.shutdown()

        self.assertEqual("failed", failed["status"])
        self.assertEqual("queue unavailable", failed["error"])
        self.assertIsNone(failed["job_id"])

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
