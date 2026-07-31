import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = (
    ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json",
    ROOT / "schemas" / "problem-solving-chart-prompt-assessment.schema.json",
)


class ChartPromptSchemaTests(unittest.TestCase):
    def test_const_fields_also_declare_a_json_type(self):
        for path in SCHEMA_PATHS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            pending = [("$", schema)]
            while pending:
                location, value = pending.pop()
                if isinstance(value, dict):
                    if "const" in value:
                        self.assertIn(
                            "type",
                            value,
                            f"{path.name} {location} uses const without type",
                        )
                    pending.extend(
                        (f"{location}.{key}", child)
                        for key, child in value.items()
                    )
                elif isinstance(value, list):
                    pending.extend(
                        (f"{location}[{index}]", child)
                        for index, child in enumerate(value)
                    )

    def test_version_is_an_integer_constant(self):
        for path in SCHEMA_PATHS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                {"type": "integer", "const": 1},
                schema["properties"]["version"],
                path.name,
            )


if __name__ == "__main__":
    unittest.main()
