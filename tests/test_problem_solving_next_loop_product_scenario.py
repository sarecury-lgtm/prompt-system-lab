import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_next_loop_runtime as LOOP


def scout_output():
    return {
        "source_scout": {
            "request_summary": "온라인 삼겹살 후보를 조사한다",
            "external_research_needed": True,
            "searches_used": 2,
            "probes": [
                {
                    "family": "MARKETPLACE",
                    "queries": ["온라인 삼겹살 현재 판매"],
                    "concrete_leads": [
                        {
                            "name": "기존 냉장 삼겹살",
                            "url": "https://example.test/pork-a",
                            "why_actionable": "현재 판매 페이지 후보",
                        },
                        {
                            "name": "기존 냉동 삼겹살",
                            "url": "https://example.test/pork-b",
                            "why_actionable": "현재 판매 페이지 후보",
                        },
                    ],
                    "repeated_specificity": "concrete",
                    "recency": "current",
                    "actionability": "decision_ready",
                    "access": "open",
                    "verification_need": "current_state",
                    "signal_summary": "판매 후보가 구체적이다.",
                },
                {
                    "family": "COMMUNITY",
                    "queries": ["삼겹살 실구매 후기"],
                    "concrete_leads": [],
                    "repeated_specificity": "weak",
                    "recency": "mixed",
                    "actionability": "lead",
                    "access": "open",
                    "verification_need": "cross_check",
                    "signal_summary": "후기 신호는 보조적이다.",
                },
            ],
            "scouting_limitations": ["배송비 포함 가격은 아직 확인하지 않음"],
        }
    }


def framing_output():
    return {
        "framing": {
            "goal_hypothesis": "3kg 이하에서 실제로 살 삼겹살 후보를 고른다",
            "explicit_constraints": ["현재 구매 가능해야 한다", "배송비 포함 가격을 비교한다"],
            "unknowns": [],
            "external_landscape_matters": True,
        }
    }


def question_gate():
    return {
        "question_gate": {
            "questions": [],
            "can_proceed_without_answers": True,
            "reason": "현재 후보와 사용자 교정으로 조사할 수 있다.",
        }
    }


def plan_output(target):
    return {
        "plan": {
            "candidate_actions": [
                {
                    "id": "targeted-research",
                    "description": target,
                    "method": "부분 재조사",
                    "route": "RESEARCH",
                    "information_target": target,
                    "expected_value": "높음",
                    "cost": "낮음",
                },
                {
                    "id": "restart-all",
                    "description": "전체 시장을 처음부터 다시 조사",
                    "method": "전체 재조사",
                    "route": "RESEARCH",
                    "information_target": "전체 후보",
                    "expected_value": "중간",
                    "cost": "높음",
                },
            ],
            "selected_action_id": "targeted-research",
            "selection_reason": "사용자 교정에 필요한 구간만 확인하면 된다.",
            "difference_from_previous": None,
        }
    }


def execution_output(summary, evidence_url):
    return {
        "execution": {
            "status": "completed",
            "summary": summary,
            "result_markdown": summary,
            "capabilities_used": ["web_search"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [
                {
                    "source": evidence_url,
                    "finding": summary,
                    "kind": "web",
                }
            ],
            "limitations": [],
        }
    }


def assessment_output(reason):
    return {
        "assessment": {
            "verdict": "STOP",
            "reason": reason,
            "meaningful_information": [
                {
                    "claim": reason,
                    "source": "https://example.test/evidence",
                    "decision_effect": "후보 작업대를 갱신할 수 있다.",
                    "semantic_scope": "현재 판매 조건",
                    "reliability": "strong",
                }
            ],
            "discarded_information": [],
            "missing_information": [],
            "questions": [],
            "required_change": None,
        }
    }


def candidate_update_after_price_research():
    def item(candidate_id, name, url, price):
        return {
            "candidate_id": candidate_id,
            "name": name,
            "source_family": "MARKETPLACE",
            "source_url": url,
            "why_actionable": "배송비 포함 100g당 가격을 직접 확인함",
            "attributes": [
                {
                    "key": "price_per_100g",
                    "value": str(price),
                    "source": url,
                }
            ],
            "evidence": [
                {
                    "source": url,
                    "finding": f"배송비 포함 100g당 {price}원",
                    "kind": "web",
                }
            ],
            "strengths": ["가격이 직접 확인됨"],
            "risks": ["현재 판매 상태는 추가 확인 필요"],
            "status": "kept",
            "verification_status": "partially_verified",
        }

    return {
        "candidate_update": {
            "updates": [
                item(
                    "candidate-001",
                    "기존 냉장 삼겹살",
                    "https://example.test/pork-a",
                    1450,
                ),
                item(
                    "candidate-002",
                    "기존 냉동 삼겹살",
                    "https://example.test/pork-b",
                    1280,
                ),
                item(
                    "",
                    "추가 가성비 삼겹살",
                    "https://example.test/pork-c",
                    950,
                ),
            ],
            "resolved_requirements": [],
            "unresolved_requirements": ["현재 판매 상태 확인"],
            "completion_recommendation": "awaiting_correction",
            "reason": "가격 조건에 맞는 새 후보를 찾고 기존 후보 가격도 확인했다.",
        }
    }


def candidate_update_after_availability_check():
    return {
        "candidate_update": {
            "updates": [
                {
                    "candidate_id": "candidate-003",
                    "name": "추가 가성비 삼겹살",
                    "source_family": "MARKETPLACE",
                    "source_url": "https://example.test/pork-c",
                    "why_actionable": "현재 주문 가능한 옵션을 직접 확인함",
                    "attributes": [
                        {
                            "key": "availability",
                            "value": "available",
                            "source": "https://example.test/pork-c",
                        },
                        {
                            "key": "price_per_100g",
                            "value": "950",
                            "source": "https://example.test/pork-c",
                        },
                    ],
                    "evidence": [
                        {
                            "source": "https://example.test/pork-c",
                            "finding": "현재 주문 가능",
                            "kind": "web",
                        }
                    ],
                    "strengths": ["가격 상한 충족", "현재 주문 가능"],
                    "risks": [],
                    "status": "kept",
                    "verification_status": "verified",
                }
            ],
            "resolved_requirements": ["현재 판매 상태 확인"],
            "unresolved_requirements": [],
            "completion_recommendation": "completed",
            "reason": "남은 후보의 현재 판매 상태와 가격을 검증했다.",
        }
    }


class FakeEngine:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def capabilities(self):
        return LOOP.OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fake",
        )

    def execute(self, prompt, run_dir, invocation):
        self.calls.append((prompt, invocation))
        if not self.outputs:
            raise AssertionError(f"unexpected engine call: {invocation.name}")
        return self.outputs.pop(0)

    def trace(self):
        return [
            {"name": invocation.name, "phase": invocation.phase}
            for _prompt, invocation in self.calls
        ]


class ProductNextLoopScenarioTests(unittest.TestCase):
    def test_price_correction_research_merge_filter_and_verified_completion(self):
        engine = FakeEngine(
            [
                scout_output(),
                framing_output(),
                question_gate(),
                plan_output("100g당 1000원 이하 후보 조사"),
                execution_output(
                    "기존 두 후보 가격과 새로운 저가 후보를 확인했다.",
                    "https://example.test/pork-c",
                ),
                assessment_output("가격 구간 조사가 충분하다."),
                candidate_update_after_price_research(),
                question_gate(),
                plan_output("남은 후보의 현재 판매 상태 검증"),
                execution_output(
                    "가성비 후보가 현재 주문 가능함을 확인했다.",
                    "https://example.test/pork-c",
                ),
                assessment_output("현재 판매 상태까지 확인했다."),
                candidate_update_after_availability_check(),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, initial = LOOP.run_next_loop(
                "온라인 삼겹살을 3kg 이하에서 실제로 살 후보로 압축해줘",
                output_root=Path(temp_dir),
                run_id="pork-scenario",
                engine=engine,
            )
            self.assertEqual("awaiting_correction", initial["state"])

            _run_dir, after_price = LOOP.resume_next_loop(
                run_dir,
                engine=engine,
                correction={
                    "id": "correction-001",
                    "text": "전부 비싸. 배송비 포함 100g당 1000원 이하만 남겨",
                    "type": "constraint_change",
                    "target_candidate_ids": [],
                    "constraint_updates": {
                        "price_per_100g": {"op": "lte", "value": 1000}
                    },
                    "scope_terms": [],
                    "verification_fields": [],
                    "planned_action": "FILTER",
                },
            )

            candidates = after_price["candidate_working_set"]["candidates"]
            by_id = {candidate["id"]: candidate for candidate in candidates}
            self.assertEqual("awaiting_correction", after_price["state"])
            self.assertEqual("excluded", by_id["candidate-001"]["status"])
            self.assertEqual("excluded", by_id["candidate-002"]["status"])
            self.assertEqual("kept", by_id["candidate-003"]["status"])
            self.assertEqual(950, by_id["candidate-003"]["attributes"]["price_per_100g"])
            self.assertEqual(
                ["현재 판매 상태 확인"],
                after_price["candidate_working_set"]["unresolved_requirements"],
            )
            self.assertTrue(
                any(
                    item.get("action") == "REAPPLY_FILTER"
                    for item in after_price.get("candidate_update_history", [])
                )
            )

            _run_dir, final = LOOP.resume_next_loop(
                run_dir,
                engine=engine,
                correction={
                    "id": "correction-002",
                    "text": "현재 남은 후보로 결론 내줘",
                    "type": "accept_candidates",
                    "target_candidate_ids": [],
                    "constraint_updates": {},
                    "scope_terms": [],
                    "verification_fields": [],
                    "planned_action": "VERIFY_COMPLETION",
                },
            )

            final_candidate = next(
                candidate
                for candidate in final["candidate_working_set"]["candidates"]
                if candidate["id"] == "candidate-003"
            )
            result_text = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("completed", final["state"])
        self.assertEqual("verified", final_candidate["verification_status"])
        self.assertEqual("available", final_candidate["attributes"]["availability"])
        self.assertEqual([], final["candidate_working_set"]["unresolved_requirements"])
        self.assertIn("현재 주문 가능", result_text)
        self.assertEqual([], engine.outputs)


if __name__ == "__main__":
    unittest.main()
