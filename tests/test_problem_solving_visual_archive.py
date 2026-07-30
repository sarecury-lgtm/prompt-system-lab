import hashlib
import importlib.util
import io
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_visual_archive.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_visual_archive", MODULE_PATH)
ARCHIVE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ARCHIVE
SPEC.loader.exec_module(ARCHIVE)


PNG = b"\x89PNG\r\n\x1a\n" + b"fixture-image"


class FakeResponse:
    def __init__(self, content, *, media_type="image/png", content_length=None):
        self._stream = io.BytesIO(content)
        self.headers = Message()
        self.headers["Content-Type"] = media_type
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self, amount):
        return self._stream.read(amount)


class VisualArchiveTests(unittest.TestCase):
    def test_rejects_local_private_and_credential_urls(self):
        for url in (
            "http://127.0.0.1/photo.png",
            "http://10.0.0.2/photo.png",
            "http://[::1]/photo.png",
            "https://user:secret@example.com/photo.png",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ARCHIVE.VisualArchiveError):
                    ARCHIVE.validate_public_http_url(url)

    def test_hostname_resolution_must_be_globally_routable(self):
        with mock.patch.object(
            ARCHIVE.socket,
            "getaddrinfo",
            return_value=[(None, None, None, None, ("192.168.1.2", 443))],
        ):
            with self.assertRaisesRegex(ARCHIVE.VisualArchiveError, "사설"):
                ARCHIVE.validate_public_http_url("https://images.example.test/photo.png")

    def test_magic_detection_and_declared_size_limit(self):
        self.assertEqual("image/png", ARCHIVE._detect_media_type(PNG))
        self.assertIsNone(ARCHIVE._detect_media_type(b"<html>not an image</html>"))
        response = FakeResponse(PNG, content_length=1000)
        with self.assertRaisesRegex(ARCHIVE.VisualArchiveError, "크기"):
            ARCHIVE._read_limited(response, 100)

    def test_archive_writes_content_addressed_file_and_deduplicates_url(self):
        calls = []

        def downloader(url, remaining):
            calls.append((url, remaining))
            return {
                "content": PNG,
                "media_type": "image/png",
                "final_url": url,
            }

        images = [
            {"src": "https://cdn.example.test/photo.png"},
            {"src": "https://cdn.example.test/photo.png"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = ARCHIVE.archive_selected_images(
                run_dir,
                images,
                downloader=downloader,
            )
            record = result[images[0]["src"]]
            archived = run_dir / record["path"]
            content = archived.read_bytes()

        digest = hashlib.sha256(PNG).hexdigest()
        self.assertEqual(1, len(calls))
        self.assertEqual("archived", record["status"])
        self.assertEqual(digest, record["sha256"])
        self.assertEqual(PNG, content)
        self.assertTrue(record["path"].endswith(f"{digest}.png"))

    def test_archive_failure_is_explicit_and_does_not_create_file(self):
        def downloader(_url, _remaining):
            raise ARCHIVE.VisualArchiveError("hotlink 차단")

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = ARCHIVE.archive_selected_images(
                run_dir,
                [{"src": "https://cdn.example.test/blocked.jpg"}],
                downloader=downloader,
            )
            files = list(run_dir.rglob("*"))

        record = result["https://cdn.example.test/blocked.jpg"]
        self.assertEqual("unavailable", record["status"])
        self.assertIn("hotlink", record["error"])
        self.assertEqual([], files)


if __name__ == "__main__":
    unittest.main()
