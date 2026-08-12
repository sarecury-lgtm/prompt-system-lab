import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_web_attachments as ATTACHMENTS


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def png_item(name: str = "chart.png") -> dict:
    encoded = base64.b64encode(PNG_BYTES).decode("ascii")
    return {
        "name": name,
        "type": "image/png",
        "data_url": f"data:image/png;base64,{encoded}",
    }


class WebAttachmentTests(unittest.TestCase):
    def test_store_attachments_writes_image_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            stored = ATTACHMENTS.store_attachments(
                {"files": [png_item("my chart.png")]},
                root=Path(directory),
            )
            self.assertEqual(1, len(stored))
            path = Path(stored[0]["path"])
            self.assertTrue(path.is_file())
            self.assertEqual(PNG_BYTES, path.read_bytes())
            manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, manifest["attachments"])

    def test_rejects_mime_mismatch(self):
        item = png_item()
        item["type"] = "image/jpeg"
        item["data_url"] = "data:image/jpeg;base64," + base64.b64encode(PNG_BYTES).decode("ascii")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ATTACHMENTS.AttachmentError, "실제 이미지 형식"):
                ATTACHMENTS.store_attachments(
                    {"files": [item]},
                    root=Path(directory),
                )

    def test_rejects_more_than_four_images(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ATTACHMENTS.AttachmentError, "최대 4장"):
                ATTACHMENTS.store_attachments(
                    {"files": [png_item(f"chart-{index}.png") for index in range(5)]},
                    root=Path(directory),
                )


if __name__ == "__main__":
    unittest.main()
