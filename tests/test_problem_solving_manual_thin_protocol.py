from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
THIN = ROOT / "web" / "psos-manual-thin-v1.js"
SMART_WEB = ROOT / "scripts" / "problem_solving_quality_next_loop_smart_web.py"


class ManualThinProtocolTests(unittest.TestCase):
    def test_thin_adapter_keeps_native_problem_solving_and_key_guardrails(self):
        text = THIN.read_text(encoding="utf-8")
        self.assertIn("정해진 워크플로를 수행하거나 내부 구조를 설명하는 것이 목적이 아니라", text)
        self.assertIn("질문을 한 번으로 끝낼 필요는 없습니다", text)
        self.assertIn("특정 브랜드·품종·제품군의 선호로 바로 치환하지 말고", text)
        self.assertIn("사용자 목적/선호 → 후보의 관련 특성 → 근거 → 주요 대안보다 적합한 이유", text)
        self.assertIn("구체적인 다음 행동 1~2개", text)
        self.assertNotIn("[PSOS Job Packet]", text)

    def test_thin_adapter_wraps_legacy_instead_of_deleting_it(self):
        text = THIN.read_text(encoding="utf-8")
        self.assertIn("window.PSOSManualProtocolLegacy = legacy", text)
        self.assertIn("...legacy", text)
        self.assertIn("buildExecutionPrompt: buildThinExecutionPrompt", text)
        self.assertIn("buildContinuationPrompt: buildThinContinuationPrompt", text)

    def test_loader_places_thin_adapter_before_manual_fallback(self):
        text = SMART_WEB.read_text(encoding="utf-8")
        protocol = text.index('renderer_addons.append("psos-manual-protocol.js")')
        thin = text.index('renderer_addons.append("psos-manual-thin-v1.js")')
        fallback = text.index('renderer_addons.append("chatgpt-manual-fallback-v5.js")')
        self.assertLess(protocol, thin)
        self.assertLess(thin, fallback)

    def test_strict_controller_ui_does_not_hijack_default_manual_toggle(self):
        text = SMART_WEB.read_text(encoding="utf-8")
        self.assertNotIn('renderer_addons.append("psos-manual-controller-v1.js")', text)
        self.assertNotIn('renderer_addons.append("psos-manual-verification-v1.js")', text)
        self.assertNotIn('renderer_addons.append("psos-manual-refinement-v1.js")', text)
        self.assertIn("manual_controller_support.install(web)", text)


if __name__ == "__main__":
    unittest.main()
