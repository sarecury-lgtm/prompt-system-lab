import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_prompt_renderer as RENDERER  # noqa: E402


class DeterministicPromptRendererTests(unittest.TestCase):
    def ledger(self):
        return {
            "fixed_constraints": [
                "예산은 3만원 이하다.",
                "하나의 후보를 최종 추천한다.",
            ],
            "completion_condition": "사용자가 바로 선택할 수 있는 최종 추천이 제시된다.",
        }

    def brief(self):
        return {
            "version": 1,
            "goal": "사용자 취향과 실패 위험을 함께 고려해 상품 하나를 추천한다.",
            "core_procedure": [
                "후보를 사용자 취향과 예산에 맞춰 비교한다.",
                "가장 적합한 후보와 결론이 바뀌는 조건을 정한다.",
            ],
            "supporting_inputs": ["후보별 가격과 반복되는 실제 사용 경험"],
            "fixed_constraints": [
                "예산은 3만원 이하다.",
                "하나의 후보를 최종 추천한다.",
            ],
            "output_contract": [
                "사용자가 바로 선택할 수 있는 최종 추천이 제시된다.",
                "핵심 근거와 가장 큰 실패 위험을 짧게 밝힌다.",
            ],
            "defaults_and_exceptions": [
                "결론을 바꿀 정보가 없을 때는 추가 질문 없이 진행한다."
            ],
            "exclusions": ["후보를 나열만 하고 결론을 피하지 않는다."],
            "upstream_context": [],
        }

    def test_renderer_includes_substantive_goal_aware_contract(self):
        policy = "사용자의 실제 결과를 우선한다.\n추천은 근거로 독립적으로 판단한다."
        prompt = RENDERER.render_prompt(self.brief(), self.ledger(), policy)

        self.assertIn("# 역할과 목표", prompt)
        self.assertIn("사용자 취향과 실패 위험", prompt)
        self.assertIn("추천은 근거로 독립적으로 판단한다.", prompt)
        self.assertIn("하나의 후보를 최종 추천한다.", prompt)
        self.assertIn("결론이 바뀌는 조건", prompt)
        self.assertIn("같은 결론을 더 길게 표현하는 것을 개선으로 간주하지 않는다.", prompt)
        self.assertNotIn("## 검증된 상위 맥락", prompt)

    def test_renderer_accepts_nine_distinct_domain_steps(self):
        brief = self.brief()
        brief["core_procedure"] = [
            f"도메인 판단 절차 {index}을 수행한다."
            for index in range(1, 10)
        ]

        prompt = RENDERER.render_prompt(brief, self.ledger(), "공통 정책")

        self.assertIn("도메인 판단 절차 9", prompt)
        self.assertEqual(12, RENDERER.CORE_PROCEDURE_LIMIT)

    def test_renderer_rejects_more_than_twelve_domain_steps(self):
        brief = self.brief()
        brief["core_procedure"] = [
            f"도메인 판단 절차 {index}을 수행한다."
            for index in range(1, 14)
        ]

        with self.assertRaisesRegex(
            RENDERER.BRIEF.PromptBuildBriefError,
            "0~12",
        ):
            RENDERER.render_prompt(brief, self.ledger(), "공통 정책")

    def test_renderer_rejects_brief_that_changes_fixed_constraints(self):
        brief = self.brief()
        brief["fixed_constraints"] = ["예산은 5만원 이하다."]
        with self.assertRaisesRegex(
            RENDERER.BRIEF.PromptBuildBriefError,
            "fixed_constraints",
        ):
            RENDERER.render_prompt(brief, self.ledger(), "공통 정책")

    def test_cli_writes_prompt_without_model_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief_path = root / "brief.json"
            ledger_path = root / "ledger.json"
            policy_path = root / "policy.md"
            output_path = root / "final_prompt.md"
            brief_path.write_text(
                json.dumps(self.brief(), ensure_ascii=False),
                encoding="utf-8",
            )
            ledger_path.write_text(
                json.dumps(self.ledger(), ensure_ascii=False),
                encoding="utf-8",
            )
            policy_path.write_text(
                "# Goal-aware assistant policy\n\n실제 선택과 행동을 분명하게 만든다.\n",
                encoding="utf-8",
            )

            exit_code = RENDERER.main(
                [
                    "--brief",
                    str(brief_path),
                    "--ledger",
                    str(ledger_path),
                    "--policy",
                    str(policy_path),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertTrue(output_path.is_file())
            text = output_path.read_text(encoding="utf-8")
            self.assertIn("실제 선택과 행동을 분명하게 만든다.", text)
            self.assertNotIn("Goal-aware assistant policy", text)


if __name__ == "__main__":
    unittest.main()
