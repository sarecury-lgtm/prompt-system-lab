import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "problem_solving_compare_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_compare_web", MODULE_PATH)
COMPARE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = COMPARE
SPEC.loader.exec_module(COMPARE)


class ProblemSolvingCompareWebTests(unittest.TestCase):
    def final_prompt(self):
        return """당신은 주식·ETF·암호화폐의 다중 시간대 차트를 분석하는 매매 판단 보조자다.

첨부된 차트를 상위 시간대부터 검토해 추세, 가격 구조, 거래량, 지지·저항을 종합한다.

## 분석 절차
1. 상위 시간대의 추세와 주요 가격대를 확인한다.
2. 시간대별 신호 충돌과 현재 가격의 위치를 비교한다.
3. 구조적 무효화 조건을 먼저 정하고 손절을 배치한다.
4. 저항과 손익비를 기준으로 분할익절 계획을 만든다.

## 출력
즉시 진입, 조건부 진입, 대기 중 하나를 고르고 핵심 근거, 손절, 분할익절을 제시한다.
차트에서 확인되지 않는 가격은 만들지 않는다."""

    def design_payload(self):
        completion = "사용자가 바로 실행할 수 있는 매매 판단 프롬프트가 제공된다."
        constraints = [
            "차트에서 확인되지 않는 가격을 만들지 않는다.",
            "하나의 현재 판단을 분명히 제시한다.",
        ]
        return {
            "goal_ledger": {
                "parent_goal": "다중 시간대 차트로 매매 계획을 세운다.",
                "current_goal_hypothesis": "첨부 차트를 분석해 진입·손절·분할익절을 판단한다.",
                "fixed_constraints": constraints,
                "current_position": "재사용할 차트 분석 프롬프트가 아직 없다.",
                "selected_route": "PROMPT",
                "secondary_route": None,
                "route_reason": "반복 실행할 지침 자체가 산출물이다.",
                "current_step": "차트 분석의 도메인 절차와 출력 계약을 설계한다.",
                "why_this_step_matters": "범용 절차만으로는 매매 판단이 일관되지 않기 때문이다.",
                "completion_condition": completion,
                "important_uncertainties": ["첨부 차트 시간대 구성"],
            },
            "prompt_build_brief": {
                "version": 1,
                "goal": "여러 시간대 차트를 분석해 진입·손절·분할익절 계획을 만든다.",
                "core_procedure": [
                    "상위 시간대부터 추세와 주요 지지·저항을 확인한다.",
                    "시간대별 신호 충돌과 현재 가격의 위치를 비교한다.",
                    "가격 구조의 무효화 조건을 먼저 정하고 손절을 배치한다.",
                    "저항과 손익비를 기준으로 분할익절 계획을 만든다.",
                ],
                "supporting_inputs": ["첨부된 여러 시간대 차트", "보유 정보와 평균 진입가"],
                "fixed_constraints": constraints,
                "output_contract": [
                    completion,
                    "즉시 진입·조건부 진입·대기 중 하나를 선택한다.",
                ],
                "defaults_and_exceptions": [
                    "보유 정보가 없으면 신규 진입 관점으로 판단한다."
                ],
                "exclusions": ["실시간 시세를 임의로 가정하지 않는다."],
                "upstream_context": [],
            },
            "final_prompt": self.final_prompt(),
        }

    def test_pasted_one_ai_result_extracts_ai_final_prompt_without_codex(self):
        with mock.patch.object(
            COMPARE.problem_os,
            "CodexEngine",
            side_effect=AssertionError("Codex must not run"),
        ), mock.patch.object(
            COMPARE.prompt_renderer,
            "render_prompt",
            side_effect=AssertionError("local renderer must not rewrite final prompt"),
        ):
            result = COMPARE.design_prompt_request(
                {
                    "request": "차트 분석 프롬프트를 만들어 줘",
                    "integrated_design": json.dumps(self.design_payload(), ensure_ascii=False),
                }
            )

        self.assertEqual(0, result["codex_call_count"])
        self.assertEqual(0, result["model_call_count"])
        self.assertEqual(1, result["external_ai_round_trip_count"])
        self.assertEqual("PROMPT · AI 왕복 1회 · CODEX 0회", result["route"])
        self.assertEqual(self.final_prompt(), result["result_markdown"])
        self.assertIn("AI가 직접 작성한 final_prompt", result["evidence"][0]["finding"])

    def test_integrated_prompt_requests_design_and_final_prompt(self):
        prompt = COMPARE.build_integrated_design_prompt("상품 비교 프롬프트를 만들어 줘")

        self.assertIn("Goal Ledger", prompt)
        self.assertIn("Prompt Build Brief", prompt)
        self.assertIn("최종 프롬프트", prompt)
        self.assertIn("final_prompt", prompt)
        self.assertIn("한 번만 분석", prompt)
        self.assertIn("제작 과정의 명칭이나 설명을 넣지 않는다", prompt)
        self.assertIn("selected_route는 반드시 PROMPT", prompt)

    def test_parser_accepts_markdown_json_fence(self):
        text = "```json\n" + json.dumps(self.design_payload(), ensure_ascii=False) + "\n```"
        parsed = COMPARE.parse_integrated_design(text)
        self.assertEqual("PROMPT", parsed["goal_ledger"]["selected_route"])
        self.assertEqual(self.final_prompt(), parsed["final_prompt"])

    def test_validation_rejects_constraint_mismatch(self):
        payload = self.design_payload()
        payload["prompt_build_brief"]["fixed_constraints"] = ["다른 조건"]

        with self.assertRaisesRegex(ValueError, "fixed_constraints"):
            COMPARE.validate_integrated_design(payload)

    def test_validation_rejects_non_prompt_route(self):
        payload = self.design_payload()
        payload["goal_ledger"]["selected_route"] = "DIRECT"

        with self.assertRaisesRegex(ValueError, "PROMPT"):
            COMPARE.validate_integrated_design(payload)

    def test_validation_requires_final_prompt(self):
        payload = self.design_payload()
        del payload["final_prompt"]

        with self.assertRaisesRegex(ValueError, "최상위 필드"):
            COMPARE.validate_integrated_design(payload)

    def test_validation_rejects_meta_design_markers_in_final_prompt(self):
        payload = self.design_payload()
        payload["final_prompt"] += "\n\nPrompt Build Brief를 바탕으로 작성했다."

        with self.assertRaisesRegex(ValueError, "제작 단계"):
            COMPARE.validate_integrated_design(payload)

    def test_compare_runtime_source_does_not_invoke_codex_or_local_render(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("CodexEngine(", source)
        self.assertNotIn("active_engine.execute", source)
        self.assertNotIn("prompt_renderer.render_prompt(", source)
        self.assertIn("zero Codex calls", source)


if __name__ == "__main__":
    unittest.main()
