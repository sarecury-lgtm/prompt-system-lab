import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual_web.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_manual_web_test",
    MODULE_PATH,
)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


class ManualBridgeHTTPTests(unittest.TestCase):
    def test_static_page_and_active_api_serve_over_http(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = WEB.manual.ManualBridge(
                runs_dir=Path(directory) / "runs"
            )
            configured = type(
                "TestHandler",
                (WEB.Handler,),
                {
                    "bridge": bridge,
                    "log_message": lambda self, format, *args: None,
                },
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), configured)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                with urlopen(f"http://{host}:{port}/", timeout=5) as response:
                    body = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn("ChatGPT 수동 브리지", body)

                with urlopen(
                    f"http://{host}:{port}/api/manual/active",
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    self.assertEqual(payload, {"session": None})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_trailing_markdown_link_definitions_are_removed(self):
        raw = (
            '{"execution":{"status":"completed"}}\n\n'
            '[1]: https://example.com/a "first"\n'
            '[2]: https://example.com/b "second"\n'
        )
        cleaned = WEB.strip_trailing_markdown_references(raw)
        self.assertEqual(
            cleaned,
            '{"execution":{"status":"completed"}}',
        )

    def test_unrelated_trailing_text_is_not_removed(self):
        raw = '{"execution":{}}\nThis explanation must remain invalid.'
        self.assertEqual(WEB.strip_trailing_markdown_references(raw), raw)


if __name__ == "__main__":
    unittest.main()
