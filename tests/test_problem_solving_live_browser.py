import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_live_browser.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_live_browser", MODULE_PATH)
BROWSER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = BROWSER
SPEC.loader.exec_module(BROWSER)


def execution_payload(url="https://shop.test/products/123"):
    return {
        "execution": {
            "status": "completed",
            "summary": "상품 확인",
            "result_markdown": f"[상품]({url})",
            "capabilities_used": ["live_web_search"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [
                {
                    "source": url,
                    "finding": "현재 판매 상태와 구매 가능 여부를 확인했다.",
                    "kind": "web",
                }
            ],
            "limitations": [],
        }
    }


class LiveBrowserTests(unittest.TestCase):
    def test_candidate_table_urls_take_priority_over_excluded_evidence(self):
        payload = execution_payload("https://shop.test/products/candidate")
        payload["execution"]["result_markdown"] = (
            "| 후보 | 링크 |\n"
            "|---|---|\n"
            "| A | [상품](https://short.test/x) |\n\n"
            "제외: [품절](https://shop.test/products/excluded)"
        )
        payload["execution"]["evidence"].append(
            {
                "source": "https://shop.test/products/excluded",
                "finding": "품절 상태를 확인했다.",
                "kind": "web",
            }
        )

        targets = BROWSER.verification_targets(payload["execution"])

        self.assertEqual(["https://short.test/x"], targets)

    def test_sold_out_signal_wins_over_stale_price_content(self):
        dom = """
        <main><p class="text_em_lg">현재 판매중인 상품이 아닙니다.</p></main>
        <aside><span>판매가 13,520원</span><button>장바구니</button></aside>
        """

        result = BROWSER.classify_rendered_dom("https://shop.test/products/123", dom)

        self.assertEqual("sold_out", result["status"])
        self.assertIn("현재 판매중인 상품", result["signal"])

    def test_active_purchase_control_is_available(self):
        dom = '<main><button type="button">바로구매</button></main>'

        result = BROWSER.classify_rendered_dom("https://shop.test/products/123", dom)

        self.assertEqual("available", result["status"])

    def test_script_default_soldout_flag_does_not_override_purchase_button(self):
        dom = (
            "<script>data.soldout = true; data.soldout = false;</script>"
            "<main><button>주문하기</button></main>"
        )

        result = BROWSER.classify_rendered_dom("https://shop.test/products/123", dom)

        self.assertEqual("available", result["status"])

    def test_cloudflare_challenge_is_unknown(self):
        dom = "<title>잠시만 기다리십시오…</title><input name='cf-turnstile-response'>"

        result = BROWSER.classify_rendered_dom("https://shop.test/products/123", dom)

        self.assertEqual("unknown", result["status"])
        self.assertEqual("bot_challenge", result["signal"])

    def test_receipt_downgrades_sold_out_execution(self):
        def sold_out_fetcher(_url, _chrome):
            return '<main><p>현재 판매중인 상품이 아닙니다.</p></main>'

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = BROWSER.verify_execution(
                execution_payload(),
                run_dir,
                "primary-research",
                chrome_path=Path(__file__),
                fetcher=sold_out_fetcher,
            )
            receipt = json.loads(
                (run_dir / "primary-research-live-browser.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual("partial", result["execution"]["status"])
        self.assertEqual(1, receipt["counts"]["sold_out"])
        self.assertIn("검색·AI 문구보다 우선", result["execution"]["result_markdown"])
        self.assertNotIn("[상품](https://shop.test/products/123)", result["execution"]["result_markdown"])
        self.assertTrue(
            any(
                "status=sold_out" in item["finding"]
                for item in result["execution"]["evidence"]
            )
        )

    def test_sold_out_is_valid_when_request_only_asks_for_status(self):
        def sold_out_fetcher(_url, _chrome):
            return '<main><p>현재 판매중인 상품이 아닙니다.</p></main>'

        with tempfile.TemporaryDirectory() as temp_dir:
            result = BROWSER.verify_execution(
                execution_payload(),
                Path(temp_dir),
                "status-check",
                chrome_path=Path(__file__),
                fetcher=sold_out_fetcher,
                require_available=False,
            )

        self.assertEqual("completed", result["execution"]["status"])


if __name__ == "__main__":
    unittest.main()
