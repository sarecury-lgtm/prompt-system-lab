import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_quality_next_loop_smart_web.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_quality_next_loop_smart_web",
    MODULE_PATH,
)
SMART = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = SMART
SPEC.loader.exec_module(SMART)


class QualityNextLoopSmartWebTests(unittest.TestCase):
    def test_smart_assets_are_built_without_mutating_base_assets(self):
        before = {name: list(values) for name, values in SMART.web.STATIC_ADDONS.items()}
        addons = SMART.build_static_addons()

        self.assertEqual(before, SMART.web.STATIC_ADDONS)
        self.assertEqual(
            [
                "quality-review.js",
                "next-loop-attachments.js",
                "next-loop.js",
                "next-loop-details.js",
            ],
            addons["app.js"],
        )
        self.assertEqual(
            ["next-loop-workflow.js", "chatgpt-manual-fallback-v2.js"],
            addons["renderer.js"],
        )
        self.assertIn("next-loop-attachments.css", addons["styles.css"])
        self.assertEqual("chatgpt-manual-fallback.css", addons["styles.css"][-1])

    def test_workflow_script_exposes_auto_routes_and_manual_diagnostics(self):
        script = (ROOT / "web" / "next-loop-workflow.js").read_text(encoding="utf-8")
        for marker in (
            "일반 해결",
            "최신 조사",
            "후보 비교",
            "프롬프트 제작",
            "파일 변경",
            "PSOSWorkflowRouter",
            "manual-progress",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_attachment_script_supports_picker_paste_and_drop(self):
        script = (ROOT / "web" / "next-loop-attachments.js").read_text(encoding="utf-8")
        for marker in (
            "/api/attachments",
            "차트·스크린샷 첨부",
            'addEventListener("paste"',
            'addEventListener("drop"',
            "PSOSAttachments",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_manual_chatgpt_fallback_has_no_api_engine_dependency_or_observer_loop(self):
        script = (ROOT / "web" / "chatgpt-manual-fallback-v2.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "Codex 없이 사용",
            "https://chatgpt.com/",
            "buildInitialPacket",
            "buildContinuationPacket",
            "일반 ChatGPT로 계속",
            "PSOSManualChatGPT",
            "fallbackButton.hidden !== shouldHide",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        for forbidden in (
            "OPENAI_API_KEY",
            "api.openai.com",
            'fetch("/api/',
            'observe(errorPanel, {\n    attributes: true,\n    attributeFilter: ["hidden"],\n    childList: true,\n    subtree: true',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)

    def test_workflow_styles_hide_advanced_controls_only_in_auto_mode(self):
        styles = (ROOT / "web" / "next-loop-workflow.css").read_text(encoding="utf-8")
        fallback_styles = (ROOT / "web" / "chatgpt-manual-fallback.css").read_text(
            encoding="utf-8"
        )
        attachment_styles = (ROOT / "web" / "next-loop-attachments.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("body.workflow-auto:not(.workflow-show-advanced)", styles)
        self.assertIn("manual-current-step", styles)
        self.assertIn("chatgpt-manual-panel", fallback_styles)
        self.assertIn("attachment-dropzone", attachment_styles)


if __name__ == "__main__":
    unittest.main()
