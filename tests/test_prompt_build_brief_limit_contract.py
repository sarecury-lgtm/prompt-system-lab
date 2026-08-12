import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import problem_solving_compare_web as COMPARE  # noqa: E402
import problem_solving_prompt_build_brief as BRIEF  # noqa: E402
import problem_solving_prompt_renderer as RENDERER  # noqa: E402


class PromptBuildBriefLimitContractTests(unittest.TestCase):
    def ledger(self) -> dict:
        return {
            "parent_goal": "재사용 가능한 작업 프롬프트를 만든다.",
            "current_goal_hypothesis": "누락 정보와 예외를 다루는 프롬프트를 만든다.",
            "fixed_constraints": [],
            "current_position": "프롬프트 설계가 필요하다.",
            "selected_route": "PROMPT",
            "secondary_route": None,
            "route_reason": "반복 실행할 지시문이 산출물이다.",
            "current_step": "필수 절차와 예외를 설계한다.",
            "why_this_step_matters": "결과의 일관성을 높이기 위해서다.",
            "completion_condition": "다른 AI가 바로 실행할 프롬프트가 제공된다.",
            "important_uncertainties": [],
        }

    def brief(self, defaults_count: int) -> dict:
        return {
            "version": 1,
            "goal": "누락 정보와 예외를 처리해 결과를 만든다.",
            "core_procedure": ["요청에 필요한 판단을 수행한다."],
            "supporting_inputs": [],
            "fixed_constraints": [],
            "output_contract": [self.ledger()["completion_condition"]],
            "defaults_and_exceptions": [
                f"누락 정보 또는 예외 처리 {index}"
                for index in range(1, defaults_count + 1)
            ],
            "exclusions": [],
            "upstream_context": [],
        }

    def brief_with_field_count(self, field: str, count: int) -> dict:
        brief = self.brief(0)
        if field == "output_contract":
            brief[field] = [self.ledger()["completion_condition"]] + [
                f"{field} 항목 {index}" for index in range(2, count + 1)
            ]
        else:
            brief[field] = [f"{field} 항목 {index}" for index in range(1, count + 1)]
        return brief

    def integrated_design(self, defaults_count: int) -> dict:
        return {
            "goal_ledger": self.ledger(),
            "prompt_build_brief": self.brief(defaults_count),
            "final_prompt": (
                "사용자의 요청을 확인하고 필요한 판단을 수행한다. "
                "확인할 수 없는 사실은 만들지 않고 누락 정보가 결과를 바꾸면 명시한다. "
                "최종 결과에는 판단 근거와 실행 가능한 다음 행동을 함께 제시한다."
            ),
        }

    def schema_properties(self) -> list[dict]:
        brief_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-prompt-build-brief.schema.json")
            .read_text(encoding="utf-8")
        )
        integrated_schema = json.loads(
            (ROOT / "schemas" / "problem-solving-integrated-prompt-design.schema.json")
            .read_text(encoding="utf-8")
        )
        return [
            brief_schema["properties"],
            integrated_schema["properties"]["prompt_build_brief"]["properties"],
        ]

    def test_base_validator_accepts_hard_limit_and_rejects_above_it(self):
        bounded_fields = [
            field for field, (_minimum, maximum) in BRIEF.LIST_LIMITS.items()
            if maximum is not None
        ]
        for field in bounded_fields:
            with self.subTest(field=field, count=100):
                validated = BRIEF.validate_prompt_build_brief(
                    self.brief_with_field_count(field, 100),
                    self.ledger(),
                )
                self.assertEqual(100, len(validated[field]))

            with self.subTest(field=field, count=101):
                with self.assertRaises(BRIEF.PromptBuildBriefError):
                    BRIEF.validate_prompt_build_brief(
                        self.brief_with_field_count(field, 101),
                        self.ledger(),
                    )

    def test_integrated_validator_accepts_hard_limit_in_every_bounded_field(self):
        bounded_fields = [
            field for field, (_minimum, maximum) in BRIEF.LIST_LIMITS.items()
            if maximum is not None
        ]
        for field in bounded_fields:
            with self.subTest(field=field):
                payload = self.integrated_design(0)
                payload["prompt_build_brief"] = self.brief_with_field_count(field, 100)
                _ledger, brief, _final_prompt = COMPARE.validate_integrated_design(payload)
                self.assertEqual(100, len(brief[field]))

    def test_all_brief_schema_maximums_match_the_base_validator(self):
        for properties in self.schema_properties():
            for field, (_minimum, maximum) in BRIEF.LIST_LIMITS.items():
                with self.subTest(field=field):
                    if maximum is None:
                        self.assertNotIn("maxItems", properties[field])
                    else:
                        self.assertEqual(maximum, properties[field]["maxItems"])

    def test_renderer_uses_base_constants_without_mutating_limits(self):
        self.assertEqual(
            BRIEF.CORE_PROCEDURE_LIMIT,
            RENDERER.CORE_PROCEDURE_LIMIT,
        )
        self.assertEqual(
            BRIEF.OUTPUT_CONTRACT_LIMIT,
            RENDERER.OUTPUT_CONTRACT_LIMIT,
        )
        self.assertEqual(
            BRIEF.DEFAULTS_AND_EXCEPTIONS_LIMIT,
            RENDERER.DEFAULTS_AND_EXCEPTIONS_LIMIT,
        )
        source = (SCRIPTS_DIR / "problem_solving_prompt_renderer.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('BRIEF.LIST_LIMITS[', source)

    def test_model_instructions_state_the_twelve_item_limit(self):
        integrated_prompt = COMPARE.build_integrated_design_prompt("비교 프롬프트를 만든다.")
        brief_prompt = BRIEF.build_prompt_build_brief_prompt(
            "비교 프롬프트를 만든다.",
            self.ledger(),
            {},
            None,
        )
        browser_source = (ROOT / "web" / "compare-no-codex.js").read_text(
            encoding="utf-8"
        )

        for text in (integrated_prompt, brief_prompt, browser_source):
            with self.subTest(source=text[:30]):
                for field, (_minimum, maximum) in BRIEF.LIST_LIMITS.items():
                    if maximum is not None:
                        self.assertIn(field, text)
                self.assertGreaterEqual(text.count("권장 12개 이하"), 6)


if __name__ == "__main__":
    unittest.main()
