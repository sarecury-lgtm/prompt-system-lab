import importlib.util
import json
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
            [
                "next-loop-workflow.js",
                "psos-manual-protocol.js",
                "psos-manual-route-policy.js",
                "chatgpt-manual-fallback-v5.js",
                "chatgpt-manual-focus-v1.js",
                "psos-manual-controller-v1.js",
                "psos-manual-request-switch-v1.js",
                "psos-manual-verification-v1.js",
                "psos-manual-refinement-v1.js",
                "chatgpt-manual-patch-v1.js",
            ],
            addons["renderer.js"],
        )
        self.assertIn("next-loop-attachments.css", addons["styles.css"])
        self.assertIn("psos-manual-controller-v1.css", addons["styles.css"])
        self.assertIn("psos-manual-request-switch-v1.css", addons["styles.css"])
        self.assertIn("psos-manual-verification-v1.css", addons["styles.css"])
        self.assertIn("psos-manual-refinement-v1.css", addons["styles.css"])
        self.assertEqual("chatgpt-manual-patch-v1.css", addons["styles.css"][-1])

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

    def test_manual_protocol_builds_job_packet_and_imports_envelope(self):
        script = (ROOT / "web" / "psos-manual-protocol.js").read_text(encoding="utf-8")
        for marker in (
            "PSOS Job Packet",
            "goal_ledger_task",
            "execution_contract",
            "quality_gates",
            "completion_rule",
            "PSOS_RESULT_ENVELOPE_START",
            "parseResultEnvelope",
            "buildContinuationPrompt",
            "PSOSManualProtocol",
            "version: 1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn('fetch("/api/', script)

    def test_manual_route_policy_prioritizes_specific_decisions(self):
        script = (ROOT / "web" / "psos-manual-route-policy.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "decisionAction",
            "broadSearch",
            'return "DECISION"',
            "base.inferRoute",
            "PSOSManualProtocol",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_legacy_manual_ui_remains_as_hidden_fallback(self):
        script = (ROOT / "web" / "chatgpt-manual-fallback-v5.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "ChatGPT 수동 실행",
            'id="manual-v5-request"',
            "실행 패킷 복사",
            "결과 가져오기",
            "한 번 더 고치기",
            "PSOSManualChatGPT",
            "version: 5",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_manual_focus_hides_unrelated_engines_and_marks_completion(self):
        script = (ROOT / "web" / "chatgpt-manual-focus-v1.js").read_text(
            encoding="utf-8"
        )
        styles = (ROOT / "web" / "chatgpt-manual-focus-v1.css").read_text(
            encoding="utf-8"
        )
        for marker in (
            ".engine-selector",
            ".workspace > .section-heading",
            "수동 실행 완료",
            "새 요청 시작",
            "PSOSManualFocus",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertIn("body.manual-v5-enabled .engine-selector", styles)
        self.assertIn("manual-v5-focus-note", styles)

    def test_manual_controller_ui_uses_server_owned_next_action(self):
        script = (ROOT / "web" / "psos-manual-controller-v1.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            "같은 Controller · 수동 전송",
            "/api/manual-controller/sessions",
            "현재 행동 패킷 복사",
            "결과를 Controller에 제출",
            "awaiting_user_input",
            "used_method_changes",
            "PSOSManualController",
            "version: 1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn("api.openai.com", script)

    def test_manual_request_switch_is_visible_for_restored_sessions(self):
        script = (ROOT / "web" / "psos-manual-request-switch-v1.js").read_text(
            encoding="utf-8"
        )
        styles = (ROOT / "web" / "psos-manual-request-switch-v1.css").read_text(
            encoding="utf-8"
        )
        for marker in (
            "요청 바꾸기",
            "현재 요청",
            "manual-controller-reset",
            "getSession",
            "PSOSManualRequestSwitch",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertIn("manual-controller-head-actions", styles)
        self.assertIn("manual-controller-current-request", styles)

    def test_manual_verification_ui_shows_failures_and_next_action(self):
        script = (ROOT / "web" / "psos-manual-verification-v1.js").read_text(
            encoding="utf-8"
        )
        styles = (ROOT / "web" / "psos-manual-verification-v1.css").read_text(
            encoding="utf-8"
        )
        for marker in (
            "Controller 검증 실패",
            "missing_conditions",
            "last_verification",
            "request_contract",
            "current_action",
            "PSOSManualVerification",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertIn("manual-controller-verification-next", styles)

    def test_manual_refinement_collects_reason_and_direction(self):
        script = (ROOT / "web" / "psos-manual-refinement-v1.js").read_text(
            encoding="utf-8"
        )
        styles = (ROOT / "web" / "psos-manual-refinement-v1.css").read_text(
            encoding="utf-8"
        )
        for marker in (
            "결과에 의견 반영하기",
            "왜 바꾸려는지",
            "다음에는 어떤 방향으로 갈지",
            "/refine",
            "controller.reload",
            "PSOSManualRefinement",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)
        self.assertIn("body.manual-controller-enabled #manual-v5-continue-current", styles)
        self.assertIn("manual-controller-refinement-form", styles)

    def test_manual_contract_schemas_are_valid_json(self):
        job_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-manual-job-packet.schema.json").read_text(
                encoding="utf-8"
            )
        )
        result_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-manual-result-envelope.schema.json").read_text(
                encoding="utf-8"
            )
        )
        action_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-controller-action.schema.json").read_text(
                encoding="utf-8"
            )
        )
        action_result_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-controller-action-result.schema.json").read_text(
                encoding="utf-8"
            )
        )
        session_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-controller-session.schema.json").read_text(
                encoding="utf-8"
            )
        )
        request_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-request-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        obligation_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-evidence-obligation.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("PSOS Manual Job Packet", job_schema["title"])
        self.assertEqual("PSOS Manual Result Envelope", result_schema["title"])
        self.assertEqual("PSOS Controller Action Packet", action_schema["title"])
        self.assertEqual("PSOS Controller Action Result", action_result_schema["title"])
        self.assertEqual("PSOS Controller Session State", session_schema["title"])
        self.assertEqual("PSOS Request Contract", request_schema["title"])
        self.assertEqual("PSOS Evidence Obligation", obligation_schema["title"])
        self.assertIn("request_contract", action_schema["required"])
        self.assertIn("coverage", action_result_schema["required"])
        self.assertIn("continuation", result_schema["required"])

    def test_workflow_styles_hide_legacy_manual_and_show_controller(self):
        styles = (ROOT / "web" / "next-loop-workflow.css").read_text(encoding="utf-8")
        fallback_styles = (ROOT / "web" / "chatgpt-manual-fallback-v5.css").read_text(
            encoding="utf-8"
        )
        controller_styles = (ROOT / "web" / "psos-manual-controller-v1.css").read_text(
            encoding="utf-8"
        )
        attachment_styles = (ROOT / "web" / "next-loop-attachments.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("body.workflow-auto:not(.workflow-show-advanced)", styles)
        self.assertIn("manual-current-step", styles)
        self.assertIn("manual-v5-request-label", fallback_styles)
        self.assertIn("manual-v5-progress", fallback_styles)
        self.assertIn("body:not(.workflow-show-advanced) #manual-panel", fallback_styles)
        self.assertIn("body.manual-controller-enabled #chatgpt-manual-panel", controller_styles)
        self.assertIn("manual-controller-budget", controller_styles)
        self.assertIn("attachment-dropzone", attachment_styles)


if __name__ == "__main__":
    unittest.main()
