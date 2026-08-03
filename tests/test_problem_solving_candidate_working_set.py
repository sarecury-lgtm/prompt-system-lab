import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_candidate_working_set as WORKING


def source_state():
    return {
        "source_scout": {
            "request_summary": "실제로 살 후보를 찾는다",
            "external_research_needed": True,
            "searches_used": 2,
            "probes": [
                {
                    "family": "MARKETPLACE",
                    "queries": ["현재 판매 후보"],
                    "concrete_leads": [
                        {
                            "name": "후보 A",
                            "url": "https://example.test/a",
                            "why_actionable": "현재 가격을 확인할 수 있음",
                        },
                        {
                            "name": "후보 B",
                            "url": "https://example.test/b",
                            "why_actionable": "중량 옵션을 확인할 수 있음",
                        },
                    ],
                    "repeated_specificity": "concrete",
                    "recency": "current",
                    "actionability": "decision_ready",
                    "access": "open",
                    "verification_need": "current_state",
                    "signal_summary": "판매 후보와 가격 단서가 구체적이다.",
                },
                {
                    "family": "COMMUNITY",
                    "queries": ["실사용 후기"],
                    "concrete_leads": [
                        {
                            "name": "후보 A 중복",
                            "url": "https://example.test/a",
                            "why_actionable": "반복 언급됨",
                        }
                    ],
                    "repeated_specificity": "concrete",
                    "recency": "current",
                    "actionability": "lead",
                    "access": "open",
                    "verification_need": "current_state",
                    "signal_summary": "실사용 언급이 반복된다.",
                },
            ],
            "scouting_limitations": ["배송지는 아직 확인하지 않음"],
        },
        "decision": {
            "strategy": "MARKET_SCAN",
            "primary_source_family": "MARKETPLACE",
            "secondary_source_family": None,
            "scores": {"MARKETPLACE": 11, "COMMUNITY": 9},
            "selection_reason": "MARKETPLACE가 가장 구체적이다.",
            "next_action": "가격과 옵션을 구조화한다.",
        },
    }


class CandidateWorkingSetTests(unittest.TestCase):
    def make_working(self):
        return WORKING.new_working_set(
            run_id="next-test",
            request="후보를 찾아줘",
            goal="실제로 쓸 후보를 고른다",
            constraints={"budget": 2000},
            source_scout_state=source_state(),
            unresolved_requirements=["배송지"],
        )

    def test_source_scout_becomes_deduplicated_working_set_and_dynamic_scan(self):
        working = self.make_working()
        scan = WORKING.source_scout_to_dynamic_scan(source_state())

        self.assertEqual("awaiting_correction", working["state"])
        self.assertEqual(2, len(working["candidates"]))
        self.assertEqual("candidate-001", working["candidates"][0]["id"])
        self.assertEqual("needs_check", working["candidates"][0]["status"])
        self.assertEqual("MARKET_SCAN", working["source_plan"]["strategy"])
        self.assertIn("현재 판매 후보", scan["vocabulary"])
        self.assertEqual(2, len(scan["adjacent_possibilities"]))
        self.assertIn("배송지는 아직 확인하지 않음", scan["source_gaps"])

    def test_exclusion_is_local_rerank(self):
        working = self.make_working()
        correction = WORKING.plan_correction(
            correction_id="correction-001",
            text="후보 A 제외",
            correction_type="exclude_candidate",
            target_candidate_ids=["candidate-001"],
        )
        updated = WORKING.apply_correction(working, correction)

        self.assertEqual("RERANK", updated["next_action"])
        self.assertEqual("excluded", updated["candidates"][0]["status"])
        self.assertEqual(["candidate-002"], [item["id"] for item in WORKING.kept_candidates(updated)])

    def test_known_constraint_filters_without_research(self):
        working = self.make_working()
        working["candidates"][0]["attributes"]["price_per_100g"] = 900
        working["candidates"][1]["attributes"]["price_per_100g"] = 1500
        working = WORKING.validate_working_set(working)

        filtered, stats = WORKING.apply_known_constraint_filter(
            working,
            {"price_per_100g": {"op": "lte", "value": 1000}},
            reason="100g당 1000원 이하",
        )

        self.assertEqual({"evaluated": 2, "excluded": 1, "kept": 1, "unknown": 0}, stats)
        self.assertEqual("kept", filtered["candidates"][0]["status"])
        self.assertEqual("excluded", filtered["candidates"][1]["status"])

    def test_unknown_constraint_is_preserved_for_partial_research(self):
        working = self.make_working()
        filtered, stats = WORKING.apply_known_constraint_filter(
            working,
            {"price_per_100g": {"op": "lte", "value": 1000}},
            reason="가격 상한 변경",
        )

        self.assertEqual(0, stats["evaluated"])
        self.assertEqual(2, stats["unknown"])
        self.assertTrue(all(item["status"] == "needs_check" for item in filtered["candidates"]))

    def test_model_output_only_structures_correction(self):
        working = self.make_working()
        correction = WORKING.correction_from_model_output(
            {
                "candidate_correction": {
                    "correction_type": "constraint_change",
                    "target_candidate_ids": [],
                    "constraint_updates": [
                        {"key": "price_per_100g", "operator": "lte", "value": "1,000"}
                    ],
                    "scope_terms": [],
                    "verification_fields": [],
                    "interpretation": "100g당 가격 상한을 1000원으로 낮춤",
                }
            },
            working_set=working,
            correction_id="correction-001",
            original_text="전부 비싸. 100g당 1000원 이하로 봐",
        )

        self.assertEqual("FILTER", correction["planned_action"])
        self.assertEqual(
            {"op": "lte", "value": 1000},
            correction["constraint_updates"]["price_per_100g"],
        )


if __name__ == "__main__":
    unittest.main()
