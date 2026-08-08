import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SCRIPTS))

import problem_solving_blind_handoff_web as HANDOFF


class BlindHandoffZipTests(unittest.TestCase):
    def test_builds_continuation_zip_with_request_result_and_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            attachment_root = Path(tmp) / "attachments"
            attachment_root.mkdir()
            image = attachment_root / "sample.png"
            image.write_bytes(b"fake-image-bytes")

            content, filename, manifest = HANDOFF.build_handoff_zip(
                {
                    "request": "맛있는 삼겹살 추천해줘",
                    "current_result": "집에서 먹을지 식당인지 확인이 필요합니다.",
                    "route": "CANDIDATE",
                    "run_id": "manual-1",
                    "manual_state": {
                        "latest_correction": "집에서 구워 먹을 거야",
                    },
                    "attachment_paths": [str(image)],
                },
                attachment_root=attachment_root,
            )

            self.assertTrue(filename.startswith("psos-blind-handoff-"))
            self.assertEqual(manifest["continuation"]["mode"], "same_task")
            self.assertFalse(manifest["continuation"]["reupload_each_turn"])

            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                self.assertIn("psos-handoff/00_START_HERE.md", names)
                self.assertIn("psos-handoff/STATE.md", names)
                self.assertIn("psos-handoff/conversation.md", names)
                self.assertIn("psos-handoff/manifest.json", names)
                self.assertIn("psos-handoff/attachments/sample.png", names)
                conversation = archive.read("psos-handoff/conversation.md").decode("utf-8")
                self.assertIn("맛있는 삼겹살 추천해줘", conversation)
                self.assertIn("집에서 구워 먹을 거야", conversation)
                stored = json.loads(archive.read("psos-handoff/manifest.json"))
                self.assertEqual(stored["current_request"], "맛있는 삼겹살 추천해줘")

    def test_rejects_attachment_outside_psos_attachment_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed = root / "allowed"
            allowed.mkdir()
            outside = root / "outside.png"
            outside.write_bytes(b"x")
            with self.assertRaises(HANDOFF.BlindHandoffError):
                HANDOFF.build_handoff_zip(
                    {
                        "request": "요청",
                        "attachment_paths": [str(outside)],
                    },
                    attachment_root=allowed,
                )

    def test_smart_web_loads_handoff_assets_and_endpoint(self):
        smart = (SCRIPTS / "problem_solving_quality_next_loop_smart_web.py").read_text(encoding="utf-8")
        self.assertIn("blind_handoff_support.install(web)", smart)
        self.assertIn('renderer_addons.append("psos-blind-handoff-v1.js")', smart)
        self.assertIn('style_addons.append("psos-blind-handoff-v1.css")', smart)


if __name__ == "__main__":
    unittest.main()
