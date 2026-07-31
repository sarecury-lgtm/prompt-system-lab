import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = (
    ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json",
    ROOT / "schemas" / "problem-solving-chart-prompt-assessment.schema.json",
)


class ChartPromptSchemaTests(unittest.TestCase):
    def _walk(self, path: Path):
        schema = json.loads(path.read_text(encoding="utf-8"))
        pending = [("$", schema)]
        while pending:
            location, value = pending.pop()
            yield location, value
            if isinstance(value, dict):
                pending.extend(
                    (f"{location}.{key}", child)
                    for key, child in value.items()
                )
            elif isinstance(value, list):
                pending.extend(
                    (f"{location}[{index}]", child)
                    for index, child in enumerate(value)
                )

    def test_const_fields_also_declare_a_json_type(self):
        for path in SCHEMA_PATHS:
            for location, value in self._walk(path):
                if isinstance(value, dict) and "const" in value:
                    self.assertIn(
                        "type",
                        value,
                        f"{path.name} {location} uses const without type",
                    )

    def test_strict_output_schemas_do_not_use_unique_items(self):
        for path in SCHEMA_PATHS:
            for location, value in self._walk(path):
                if isinstance(value, dict):
                    self.assertNotIn(
                        "uniqueItems",
                        value,
                        f"{path.name} {location} uses unsupported uniqueItems",
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
