import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManualWebAssetTests(unittest.TestCase):
    def test_copy_and_open_are_separate_and_result_is_copyable(self):
        html = (ROOT / "web" / "manual.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        actions = (ROOT / "web" / "manual_result_actions.js").read_text(
            encoding="utf-8"
        )
        action_styles = (ROOT / "web" / "manual_result_actions.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="copy-prompt"', html)
        self.assertIn('id="open-chatgpt"', html)
        self.assertIn('id="copy-result"', html)
        self.assertIn("copyPromptButton.addEventListener", script)
        self.assertIn("copyResultButton.addEventListener", script)
        self.assertIn("output_markdown", script)
        self.assertIn("result-copy-card", action_styles)
        self.assertIn("result-copy", actions)
        self.assertNotIn("send-to-chatgpt", script)

    def test_prompt_brief_and_final_require_separate_new_chats(self):
        html = (ROOT / "web" / "manual.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "manual_prompt_brief.js").read_text(
            encoding="utf-8"
        )
        server = (
            ROOT / "scripts" / "problem_solving_manual_web.py"
        ).read_text(encoding="utf-8")

        self.assertIn('/manual_prompt_brief.js', html)
        self.assertIn('phase.endsWith("_prompt_brief")', script)
        self.assertIn('phase.endsWith("_prompt_final")', script)
        self.assertGreaterEqual(script.count("새 ChatGPT 채팅"), 2)
        self.assertIn("다시 새 채팅", script)
        self.assertIn('"/manual_prompt_brief.js"', server)

    def test_page_does_not_auto_restore_unselected_latest_completed_run(self):
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        self.assertNotIn("/api/manual/latest", script)
        self.assertNotIn("/api/manual/active", script)
        self.assertIn("psos-current-run-id", script)


if __name__ == "__main__":
    unittest.main()
