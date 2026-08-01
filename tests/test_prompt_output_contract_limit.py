import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import problem_solving_prompt_renderer as RENDERER  # noqa: E402


class PromptOutputContractLimitTests(unittest.TestCase):
    def brief(self, count: int) -> dict:
        completion = "사용자가 결과를 바로 판단할 수 있다."
        return {
            "version": 1,
            "goal": "복잡한 비교 결과를 구조적으로 제시한다.",
            "core_procedure": [],
            "supporting_inputs": [],
            "fixed_constraints": [],
            "output_contract": [completion]
            + [f"필수 산출물 {index}" for index in range(2, count + 1)],
            "defaults_and_exceptions": [],
            "exclusions": [],
            "upstream_context": [],
        }

    def ledger(self) -> dict:
        return {
            "fixed_constraints": [],
            "completion_condition": "사용자가 결과를 바로 판단할 수 있다.",
        }

    def test_renderer_accepts_twelve_output_contract_items(self):
        validated = RENDERER.BRIEF.validate_prompt_build_brief(
            self.brief(12),
            self.ledger(),
        )
        self.assertEqual(12, len(validated["output_contract"]))

    def test_schema_matches_renderer_output_contract_limit(self):
        schema = json.loads(
            (ROOT / "schemas" / "problem-solving-prompt-build-brief.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            RENDERER.OUTPUT_CONTRACT_LIMIT,
            schema["properties"]["output_contract"]["maxItems"],
        )

    def test_renderer_still_rejects_thirteen_output_contract_items(self):
        with self.assertRaises(RENDERER.BRIEF.PromptBuildBriefError):
            RENDERER.BRIEF.validate_prompt_build_brief(
                self.brief(13),
                self.ledger(),
            )


if __name__ == "__main__":
    unittest.main()
