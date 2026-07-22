import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_chatgpt_action_runtime.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_chatgpt_action_runtime", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ChatGPTActionRuntimeTests(unittest.TestCase):
    def test_builds_only_approved_patterns_active_sources_and_bundle(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "runtime"
            catalog = builder.build_runtime(output_root=output)

            self.assertEqual(9, len(catalog["patterns"]))
            self.assertEqual(7, len(catalog["active_sources"]))
            self.assertFalse(catalog["routing_policy"]["full_corpus_auto_search"])
            self.assertEqual(1, catalog["routing_policy"]["max_active_sources_per_request"])
            self.assertTrue(catalog["routing_policy"]["baseline_first"])
            self.assertTrue(catalog["routing_policy"]["pattern_only_preferred"])

            pattern_files = sorted((output / "patterns").glob("*.json"))
            active_files = sorted((output / "active").glob("*.json"))
            self.assertEqual(9, len(pattern_files))
            self.assertEqual(7, len(active_files))

            for path in pattern_files:
                card = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual("pattern-card", card["kind"])
                self.assertTrue(card["detail_markdown"])
                self.assertTrue(card["source_entries"])

            for path in active_files:
                card = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual("active-source-card", card["kind"])
                self.assertEqual(1, card["global_policy"]["max_active_sources_per_request"])
                self.assertFalse(card["global_policy"]["full_corpus_auto_search"])

            bundle = (output / "PROMPT_COMPILER_BUNDLE.md").read_text(encoding="utf-8")
            self.assertIn('"pattern_cards"', bundle)
            self.assertIn('"active_cards"', bundle)
            self.assertIn('"global_protocol"', bundle)
            self.assertIn('"bundle_version": "0.3-draft"', bundle)

    def test_custom_gpt_contract_uses_bundle_by_default_and_action_on_request(self):
        instructions = (ROOT / "runtime" / "CUSTOM_GPT_INSTRUCTIONS.md").read_text(
            encoding="utf-8"
        )
        schema = (ROOT / "runtime" / "openapi.yaml").read_text(encoding="utf-8")

        for operation in (
            "getRuntimeCatalog",
            "getPatternCard",
            "getActiveSourceCard",
            "getGlobalResponseProtocol",
        ):
            self.assertIn(operation, schema)

        self.assertIn("일반적인 프롬프트 제작 요청에서는 GitHub Action을 호출하지 않는다", instructions)
        self.assertIn("명시적으로 요구한 경우에만 Action을 호출한다", instructions)
        self.assertIn("active → pattern-only → baseline", instructions)
        self.assertIn("full corpus 자동 검색을 하지 않는다", instructions)
        self.assertIn("getRuntimeCatalog", instructions)
        self.assertIn("enum: [pr002, pr026, pr065, pr086, pr089, pr091, pr093]", schema)

    def test_global_protocol_is_a_quality_gate_not_a_pattern(self):
        protocol = json.loads(
            (ROOT / "runtime" / "protocols" / "global-response-v3.1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("evolving-reference", protocol["status"])
        self.assertEqual(4, len(protocol["sequence"]))
        self.assertNotIn(protocol["id"], {"pattern-card", "active-source-card"})


if __name__ == "__main__":
    unittest.main()
