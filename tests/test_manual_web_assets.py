# CI probe for the manual PROMPT structure comparison flow.

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
        self.assertIn('session.output_markdown || session.result_markdown', script)
        self.assertNotIn('send-to-chatgpt', script)

    def test_page_does_not_auto_restore_unselected_latest_completed_run(self):
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        self.assertNotIn('/api/manual/latest', script)
        self.assertNotIn('/api/manual/active', script)
        self.assertIn('psos-current-run-id', script)

    def test_prompt_comparison_uses_new_chats_and_separate_endpoints(self):
        html = (ROOT / "web" / "manual.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "manual.js").read_text(encoding="utf-8")
        server = (
            ROOT / "scripts" / "problem_solving_manual_web.py"
        ).read_text(encoding="utf-8")
        self.assertIn('id="compare-prompt"', html)
        self.assertIn('id="back-to-parent"', html)
        self.assertIn('session_kind === "prompt_ablation"', script)
        self.assertIn('반드시 새 ChatGPT 채팅', script)
        self.assertIn('/api/manual/prompt-ablation/start', script)
        self.assertIn('/api/manual/prompt-ablation/submit', script)
        self.assertIn('/api/manual/prompt-ablation/start', server)
        self.assertIn('/api/manual/prompt-ablation/submit', server)

    def test_extension_does_not_overwrite_or_extract_arbitrary_or_old_reply(self):
        content = (
            ROOT / "extensions" / "psos-chatgpt-bridge" / "content.js"
        ).read_text(encoding="utf-8")
        popup = (
            ROOT / "extensions" / "psos-chatgpt-bridge" / "popup.js"
        ).read_text(encoding="utf-8")
        self.assertIn("작성 중인 내용이 있어 덮어쓰지 않았습니다", content)
        self.assertNotIn('querySelectorAll("main article")', content)
        self.assertIn("답변을 생성 중", content)
        self.assertIn("이 PSOS 지시문 이후에 생성된 새 ChatGPT 답변", content)
        self.assertIn("assistantBaseline", content)
        self.assertIn("psosAssistantBaseline", popup)
        self.assertIn("linkedPendingSession", popup)
        self.assertIn("clearLinkedSession", popup)


if __name__ == "__main__":
    unittest.main()
