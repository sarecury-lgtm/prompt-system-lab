import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [
    ROOT / "schemas" / "problem-solving-os-route.schema.json",
    ROOT / "schemas" / "problem-solving-os-execution.schema.json",
    ROOT / "schemas" / "problem-solving-os-result-contract.schema.json",
    ROOT / "schemas" / "problem-solving-os-result-contract-assessment.schema.json",
    ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json",
    ROOT / "schemas" / "problem-solving-prompt-applied-assessment.schema.json",
    ROOT / "schemas" / "problem-solving-goal-aware-assessment.schema.json",
    ROOT / "schemas" / "problem-solving-dynamic-framing.schema.json",
    ROOT / "schemas" / "problem-solving-dynamic-open-scan.schema.json",
    ROOT / "schemas" / "problem-solving-dynamic-question-gate.schema.json",
    ROOT / "schemas" / "problem-solving-dynamic-action-plan.schema.json",
    ROOT / "schemas" / "problem-solving-dynamic-assessment.schema.json",
    ROOT / "schemas" / "problem-solving-source-scout.schema.json",
    ROOT / "schemas" / "problem-solving-candidate-correction.schema.json",
]
UNSUPPORTED_KEYWORDS = {"minLength", "maxLength", "uniqueItems"}


def walk(value, path="$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


class CodexStructuredOutputSchemaCompatibilityTests(unittest.TestCase):
    def test_response_schemas_use_explicit_types_and_safe_keywords(self):
        for schema_path in SCHEMAS:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            with self.subTest(schema=schema_path.name):
                for path, node in walk(schema):
                    if "const" in node:
                        self.assertIn("type", node, f"{schema_path.name}:{path}")
                    self.assertTrue(
                        UNSUPPORTED_KEYWORDS.isdisjoint(node),
                        f"{schema_path.name}:{path} contains an unsupported keyword",
                    )
                    if node.get("type") == "object":
                        self.assertIs(
                            node.get("additionalProperties"),
                            False,
                            f"{schema_path.name}:{path}",
                        )


if __name__ == "__main__":
    unittest.main()
