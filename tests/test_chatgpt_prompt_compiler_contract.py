import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / "chatgpt-project" / "PROMPT_COMPILER_INSTRUCTIONS.md"
SETUP = ROOT / "chatgpt-project" / "README.md"
POLICIES = (
    ROOT
    / "specs"
    / "experiments"
    / "prompt-mode-contribution"
    / "active-source-policies.json"
)


class ChatGPTPromptCompilerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instructions = INSTRUCTIONS.read_text(encoding="utf-8")
        cls.setup = SETUP.read_text(encoding="utf-8")
        cls.policies = json.loads(POLICIES.read_text(encoding="utf-8"))

    def test_instruction_contract_keeps_ai_writing_step(self):
        required = (
            "Understand the request",
            "Write a new prompt for this request",
            "Do not merely paste reusable-move sentences",
            "Validate and revise once",
            "Do not answer, research, code",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.instructions)

    def test_existing_routing_policy_is_preserved(self):
        self.assertFalse(self.policies["full_corpus_auto_search"])
        self.assertEqual(1, self.policies["max_auto_sources_per_request"])
        self.assertEqual(7, len(self.policies["sources"]))
        self.assertIn("Full-corpus automatic search is disabled", self.instructions)
        self.assertIn("At most one active source", self.instructions)

    def test_output_is_copyable_and_traceable(self):
        for field in (
            "### 바로 쓸 프롬프트",
            "### 선택 기록",
            "모드:",
            "이유:",
            "사용 패턴:",
            "active source:",
            "fallback:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.instructions)

    def test_setup_uses_repository_sources_without_claiming_git_sync(self):
        for path in (
            "prompt-corpus/PATTERN_LESSONS_INDEX.md",
            "skills/prompt-design-workflow.md",
            "active-source-policies.json",
        ):
            with self.subTest(path=path):
                self.assertIn(path, self.setup)
        self.assertIn("does not edit this repository", self.setup)
        self.assertIn("not an automatic two-way Git sync", self.setup)


if __name__ == "__main__":
    unittest.main()
