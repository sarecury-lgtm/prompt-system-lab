import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "prompt_mode_compare.py"
SPEC = importlib.util.spec_from_file_location("prompt_mode_compare", MODULE_PATH)
COMPARE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(COMPARE)


class PromptModeCompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = COMPARE.load_documents()
        cls.token_index, cls.idf = COMPARE.build_index(cls.documents)

    def test_candidate_views_match_policy(self):
        full = [item for item in self.documents if item["duplicate_status"] != "alias"]
        active = [item for item in self.documents if item["active"]]
        registry = COMPARE.load_active_source_policies()
        production_ids = {item["source_id"] for item in registry["sources"]}
        self.assertEqual(123, len(full))
        self.assertEqual(13, len(active))
        self.assertEqual(
            {"PR002", "PR026", "PR065", "PR086", "PR089", "PR091", "PR093"},
            production_ids,
        )
        self.assertFalse(registry["full_corpus_auto_search"])
        self.assertEqual(1, registry["max_auto_sources_per_request"])
        self.assertTrue(any(item["upgrade_status"] == "cataloged" for item in full))
        self.assertTrue(any(item["duplicate_status"] == "deferred" for item in full))
        self.assertTrue(all(item["duplicate_status"] not in {"alias", "deferred"} for item in active))
        self.assertTrue(all(item["verification_basis"] == "external-source" for item in active))

    def test_same_search_method_and_top_k_are_used(self):
        request = "Build a versioned evaluation harness with JSONL cases and regression metrics."
        full = COMPARE.select_sources(request, "full", self.documents, 3, self.token_index, self.idf)
        active = COMPARE.select_sources(request, "active", self.documents, 3, self.token_index, self.idf)
        self.assertLessEqual(len(full["selected"]), 3)
        self.assertLessEqual(len(active["selected"]), 3)
        self.assertTrue(full["selected"])
        self.assertTrue(active["selected"])
        self.assertEqual(7, active["candidate_count"])
        self.assertNotEqual(full["candidate_count"], active["candidate_count"])

    def test_zero_relevance_is_not_filled_by_source_id(self):
        selection = COMPARE.select_sources(
            "zxqv unmatched nonsense token", "active", self.documents, 3,
            self.token_index, self.idf,
        )
        self.assertEqual([], selection["selected"])
        self.assertEqual(selection["candidate_count"], len(selection["excluded"]))

    def test_korean_requests_receive_semantic_pattern_hints(self):
        for request in (
            "모든 방을 완전히 분리하고 통창으로 설계해 주세요.",
            "가입 없이 한 화면에서 병원 예약을 끝내고 오류를 비교해 주세요.",
            "퇴사와 재직 경로의 비용과 위험을 비교하고 중단 기준을 정해 주세요.",
        ):
            with self.subTest(request=request):
                self.assertTrue(COMPARE.hinted_patterns(request))

    def test_expert_cases_route_conservatively(self):
        cases = dict(COMPARE.load_expert_routing_cases(COMPARE.EXPERT_CASES_DIR))
        records = {}
        diagnostics = {}
        for case_id, public in cases.items():
            record, detail = COMPARE.route_request(
                case_id, public, self.documents, 3, self.token_index, self.idf,
            )
            records[case_id] = record
            diagnostics[case_id] = detail
        self.assertEqual("baseline", records["A3"]["selected_mode"])
        self.assertEqual("pattern-only", records["C10"]["selected_mode"])
        self.assertEqual("pattern-only", records["C14"]["selected_mode"])
        for case_id in ("C11", "C13", "C16"):
            self.assertEqual("pattern-only", records[case_id]["selected_mode"])
            self.assertFalse(records[case_id]["used_sources"])
        if records["A7"]["selected_mode"] == "active":
            self.assertEqual(["PR065"], [item["source_id"] for item in records["A7"]["used_sources"]])
        self.assertTrue(COMPARE.validate_routing_dry_run(
            list(records.values()), diagnostics,
        )["pass"])
        self.assertTrue(all(record["selected_mode"] != "full" for record in records.values()))

    def test_every_production_policy_requires_task_type_and_all_signal_groups(self):
        registry = COMPARE.load_active_source_policies()
        for policy in registry["sources"]:
            matching = policy["matching"]
            public = {
                "user_request": " ".join([
                    matching["task_type_any"][0],
                    *(group["any"][0] for group in matching["required_all"]),
                ]),
                "initial_information": [],
                "tools_allowed": True,
            }
            with self.subTest(source_id=policy["source_id"]):
                passed, signals, reason = COMPARE.policy_gate_decision(public, policy)
                self.assertTrue(passed, reason)
                self.assertGreaterEqual(len(signals), 1 + len(matching["required_all"]))
                missing = {**public, "user_request": matching["task_type_any"][0]}
                self.assertFalse(COMPARE.policy_gate_decision(missing, policy)[0])

    def test_research_only_sources_are_not_production_candidates(self):
        registry = COMPARE.load_active_source_policies()
        ids = {item["source_id"] for item in registry["sources"]}
        self.assertTrue(
            {"PR001", "PR011", "PR039", "PR062", "PR110", "PR111"}.isdisjoint(ids)
        )

    def test_actual_usage_requests_are_not_holdouts_and_select_at_most_one_source(self):
        requests = COMPARE.load_holdout_requests(COMPARE.ACTUAL_USAGE_REQUESTS_PATH)
        self.assertEqual(12, len(requests))
        self.assertTrue(all(item["id"].startswith("AU") for item in requests))
        for item in requests:
            route, _ = COMPARE.route_request(
                item["id"], item["public"], self.documents, 3, self.token_index, self.idf,
            )
            self.assertLessEqual(len(route["used_sources"]), 1)
            self.assertNotEqual("full", route["selected_mode"])

    def test_search_targets_lessons_moves_and_evidence(self):
        fields = COMPARE.searchable_fields(next(item for item in self.documents if item["source_id"] == "PR062"))
        self.assertIn("evaluation-driven", fields["lesson"])
        self.assertIn("output contract", fields["move"])
        self.assertTrue(fields["evidence"])
        legacy = COMPARE.searchable_fields(next(item for item in self.documents if item["source_id"] == "PR109"))
        self.assertIn("evidence retrieval", legacy["move"])

    def test_context_limit_is_respected(self):
        selection = COMPARE.select_sources(
            "Research products with sources and uncertainty.", "full", self.documents, 3,
            self.token_index, self.idf,
        )["selected"]
        context = COMPARE.evidence_context(selection, 2000)
        self.assertLessEqual(len(context), 2000)
        self.assertTrue(all(item["source_id"] in context for item in selection))

    def test_generation_validation_rejects_unselected_evidence(self):
        selection = COMPARE.select_sources(
            "Act as a Linux terminal.", "active", self.documents, 3,
            self.token_index, self.idf,
        )["selected"]
        payload = {
            "selected_patterns": [],
            "used_source_ids": ["PR999"],
            "used_reusable_moves": [],
            "final_prompt": "Return terminal output only."
        }
        with self.assertRaises(COMPARE.CompareError):
            COMPARE.validate_generation(payload, selection)

    def test_meaningful_difference_requires_mode_specific_evidence(self):
        base = {
            "selected_source_ids": ["PR001", "PR011"],
            "used_source_ids": ["PR001"],
            "selected_patterns": ["Role + Task Frame"],
            "used_reusable_moves": ["shared move"],
            "final_prompt": "Explain the topic in five concise bullets.",
        }
        active = {
            **base,
            "selected_source_ids": ["PR001", "PR110"],
            "final_prompt": "Give a concise five-part explanation of the topic.",
        }
        self.assertFalse(COMPARE.compare_pair(base, active)["final_prompt_meaningfully_different"])
        active["used_source_ids"] = ["PR110"]
        active["used_reusable_moves"] = ["different move"]
        self.assertTrue(COMPARE.compare_pair(base, active)["final_prompt_meaningfully_different"])

    def test_eight_requests_are_repository_derived(self):
        requests = COMPARE.load_requests(COMPARE.DEFAULT_REQUESTS_PATH)
        self.assertEqual(8, len(requests))
        self.assertEqual(8, len({item["id"] for item in requests}))
        self.assertTrue(all(item["source"].startswith("specs/") for item in requests))

    def test_output_schema_is_strict(self):
        schema = json.loads(COMPARE.SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(schema["required"]))

    def test_holdout_requests_and_environment_constraints_are_fixed(self):
        requests = COMPARE.load_holdout_requests(COMPARE.HOLDOUT_REQUESTS_PATH)
        self.assertEqual(12, len(requests))
        by_id = {item["id"]: item for item in requests}
        self.assertFalse(by_id["H04"]["public"]["tools_allowed"])
        self.assertFalse(by_id["H11"]["public"]["tools_allowed"])
        for case_id in ("H04", "H11"):
            record, detail = COMPARE.route_request(
                case_id, by_id[case_id]["public"], self.documents, 3,
                self.token_index, self.idf,
            )
            self.assertEqual("baseline", record["selected_mode"])
            self.assertTrue(detail["analysis"]["repository_tool_mismatch"])

    def test_unused_active_source_forces_pattern_only_fallback(self):
        selected = [{"source_id": "PR111"}]
        active = {"used_source_ids": []}
        raw = COMPARE.unused_contribution_evaluation(selected)
        result = COMPARE.validate_contribution_evaluation(raw, selected, active)
        self.assertFalse(result["keep_active"])
        self.assertEqual([], result["unique_source_ids"])
        self.assertEqual("unused", result["source_assessments"][0]["verdict"])

    def test_routed_generation_preserves_source_id_already_in_public_input(self):
        payload = {
            "selected_patterns": ["Evaluation rubric"],
            "used_source_ids": [],
            "used_reusable_moves": ["Use frozen evaluation anchors."],
            "final_prompt": "PR111의 가치를 pattern-only와 비교하세요.",
        }
        result = COMPARE.validate_routed_generation(
            payload,
            "pattern-only",
            [],
            {"Evaluation rubric": "Use frozen evaluation anchors."},
            {"user_request": "PR111의 추가 가치를 시험하세요."},
        )
        self.assertIn("PR111", result["final_prompt"])

    def test_routed_generation_rejects_source_id_not_in_public_input(self):
        payload = {
            "selected_patterns": ["Evaluation rubric"],
            "used_source_ids": [],
            "used_reusable_moves": ["Use frozen evaluation anchors."],
            "final_prompt": "PR111을 시험하고 PR065도 주입하세요.",
        }
        with self.assertRaises(COMPARE.CompareError):
            COMPARE.validate_routed_generation(
                payload,
                "pattern-only",
                [],
                {"Evaluation rubric": "Use frozen evaluation anchors."},
                {"user_request": "PR111의 추가 가치를 시험하세요."},
            )

    def test_rephrased_pattern_behavior_is_not_unique_contribution(self):
        selected = [{"source_id": "PR111"}]
        active = {"used_source_ids": ["PR111"]}
        raw = {
            "source_assessments": [{
                "source_id": "PR111",
                "used_in_active_prompt": True,
                "contributions": [{
                    "type": "executable_validation",
                    "description": "Run a final check.",
                    "active_prompt_excerpt": "Run a final check.",
                    "pattern_only_overlap": "Validate before returning.",
                    "already_in_pattern_only": True,
                    "changes_judgment_or_deliverable": True,
                    "supported_by_source": True,
                }],
                "verdict": "unique",
                "reason": "The wording differs.",
            }],
            "keep_active": True,
            "fallback_reason": "Equivalent behavior already exists.",
        }
        result = COMPARE.validate_contribution_evaluation(raw, selected, active)
        self.assertFalse(result["keep_active"])
        self.assertEqual("not_unique", result["source_assessments"][0]["verdict"])

    def test_material_source_specific_behavior_can_keep_active(self):
        selected = [{"source_id": "PR091"}]
        active = {"used_source_ids": ["PR091"]}
        raw = {
            "source_assessments": [{
                "source_id": "PR091",
                "used_in_active_prompt": True,
                "contributions": [{
                    "type": "executable_validation",
                    "description": "Re-score the revised output against the frozen anchors.",
                    "active_prompt_excerpt": "Re-score the revision against the frozen anchors.",
                    "pattern_only_overlap": "",
                    "already_in_pattern_only": False,
                    "changes_judgment_or_deliverable": True,
                    "supported_by_source": True,
                }],
                "verdict": "unique",
                "reason": "This adds an executable second pass.",
            }],
            "keep_active": True,
            "fallback_reason": "",
        }
        result = COMPARE.validate_contribution_evaluation(raw, selected, active)
        self.assertTrue(result["keep_active"])
        self.assertEqual(["PR091"], result["unique_source_ids"])

    def test_contribution_schema_is_strict(self):
        schema = json.loads(COMPARE.CONTRIBUTION_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(schema["required"]))


if __name__ == "__main__":
    unittest.main()
