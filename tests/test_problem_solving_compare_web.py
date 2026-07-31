import importlib.util
import sys
import unittest
from pathlib import Path


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


class FakeEngine:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def execute(self, prompt, run_dir, invocation):
        self.calls.append((prompt, run_dir, invocation))
        return self.payload

    def trace(self):
        return [{"model": "fake-one-call-model"}]


class ProblemSolvingCompareWebTests(unittest.TestCase):
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
        }

    def test_one_model_call_then_local_render(self):
        engine = FakeEngine(self.design_payload())
        result = COMPARE.design_prompt_request(
            {"request": "차트 분석 프롬프트를 만들어 줘"},
            engine=engine,
        )

        self.assertEqual(1, len(engine.calls))
        self.assertEqual(1, result["model_call_count"])
        self.assertEqual("PROMPT · AI 1회", result["route"])
        self.assertIn("상위 시간대부터 추세", result["result_markdown"])
        self.assertIn("fake-one-call-model", result["evidence"][0]["finding"])
        self.assertEqual("PROMPT", result["goal_ledger"]["selected_route"])

    def test_integrated_prompt_requests_both_logical_outputs(self):
        prompt = COMPARE.build_integrated_design_prompt("상품 비교 프롬프트를 만들어 줘")

        self.assertIn("Goal Ledger", prompt)
        self.assertIn("Prompt Build Brief", prompt)
        self.assertIn("한 번만 분석", prompt)
        self.assertIn("범용 절차로 끝내지 않는다", prompt)
        self.assertIn("selected_route는 반드시 PROMPT", prompt)

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


if __name__ == "__main__":
    unittest.main()
