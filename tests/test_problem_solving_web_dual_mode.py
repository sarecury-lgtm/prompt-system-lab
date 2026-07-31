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
SPEC = importlib.util.spec_from_file_location("problem_solving_web_dual", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)


class ProblemSolvingWebDualModeTests(unittest.TestCase):
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

    def test_no_codex_renderer_returns_final_prompt(self):
        with mock.patch.object(
            WEB.problem_os,
            "CodexEngine",
            side_effect=AssertionError("Codex must not run"),
        ):
            result = WEB.render_prompt_request(self.payload())

        self.assertEqual("PROMPT · NO CODEX", result["route"])
        self.assertEqual("completed", result["execution_status"])
        self.assertIn("사용자 취향에 맞는 상품 하나", result["result_markdown"])
        self.assertIn("예산은 3만원 이하다.", result["result_markdown"])
        self.assertIn("deterministic_renderer", result["evidence"][0]["source"])
        self.assertIsNone(result["run_id"])

    def test_no_codex_renderer_rejects_missing_required_structure(self):
        payload = self.payload()
        payload["core_procedure"] = []
        with self.assertRaisesRegex(ValueError, "핵심 작업 절차"):
            WEB.render_prompt_request(payload)

        payload = self.payload()
        payload["completion_condition"] = ""
        with self.assertRaisesRegex(ValueError, "완료 조건"):
            WEB.render_prompt_request(payload)

    def test_no_codex_renderer_accepts_multiline_fields(self):
        payload = self.payload()
        payload["core_procedure"] = "후보를 비교한다.\n하나를 고른다."
        payload["fixed_constraints"] = "예산을 지킨다.\n하나만 추천한다."
        result = WEB.render_prompt_request(payload)
        self.assertIn("후보를 비교한다.", result["result_markdown"])
        self.assertIn("하나만 추천한다.", result["result_markdown"])

    def test_static_ui_exposes_both_engine_modes(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn('value="codex"', html)
        self.assertIn('value="deterministic"', html)
        self.assertIn("Codex 없는 프롬프트 생성", html)
        self.assertIn("/api/render-prompt", script)
        self.assertIn("/renderer.js", WEB.STATIC_FILES)
        self.assertIn("/renderer.css", WEB.STATIC_FILES)

    def test_fast_template_ui_uses_one_primary_input_and_honest_name(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn("빠른 템플릿 생성", script)
        self.assertIn("AI 설계 없이 공통 틀", script)
        self.assertIn("DEFAULT_CORE_PROCEDURE", script)
        self.assertIn("DEFAULT_COMPLETION", script)
        self.assertIn('rendererElements.procedure.removeAttribute("required")', script)
        self.assertIn('rendererElements.completion.removeAttribute("required")', script)
        self.assertIn("세부 설정 · 필요할 때만", script)
        self.assertIn("goal: normalizedGoal", script)

    def test_fast_template_strips_nested_prompt_creation_intent(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn("function normalizePromptGoal", script)
        self.assertIn("프롬프트(?:를|을)?", script)
        self.assertIn("프롬프트를 다시 만들라고 요구하지 않는다.", script)
        self.assertIn("normalizePromptGoal(request)", script)

    def test_fast_template_result_can_copy_or_apply_once(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn('copyButton.textContent = "복사"', script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn('applyButton.textContent = "다음 Codex 요청에 1회 적용"', script)
        self.assertIn("psos-applied-fast-template", script)
        self.assertIn("applyStoredPromptToNextCodexRequest", script)
        self.assertIn("window.localStorage.removeItem(appliedPromptStorageKey)", script)


if __name__ == "__main__":
    unittest.main()
