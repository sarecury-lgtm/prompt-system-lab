import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import problem_solving_prompt_renderer as RENDERER  # noqa: E402


class PromptDefaultsAndExceptionsLimitTests(unittest.TestCase):
    def brief(self, count: int) -> dict:
        completion = "사용자가 결과를 바로 판단할 수 있다."
        return {
            "version": 1,
            "goal": "누락 정보와 예외를 처리해 추천 결과를 만든다.",
            "core_procedure": [],
            "supporting_inputs": [],
            "fixed_constraints": [],
            "output_contract": [completion],
            "defaults_and_exceptions": [
                f"누락 정보 또는 예외 처리 {index}" for index in range(1, count + 1)
            ],
            "exclusions": [],
            "upstream_context": [],
        }

    def ledger(self) -> dict:
        return {
            "fixed_constraints": [],
            "completion_condition": "사용자가 결과를 바로 판단할 수 있다.",
        }

    def test_renderer_accepts_twelve_defaults_and_exceptions(self):
        validated = RENDERER.BRIEF.validate_prompt_build_brief(
            self.brief(12),
            self.ledger(),
        )
        self.assertEqual(12, len(validated["defaults_and_exceptions"]))

    def test_schema_matches_renderer_defaults_and_exceptions_limit(self):
        schema = json.loads(
            (ROOT / "schemas" / "problem-solving-prompt-build-brief.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            RENDERER.DEFAULTS_AND_EXCEPTIONS_LIMIT,
            schema["properties"]["defaults_and_exceptions"]["maxItems"],
        )

    def test_renderer_still_rejects_thirteen_defaults_and_exceptions(self):
        with self.assertRaises(RENDERER.BRIEF.PromptBuildBriefError):
            RENDERER.BRIEF.validate_prompt_build_brief(
                self.brief(13),
                self.ledger(),
            )


if __name__ == "__main__":
    unittest.main()
