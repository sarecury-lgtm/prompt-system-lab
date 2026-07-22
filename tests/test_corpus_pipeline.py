import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "corpus_pipeline.py"
SPEC = importlib.util.spec_from_file_location("corpus_pipeline", MODULE_PATH)
PIPELINE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PIPELINE)


class CorpusPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = PIPELINE.load_manifest()
        cls.report = PIPELINE.validate_repository(cls.manifest)

    def test_manifest_covers_all_130_corpus_entries(self):
        entries = PIPELINE.parse_corpus()
        self.assertEqual(130, len(entries))
        self.assertEqual(130, len({entry["source_id"] for entry in entries}))
        self.assertEqual(130, len(self.manifest["sources"]))

    def test_next_has_only_requested_fields(self):
        batch = PIPELINE.select_next(self.manifest, 10)
        self.assertEqual(10, len(batch))
        expected = {"source_id", "name", "source_url", "current_status", "possible_patterns"}
        self.assertTrue(all(set(item) == expected for item in batch))
        duplicate_ids = PIPELINE.duplicate_url_ids(self.manifest)
        by_id = {source["source_id"]: source for source in self.manifest["sources"]}
        self.assertTrue(
            all(by_id[item["source_id"]]["duplicate_status"] not in {"alias", "deferred"} for item in batch)
        )
        self.assertTrue(all(item["current_status"] in {"cataloged", "lesson-draft"} for item in batch))

    def test_remaining_current_problems_are_reported(self):
        codes = {item["code"] for item in self.report["issues"]}
        self.assertIn("duplicate-source-url", codes)
        self.assertIn("suspicious-pattern-link", codes)
        self.assertIn("local-only-pattern-verification", codes)
        self.assertNotIn("index-source-number-mismatch", codes)
        self.assertNotIn("stale-verification-reference", codes)
        self.assertNotIn("stale-verification-conclusion", codes)

    def test_index_and_lesson_states_sync_with_automatic_verification(self):
        verified = [
            source
            for source in self.manifest["sources"]
            if source["upgrade_status"] == "verified" or source["verified_at"] is not None
        ]
        self.assertTrue(
            all(
                source["automation_status"] == "applied"
                and source["source_checked"]
                and source["verification_basis"] == "external-source"
                and source["verified_at"] is not None
                for source in verified
            )
        )
        by_id = {source["source_id"]: source for source in self.manifest["sources"]}
        for source_id in ("PR001", "PR002", "PR011", "PR025"):
            self.assertIn(
                by_id[source_id]["upgrade_status"],
                {"lesson-draft", "verified", "tested"},
            )
            self.assertEqual("referenced", by_id[source_id]["pattern_link_status"])
            self.assertTrue(by_id[source_id]["lesson_present"])

    def test_pattern_gap_strategy_rotates_across_weak_patterns(self):
        manifest = json.loads(json.dumps(self.manifest))
        by_id = {source["source_id"]: source for source in manifest["sources"]}
        targets = set(PIPELINE.PRIORITY_PATTERN_GAPS)
        for source in manifest["sources"]:
            if targets.intersection(source.get("related_patterns", [])):
                source["automation_status"] = "deferred"
                source["deferred_reasons"] = ["test"]
                source["automation_attempts"] = 1
        by_id["PR061"].update(
            upgrade_status="cataloged", automation_status="pending",
            deferred_reasons=[], automation_attempts=0,
        )
        for source_id in ("PR039", "PR025"):
            by_id[source_id].update(
                upgrade_status="lesson-draft", automation_status="deferred",
                deferred_reasons=["test"], automation_attempts=0,
            )
        batch = PIPELINE.select_next(manifest, 10, strategy="pattern-gaps")
        self.assertEqual(
            ["PR061", "PR039", "PR025"],
            [item["source_id"] for item in batch],
        )
        self.assertEqual(
            list(PIPELINE.PRIORITY_PATTERN_GAPS),
            [item["target_pattern"] for item in batch],
        )

    def test_apply_rejects_unchecked_verified_promotion(self):
        existing = self.manifest["sources"][0]
        payload = {
            "source_id": existing["source_id"],
            "name": existing["name"],
            "source_url": existing["source_url"],
            "source_status": existing["source_status"],
            "upgrade_status": "verified",
            "pattern_link_status": existing["pattern_link_status"],
            "related_patterns": existing["related_patterns"],
            "evidence_relation": "direct",
            "evidence_note": "Only a local summary was reviewed.",
            "source_checked": False,
            "checked_at": None,
            "verification_basis": "corpus-summary",
            "verified_at": None,
            "tested": False,
            "lesson": {
                "pattern_lesson": "Draft lesson",
                "mechanism": "Draft mechanism",
                "failure_mode": "Draft failure",
                "reusable_move": "Draft move"
            }
        }
        with self.assertRaises(PIPELINE.PipelineError):
            PIPELINE.validate_apply_item(payload, existing, PIPELINE.parse_pattern_index())

    def test_output_schema_is_strict_for_codex_exec(self):
        for filename in ("batch-result.schema.json", "independent-review.schema.json"):
            schema = json.loads((ROOT / "prompt-corpus" / filename).read_text(encoding="utf-8"))
            objects = [schema] + [
                value for value in schema.get("$defs", {}).values()
                if isinstance(value, dict) and "properties" in value
            ]
            for definition in objects:
                self.assertFalse(definition["additionalProperties"])
                self.assertEqual(set(definition["properties"]), set(definition["required"]))

    def test_generated_batch_rejects_automatic_confirmation(self):
        source = next(
            item for item in self.manifest["sources"]
            if item["upgrade_status"] == "cataloged"
            and item["automation_status"] == "pending"
            and item["duplicate_status"] not in {"alias", "deferred"}
        )
        selection = [{"source_id": source["source_id"]}]
        raw = {
            "source_id": source["source_id"],
            "name": source["name"],
            "source_url": source["source_url"],
            "source_status": source["source_status"],
            "upgrade_status": "cataloged",
            "pattern_link_status": "confirmed",
            "related_patterns": source["related_patterns"],
            "evidence_relation": "unverified",
            "evidence_note": None,
            "source_checked": False,
            "checked_at": None,
            "verification_basis": None,
            "verified_at": None,
            "tested": False,
            "test_evidence": None,
            "source_type": source["source_type"],
            "tags": source["tags"],
            "lesson": None,
        }
        accepted, rejected = PIPELINE.filter_generated_batch(
            {"batch_id": "test-run", "sources": [raw]},
            "test-run",
            selection,
            self.manifest,
        )
        self.assertEqual([], accepted["sources"])
        self.assertIn("human confirmation", rejected[0]["reason"])

    def test_model_disagreement_is_deferred_and_skipped(self):
        existing = next(
            item for item in self.manifest["sources"]
            if item["upgrade_status"] == "cataloged"
            and item["automation_status"] == "pending"
            and item["duplicate_status"] not in {"alias", "deferred"}
        )
        selection = [{"source_id": existing["source_id"]}]
        writer = {
            "source_id": existing["source_id"],
            "name": existing["name"],
            "source_url": existing["source_url"],
            "source_status": existing["source_status"],
            "upgrade_status": "lesson-draft",
            "pattern_link_status": existing["pattern_link_status"],
            "related_patterns": existing["related_patterns"],
            "evidence_relation": "direct",
            "evidence_note": "Directly observed source evidence; synthesis is separately identified.",
            "source_checked": True,
            "checked_at": "2026-07-13",
            "verification_basis": "external-source",
            "verified_at": None,
            "tested": False,
            "test_evidence": None,
            "source_type": existing["source_type"],
            "tags": existing["tags"],
            "lesson": {
                "short_excerpt": None,
                "structure_summary": None,
                "pattern_lesson": "Lesson",
                "mechanism": "Mechanism",
                "failure_mode": "Failure",
                "reusable_move": "Move",
                "safety_note": None,
            },
        }
        review = {
            "source_id": existing["source_id"],
            "verdict": "PASS",
            "source_checked": True,
            "checked_at": "2026-07-13",
            "evidence_relation": "partial",
            "supported_patterns": existing["related_patterns"],
            "reusable_move_supported": True,
            "claims_match_source": True,
            "evidence_note_adequate": True,
            "issues": [],
            "rationale": "Independent review",
        }
        accepted, deferred = PIPELINE.decide_automatic_application(
            selection,
            {"batch_id": "test", "sources": [writer]},
            [],
            {existing["source_id"]: review},
            [],
            self.manifest,
        )
        self.assertEqual([], accepted)
        self.assertIn("model-disagreement-relation", deferred[existing["source_id"]])

        changed = json.loads(json.dumps(self.manifest))
        changed_source = next(
            item for item in changed["sources"] if item["source_id"] == existing["source_id"]
        )
        changed_source["automation_status"] = "deferred"
        changed_source["deferred_reasons"] = ["model-disagreement-relation"]
        next_ids = {item["source_id"] for item in PIPELINE.select_next(changed, 10, strategy="pattern-gaps")}
        self.assertNotIn(existing["source_id"], next_ids)

    def test_duplicate_urls_are_signals_with_canonical_policy(self):
        duplicate_issues = [
            item for item in self.report["issues"] if item["code"] == "duplicate-source-url"
        ]
        self.assertTrue(duplicate_issues)
        self.assertTrue(all(item["severity"] == "warning" for item in duplicate_issues))
        by_id = {source["source_id"]: source for source in self.manifest["sources"]}
        self.assertEqual("distinct", by_id["PR001"]["duplicate_status"])
        self.assertEqual("canonical", by_id["PR012"]["duplicate_status"])
        self.assertEqual("alias", by_id["PR123"]["duplicate_status"])
        self.assertEqual("PR012", by_id["PR123"]["canonical_source_id"])
        self.assertEqual("deferred", by_id["PR016"]["duplicate_status"])


if __name__ == "__main__":
    unittest.main()
