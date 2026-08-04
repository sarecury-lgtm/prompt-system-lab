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

import problem_solving_quality_next_loop_job_packet as PACKET


WEB_PATH = SCRIPTS / "problem_solving_quality_next_loop_web.py"
WEB_SPEC = importlib.util.spec_from_file_location(
    "problem_solving_quality_next_loop_web_job_packet_test",
    WEB_PATH,
)
WEB = importlib.util.module_from_spec(WEB_SPEC)
assert WEB_SPEC.loader is not None
sys.modules[WEB_SPEC.name] = WEB
WEB_SPEC.loader.exec_module(WEB)
PACKET.install(WEB)


def wait_for_job(manager, job_id):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job and job["state"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def basic_result(route, markdown):
    return {
        "run_id": "packet-run",
        "route": route,
        "execution_status": "completed",
        "result_markdown": markdown,
        "artifacts": [],
        "evidence": [],
        "limitations": [],
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


class AutomaticJobPacketTests(unittest.TestCase):
    def test_specific_decision_precedes_broad_candidate_search(self):
        self.assertEqual(
            "DECISION",
            PACKET.infer_route("토스트 주식을 오늘 살까? 내일 실적 발표야."),
        )
        self.assertEqual(
            "CANDIDATE",
            PACKET.infer_route("오늘 살 만한 미국 주식 종목을 추천해 줘."),
        )
        self.assertEqual(
            "RESEARCH",
            PACKET.infer_route("어도비의 최신 실적과 현재 가격을 확인해 줘."),
        )

    def test_candidate_prompt_requires_final_selection_not_workbench_pause(self):
        packet = PACKET.build_job_packet(
            "오늘 살 만한 미국 주식 종목을 추천해 줘.",
            job_id="packet-test",
        )
        prompt = PACKET.build_execution_prompt(packet)

        self.assertEqual("CANDIDATE", packet["route_hint"])
        self.assertIn("후보 작업대에서 멈추거나", prompt)
        self.assertIn("최종 1순위", prompt)
        self.assertIn(PACKET.START_MARKER, prompt)
        self.assertIn(PACKET.END_MARKER, prompt)

    def test_runner_strips_envelope_and_keeps_structured_evidence(self):
        captured = {}

        def quality_runner(request, search, run_id, workspace_write, paths, approval):
            captured.update(
                request=request,
                search=search,
                run_id=run_id,
                workspace_write=workspace_write,
            )
            envelope = {
                "version": 1,
                "job_id": run_id,
                "status": "completed",
                "route": "CANDIDATE",
                "goal": {
                    "parent": "오늘 살 종목 선택",
                    "current": "검증 후 1순위 선택",
                    "constraints": [],
                    "completion_condition": "1순위 결정",
                },
                "decision": {
                    "conclusion": "어도비",
                    "action": "분할 매수",
                    "confidence": "medium",
                    "change_conditions": ["260달러 이상 추격 금지"],
                },
                "completion": {"met": True, "missing": []},
                "evidence": [
                    {
                        "source": "https://example.test/adobe",
                        "finding": "실적과 밸류에이션 확인",
                    }
                ],
                "candidates": [],
                "artifacts": [],
                "continuation": {
                    "preserve": [],
                    "excluded_candidate_ids": [],
                    "unresolved": [],
                },
            }
            markdown = "# 결론\n\n오늘 하나만 고르면 어도비입니다.\n\n"
            markdown += PACKET.START_MARKER + "\n```json\n"
            markdown += json.dumps(envelope, ensure_ascii=False, indent=2)
            markdown += "\n```\n" + PACKET.END_MARKER
            return basic_result("RESEARCH", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            run_dir = runs_root / "packet-run"
            run_dir.mkdir()
            result = PACKET.run_job_packet_request(
                "오늘 살 만한 미국 주식 종목을 추천해 줘.",
                False,
                "packet-run",
                False,
                [],
                None,
                quality_runner=quality_runner,
                runs_root=runs_root,
            )

            self.assertTrue((run_dir / "automatic_job_packet.json").is_file())
            self.assertTrue((run_dir / "automatic_original_request.txt").is_file())

        self.assertTrue(captured["search"])
        self.assertFalse(captured["workspace_write"])
        self.assertIn("PSOS Job Packet", captured["request"])
        self.assertEqual("JOB_PACKET · CANDIDATE", result["route"])
        self.assertEqual("# 결론\n\n오늘 하나만 고르면 어도비입니다.", result["result_markdown"])
        self.assertEqual(
            "https://example.test/adobe",
            result["evidence"][0]["source"],
        )
        self.assertNotIn(PACKET.START_MARKER, result["result_markdown"])

    def test_combined_manager_keeps_job_packet_and_advanced_loop_separate(self):
        calls = []

        def runner(label):
            def execute(request, search, run_id, workspace_write, paths, approval):
                calls.append((label, request, search, workspace_write))
                return basic_result(label.upper(), label)

            return execute

        manager = WEB.CombinedJobManager(
            quality_runner=runner("quality"),
            next_runner=runner("next"),
            resume_runner=runner("resume"),
            job_packet_runner=runner("packet"),
        )
        try:
            automatic = manager.submit(
                "오늘 살 종목 추천",
                False,
                execution_mode="job_packet",
            )
            advanced = manager.submit(
                "후보를 먼저 보여줘",
                False,
                execution_mode="next_loop",
            )
            automatic_done = wait_for_job(manager, automatic["job_id"])
            advanced_done = wait_for_job(manager, advanced["job_id"])
        finally:
            manager.shutdown()

        self.assertEqual("PACKET", automatic_done["route"])
        self.assertEqual("NEXT", advanced_done["route"])
        self.assertIn(("packet", "오늘 살 종목 추천", True, False), calls)
        self.assertIn(("next", "후보를 먼저 보여줘", True, False), calls)

    def test_job_packet_rejects_workspace_write(self):
        manager = WEB.CombinedJobManager(
            quality_runner=lambda *args: basic_result("QUALITY", "quality"),
            next_runner=lambda *args: basic_result("NEXT", "next"),
            resume_runner=lambda *args: basic_result("RESUME", "resume"),
            job_packet_runner=lambda *args: basic_result("PACKET", "packet"),
        )
        try:
            with self.assertRaisesRegex(ValueError, "파일 변경"):
                manager.submit(
                    "파일 수정",
                    False,
                    workspace_write=True,
                    allowed_write_paths=["web/"],
                    approval={"approval_id": "test"},
                    execution_mode="job_packet",
                )
        finally:
            manager.shutdown()


if __name__ == "__main__":
    unittest.main()
