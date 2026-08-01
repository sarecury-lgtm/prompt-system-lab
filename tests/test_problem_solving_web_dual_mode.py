import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "problem_solving_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_web_modes", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


class ProblemSolvingWebModeTests(unittest.TestCase):
    def payload(self):
        return {
            "goal": "사용자 취향에 맞는 상품 하나를 추천한다.",
            "core_procedure": [
                "후보를 취향과 예산에 맞춰 비교한다.",
                "가장 적합한 후보와 결론이 바뀌는 조건을 정한다.",
            ],
            "fixed_constraints": [
                "예산은 3만원 이하다.",
                "하나의 후보를 최종 추천한다.",
            ],
            "completion_condition": "사용자가 바로 선택할 수 있는 추천이 제시된다.",
            "supporting_inputs": ["후보별 가격과 반복되는 실제 사용 경험"],
            "output_details": ["핵심 근거와 가장 큰 위험을 짧게 밝힌다."],
            "defaults_and_exceptions": [],
            "exclusions": [],
            "upstream_context": [],
        }

    def test_existing_local_renderer_still_works_without_codex(self):
        with mock.patch.object(
            WEB.problem_os,
            "CodexEngine",
            side_effect=AssertionError("Codex must not run"),
        ):
            result = WEB.render_prompt_request(self.payload())

        self.assertEqual("PROMPT · NO CODEX", result["route"])
        self.assertIn("사용자 취향에 맞는 상품 하나", result["result_markdown"])

    def test_comparison_overlay_shows_integrated_final_editing_process(self):
        script = (ROOT / "web" / "compare-no-codex.js").read_text(encoding="utf-8")

        self.assertIn("통합 AI 1회 · 최종 편집 포함", script)
        self.assertIn("1. 원래 요청", script)
        self.assertIn("설계와 최종 작성을 한 번에 하는 지시문", script)
        self.assertIn("3. ChatGPT 답변 전체 붙여넣기", script)
        self.assertIn("4. 최종 프롬프트 추출", script)
        self.assertIn("integrated-instruction-preview", script)
        self.assertIn("중복과 메타 정보를 버린 최종 프롬프트까지 직접 작성", script)
        self.assertIn("integrated_design: integratedDesign", script)
        self.assertIn("AI 작성 최종 프롬프트 검증·추출 완료", script)
        self.assertIn('"final_prompt"', script)
        self.assertNotIn("CodexEngine", script)

    def test_integrated_final_editing_avoids_three_observed_failure_modes(self):
        script = (ROOT / "web" / "compare-no-codex.js").read_text(encoding="utf-8")

        self.assertIn("근거도 정의되지 않은 신뢰도 등급·점수·백분율", script)
        self.assertIn("서로 다른 판단 축을 하나의 선택지 목록에 섞지 말고", script)
        self.assertIn("누락된 기간·성향·기준을 처리할 때 임의의 고정값", script)
        self.assertIn("제공된 입력 구성을 바탕으로 추정", script)

    def test_integrated_preview_updates_from_original_request(self):
        script = (ROOT / "web" / "compare-no-codex.js").read_text(encoding="utf-8")

        self.assertIn('requestField.addEventListener("input", refreshInstructionPreview)', script)
        self.assertIn("instructionUi.preview.value = request ? integratedInstruction(request)", script)
        self.assertIn("통합 제작 지시문을 복사했습니다", script)
        self.assertIn("final_prompt는 복사해 바로 실행할 완성된 프롬프트", script)

    def test_copy_feedback_and_chatgpt_shortcut_are_visible(self):
        script = (ROOT / "web" / "compare-no-codex.js").read_text(encoding="utf-8")

        self.assertIn("복사됨 ✓", script)
        self.assertIn("복사하고 ChatGPT 새 채팅 열기", script)
        self.assertIn('const chatGptNewChatUrl = "https://chatgpt.com/"', script)
        self.assertIn("window.open(chatGptNewChatUrl", script)
        self.assertIn("Ctrl+V로 붙여넣으세요", script)
        self.assertIn('document.addEventListener("click"', script)
        self.assertIn('status.setAttribute("aria-live", "polite")', script)

    def test_comparison_ui_shows_only_the_combined_copy_action(self):
        stylesheet = (ROOT / "web" / "renderer.css").read_text(encoding="utf-8")

        for control_id in (
            "#copy-blind-a",
            "#copy-blind-b",
            "#reshuffle-blind-map",
            "#reveal-blind-map",
        ):
            self.assertIn(control_id, stylesheet)
        self.assertIn("display: none !important", stylesheet)
        self.assertIn("두 결과를 한 번에 복사해 ChatGPT에 붙여 비교합니다.", stylesheet)
        self.assertIn("white-space: nowrap", stylesheet)

    def test_integrated_json_field_uses_full_width(self):
        stylesheet = (ROOT / "web" / "renderer.css").read_text(encoding="utf-8")

        self.assertIn(".integrated-json-label", stylesheet)
        self.assertIn("grid-column: 1 / -1", stylesheet)
        self.assertIn(".integrated-flow-guide", stylesheet)

    def test_manual_four_stage_mode_is_preserved(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn('value="manual"', script)
        self.assertIn("수동 PSOS 4단계", script)
        self.assertIn("1단계 라우터 지시문 복사", script)
        self.assertIn("2단계 Brief 컴파일러 복사", script)
        self.assertIn("3단계 최종 실행기 복사", script)
        self.assertIn("수동 PSOS 최종 프롬프트", script)

    def test_two_final_prompts_can_be_copied_together(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn("두 결과 같이 복사", script)
        self.assertIn("combinedComparisonText", script)
        self.assertIn("# 통합 AI 1회 결과", script)
        self.assertIn("# 수동 PSOS 4단계 결과", script)
        self.assertIn("두 결과를 한 번에 복사했습니다.", script)

    def test_compare_server_injects_no_codex_overlay(self):
        source = (ROOT / "scripts" / "problem_solving_compare_web.py").read_text(encoding="utf-8")
        self.assertIn("compare-no-codex.js", source)
        self.assertIn("Codex 호출 없음", source)
        self.assertIn("AI가 직접 작성한 final_prompt", source)


if __name__ == "__main__":
    unittest.main()
