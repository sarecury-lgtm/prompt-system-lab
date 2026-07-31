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

    def test_browser_replaces_fast_template_with_integrated_one_call(self):
        script = (ROOT / "web" / "renderer.js").read_text(encoding="utf-8")

        self.assertIn("통합 AI 1회", script)
        self.assertIn("/api/design-prompt", script)
        self.assertIn("Goal Ledger와 Prompt Build Brief", script)
        self.assertIn("Codex 1회 · 로컬 검증 및 조립", script)
        self.assertNotIn("DEFAULT_CORE_PROCEDURE", script)
        self.assertNotIn("빠른 템플릿 생성", script)

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


if __name__ == "__main__":
    unittest.main()
