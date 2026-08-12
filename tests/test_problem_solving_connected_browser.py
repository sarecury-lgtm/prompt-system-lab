import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_connected_browser.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_connected_browser", MODULE_PATH)
BROWSER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = BROWSER
SPEC.loader.exec_module(BROWSER)

WEB_PATH = SCRIPTS / "problem_solving_quality_web.py"
WEB_SPEC = importlib.util.spec_from_file_location("connected_browser_quality_web", WEB_PATH)
WEB = importlib.util.module_from_spec(WEB_SPEC)
assert WEB_SPEC.loader is not None
sys.modules[WEB_SPEC.name] = WEB
WEB_SPEC.loader.exec_module(WEB)


class FakeJobs:
    def __init__(self):
        self.calls = []

    def submit(self, request, search_enabled):
        self.calls.append((request, search_enabled))
        return {
            "job_id": "job-browser-repair",
            "run_id": "psos-browser-repair",
            "state": "queued",
        }


class ConnectedBrowserTests(unittest.TestCase):
    def make_run(self, root, urls):
        run_dir = Path(root) / "psos-browser-parent"
        run_dir.mkdir()
        rows = ["| 상품 | 링크 |", "|---|---|"]
        rows.extend(f"| 후보 | [열기]({url}) |" for url in urls)
        (run_dir / "result.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        route = {
            "selected_route": "RESEARCH",
            "execution_status": "partial",
            "evidence": [],
            "limitations": [],
            "run": {"run_id": run_dir.name},
        }
        (run_dir / "route.json").write_text(
            json.dumps(route, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return run_dir

    def receipt(self, url, status, signal):
        return {
            "url": url,
            "final_url": url,
            "status": status,
            "checked_at": "2026-08-02T12:00:00+00:00",
            "signal": signal,
            "excerpt": "상품 페이지 본문",
            "text_sha256": "a" * 64,
            "fields": {
                "title": "수입 냉동 삼겹살 2kg",
                "prices": ["17,600원"],
                "shipping": ["무료배송"],
                "weights": ["2kg"],
                "selected_options": ["구이용 2kg"],
                "purchase_controls": ["구매하기"],
            },
        }

    def test_queue_pauses_for_user_and_preserves_progress(self):
        urls = [
            "https://shop.example.test/products/one",
            "https://shop.example.test/products/two",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(temp_dir, urls)
            queue = BROWSER.create_queue(run_dir)
            first = queue["targets"][0]
            paused = BROWSER.submit_receipt(
                run_dir,
                first["id"],
                self.receipt(first["url"], "needs_user", "사람인지 확인"),
            )
            loaded = BROWSER.create_queue(run_dir)

        self.assertEqual("needs_user", paused["state"])
        self.assertEqual(1, loaded["targets"][0]["attempts"])
        self.assertEqual("pending", loaded["targets"][1]["status"])

    def test_completed_queue_becomes_authoritative_run_evidence(self):
        urls = [
            "https://shop.example.test/products/one",
            "https://shop.example.test/products/two",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(temp_dir, urls)
            queue = BROWSER.create_queue(run_dir)
            BROWSER.submit_receipt(
                run_dir,
                queue["targets"][0]["id"],
                self.receipt(urls[0], "available", "구매하기"),
            )
            complete = BROWSER.submit_receipt(
                run_dir,
                queue["targets"][1]["id"],
                self.receipt(urls[1], "sold_out", "현재 판매중인 상품이 아닙니다"),
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            markdown = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("completed", complete["state"])
        self.assertEqual(1, complete["counts"]["available"])
        self.assertEqual("partial", route["execution_status"])
        self.assertEqual(2, sum("[CONNECTED_BROWSER]" in item["finding"] for item in route["evidence"]))
        self.assertIn("사용자 Chrome 실시간 검증", markdown)
        self.assertIn("sold_out", markdown)

    def test_completed_receipts_start_one_search_repair(self):
        url = "https://shop.example.test/products/one"
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(temp_dir, [url])
            queue = BROWSER.create_queue(run_dir)
            jobs = FakeJobs()
            original_safe_run_dir = WEB.base_web.safe_run_dir
            WEB.base_web.safe_run_dir = lambda _run_id: run_dir
            try:
                result = WEB.submit_connected_browser_receipt(
                    jobs,
                    run_dir.name,
                    queue["targets"][0]["id"],
                    self.receipt(url, "available", "구매하기"),
                )
                second = WEB.submit_connected_browser_receipt(
                    jobs,
                    run_dir.name,
                    queue["targets"][0]["id"],
                    self.receipt(url, "available", "구매하기"),
                )
            finally:
                WEB.base_web.safe_run_dir = original_safe_run_dir

        self.assertEqual(1, len(jobs.calls))
        self.assertTrue(jobs.calls[0][1])
        self.assertIn(BROWSER.RECEIPT_NAME, jobs.calls[0][0])
        self.assertEqual("psos-browser-repair", result["revision"]["run_id"])
        self.assertIsNone(second["revision"])

    def test_rejects_receipt_for_another_url(self):
        url = "https://shop.example.test/products/one"
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = self.make_run(temp_dir, [url])
            queue = BROWSER.create_queue(run_dir)
            bad = self.receipt("https://evil.example.test/products/other", "available", "구매하기")
            with self.assertRaisesRegex(BROWSER.ConnectedBrowserError, "등록되지 않은"):
                BROWSER.submit_receipt(run_dir, queue["targets"][0]["id"], bad)


if __name__ == "__main__":
    unittest.main()
