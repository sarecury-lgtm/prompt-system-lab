import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_quality_next_loop_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_quality_next_loop_web", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


def result(route):
    return {
        "run_id": "replacement-run",
        "route": route,
        "execution_status": "completed",
        "result_markdown": route,
        "artifacts": [],
        "evidence": [],
        "limitations": [],
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


def wait_for_job(manager, job_id):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job and job["state"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


class QualityNextLoopWebTests(unittest.TestCase):
    def test_combined_manager_routes_quality_and_next_loop_separately(self):
        calls = []

        def quality_runner(request, search, run_id, workspace_write, paths, approval):
            calls.append(("quality", request, search, workspace_write))
            return result("QUALITY")

        def next_runner(request, search, run_id, workspace_write, paths, approval):
            calls.append(("next", request, search, workspace_write))
            return result("NEXT_LOOP")

        manager = WEB.CombinedJobManager(
            quality_runner=quality_runner,
            next_runner=next_runner,
            resume_runner=quality_runner,
        )
        try:
            quality = manager.submit("일반 요청", False)
            next_job = manager.submit("후보 요청", False, execution_mode="next_loop")
            quality_done = wait_for_job(manager, quality["job_id"])
            next_done = wait_for_job(manager, next_job["job_id"])
        finally:
            manager.shutdown()

        self.assertEqual("QUALITY", quality_done["route"])
        self.assertEqual("NEXT_LOOP", next_done["route"])
        self.assertIn(("quality", "일반 요청", False, False), calls)
        self.assertIn(("next", "후보 요청", True, False), calls)

    def test_next_loop_rejects_workspace_write(self):
        manager = WEB.CombinedJobManager(
            quality_runner=lambda *args: result("QUALITY"),
            next_runner=lambda *args: result("NEXT_LOOP"),
            resume_runner=lambda *args: result("RESUME"),
        )
        try:
            with self.assertRaisesRegex(ValueError, "파일 변경"):
                manager.submit(
                    "후보 요청",
                    True,
                    workspace_write=True,
                    allowed_write_paths=["web/"],
                    approval={"approval_id": "test"},
                    execution_mode="next_loop",
                )
        finally:
            manager.shutdown()

    def test_public_payload_exposes_candidate_pause_without_calling_it_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "next-test"
            run_dir.mkdir()
            (run_dir / "result.md").write_text("# 후보 작업대\n", encoding="utf-8")
            state = {
                "state": "awaiting_correction",
                "dynamic_state": None,
                "candidate_working_set": {
                    "candidates": [
                        {
                            "source_url": "https://example.test/a",
                            "why_actionable": "현재 후보",
                        }
                    ]
                },
            }
            payload = WEB.public_next_loop_payload(run_dir, state)

        self.assertEqual("awaiting_correction", payload["execution_status"])
        self.assertIn("교정을 기다리고", payload["limitations"][0])
        self.assertEqual("https://example.test/a", payload["evidence"][0]["source"])

    def test_frontend_assets_are_appended_after_quality_assets(self):
        self.assertEqual(
            ["quality-review.js", "next-loop.js"],
            WEB.STATIC_ADDONS["app.js"],
        )
        self.assertEqual(
            ["quality-review.css", "next-loop.css"],
            WEB.STATIC_ADDONS["styles.css"],
        )

    def test_resume_envelope_is_json_object(self):
        envelope = json.dumps(
            {"run_id": "next-test", "body": {"correction_text": "후보 A 제외"}},
            ensure_ascii=False,
        )
        parsed = json.loads(envelope)
        self.assertEqual("후보 A 제외", parsed["body"]["correction_text"])


if __name__ == "__main__":
    unittest.main()
