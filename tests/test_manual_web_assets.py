import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManualWebAssetTests(unittest.TestCase):
    def test_copy_and_open_are_separate_and_result_is_copyable(self):
        html = (ROOT / "web" / "manual.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        self.assertIn('id="copy-prompt"', html)
        self.assertIn('id="open-chatgpt"', html)
        self.assertIn('id="copy-result"', html)
        self.assertIn('copyPromptButton.addEventListener', script)
        self.assertIn('copyResultButton.addEventListener', script)
        self.assertNotIn('send-to-chatgpt', script)

    def test_page_does_not_auto_restore_unselected_latest_completed_run(self):
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        self.assertNotIn('/api/manual/latest', script)
        self.assertNotIn('/api/manual/active', script)
        self.assertIn('psos-current-run-id', script)

    def test_extension_does_not_overwrite_or_extract_arbitrary_article(self):
        content = (
            ROOT / "extensions" / "psos-chatgpt-bridge" / "content.js"
        ).read_text(encoding="utf-8")
        popup = (
            ROOT / "extensions" / "psos-chatgpt-bridge" / "popup.js"
        ).read_text(encoding="utf-8")
        self.assertIn("작성 중인 내용이 있어 덮어쓰지 않았습니다", content)
        self.assertNotIn('querySelectorAll("main article")', content)
        self.assertIn("답변을 생성 중", content)
        self.assertIn("linkedPendingSession", popup)
        self.assertIn("clearLinkedSession", popup)


if __name__ == "__main__":
    unittest.main()
