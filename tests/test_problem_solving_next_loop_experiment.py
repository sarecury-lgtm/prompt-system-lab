import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_next_loop_experiment as LOOP


def scout_output():
    return {
        "source_scout": {
            "request_summary": "후보를 조사한다",
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
                            "why_actionable": "현재 판매 정보를 확인할 수 있음",
                        }
                    ],
                    "repeated_specificity": "concrete",
                    "recency": "current",
                    "actionability": "decision_ready",
                    "access": "open",
                    "verification_need": "current_state",
                    "signal_summary": "판매 단서가 구체적이다.",
                },
                {
                    "family": "COMMUNITY",
                    "queries": ["실사용 후기"],
                    "concrete_leads": [
                        {
                            "name": "후보 B",
                            "url": "https://example.test/b",
                            "why_actionable": "실사용 언급이 반복됨",
                        }
                    ],
                    "repeated_specificity": "concrete",
                    "recency": "current",
                    "actionability": "lead",
                    "access": "open",
                    "verification_need": "current_state",
                    "signal_summary": "실사용 신호가 있다.",
                },
            ],
            "scouting_limitations": [],
        }
    }


def framing_output():
    return {
        "framing": {
            "goal_hypothesis": "실제로 쓸 후보를 고른다",
            "explicit_constraints": ["현재 선택 가능해야 한다"],
            "unknowns": [],
            "external_landscape_matters": True,
        }
    }


def question_gate():
    return {
        "question_gate": {
            "questions": [],
            "can_proceed_without_answers": True,
            "reason": "현재 후보와 교정으로 실행 가능하다.",
        }
    }


def plan_output():
    return {
        "plan": {
            "candidate_actions": [
                {
                    "id": "partial-research",
                    "description": "부족한 범위만 추가 조사",
                    "method": "부분 재조사",
                    "route": "RESEARCH",
                    "information_target": "추가 범위 후보",
                    "expected_value": "높음",
                    "cost": "낮음",
                },
                {
                    "id": "verify-existing",
                    "description": "기존 후보만 검증",
                    "method": "현재 상태 확인",
                    "route": "RESEARCH",
                    "information_target": "기존 후보 상태",
                    "expected_value": "중간",
                    "cost": "낮음",
                },
            ],
            "selected_action_id": "partial-research",
            "selection_reason": "사용자가 확장한 범위가 비어 있다.",
            "difference_from_previous": None,
        }
    }


def execution_output():
    return {
        "execution": {
            "status": "completed",
            "summary": "부분 재조사를 완료했다.",
            "result_markdown": "기존 후보를 유지하면서 추가 후보를 조사했다.",
            "capabilities_used": [],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [
                {
                    "source": "https://example.test/new",
                    "finding": "추가 범위 후보를 직접 확인함",
                    "kind": "web",
                }
            ],
            "limitations": [],
        }
    }


def assessment_output():
    return {
        "assessment": {
            "verdict": "STOP",
            "reason": "사용자가 바로 쓸 수 있는 결과가 있다.",
            "meaningful_information": [
                {
                    "claim": "추가 후보를 확인했다",
                    "source": "https://example.test/new",
                    "decision_effect": "후보 범위가 넓어짐",
                    "semantic_scope": "현재 상태",
                    "reliability": "strong",
                }
            ],
            "discarded_information": [],
            "missing_information": [],
            "questions": [],
            "required_change": None,
        }
    }


def correction_output():
    return {
        "candidate_correction": {
            "correction_type": "exclude_candidate",
            "target_candidate_ids": ["candidate-001"],
            "constraint_updates": [],
            "scope_terms": [],
            "verification_fields": [],
            "interpretation": "후보 A를 제외함",
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


class NextLoopExperimentTests(unittest.TestCase):
    def start(self, temp_dir, engine):
        return LOOP.run_next_loop(
            "후보를 찾아줘",
            output_root=Path(temp_dir),
            run_id="next-test",
            engine=engine,
        )

    def test_initial_run_stops_at_candidate_correction(self):
        engine = FakeEngine([scout_output(), framing_output()])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = self.start(temp_dir, engine)
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("awaiting_correction", state["state"])
        self.assertEqual(2, len(state["candidate_working_set"]["candidates"]))
        self.assertIn("후보 작업대", result)
        self.assertEqual(["source-scout", "next-framing"], [call[1].name for call in engine.calls])

    def test_structured_exclusion_does_not_call_engine_again(self):
        engine = FakeEngine([scout_output(), framing_output()])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, _state = self.start(temp_dir, engine)
            before = len(engine.calls)
            _run_dir, state = LOOP.resume_next_loop(
                run_dir,
                engine=engine,
                correction={
                    "id": "correction-001",
                    "text": "후보 A 제외",
                    "type": "exclude_candidate",
                    "target_candidate_ids": ["candidate-001"],
                    "constraint_updates": {},
                    "scope_terms": [],
                    "verification_fields": [],
                    "planned_action": "RERANK",
                },
            )

        self.assertEqual(before, len(engine.calls))
        self.assertEqual("awaiting_correction", state["state"])
        self.assertEqual("excluded", state["candidate_working_set"]["candidates"][0]["status"])

    def test_natural_language_correction_only_uses_parser_for_local_change(self):
        engine = FakeEngine([scout_output(), framing_output(), correction_output()])
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, _state = self.start(temp_dir, engine)
            _run_dir, state = LOOP.resume_next_loop(
                run_dir,
                engine=engine,
                correction_text="후보 A 빼",
            )

        names = [call[1].name for call in engine.calls]
        self.assertEqual("next-correction-1", names[-1])
        self.assertNotIn("dynamic-action-1", names)
        self.assertEqual("excluded", state["candidate_working_set"]["candidates"][0]["status"])

    def test_partial_research_reuses_source_scout_scan(self):
        engine = FakeEngine(
            [
                scout_output(),
                framing_output(),
                question_gate(),
                plan_output(),
                execution_output(),
                assessment_output(),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, _state = self.start(temp_dir, engine)
            _run_dir, state = LOOP.resume_next_loop(
                run_dir,
                engine=engine,
                correction={
                    "id": "correction-001",
                    "text": "오겹살도 포함",
                    "type": "scope_expand",
                    "target_candidate_ids": [],
                    "constraint_updates": {},
                    "scope_terms": ["오겹살"],
                    "verification_fields": [],
                    "planned_action": "PARTIAL_RESEARCH",
                },
            )

        names = [call[1].name for call in engine.calls]
        self.assertEqual("completed", state["state"])
        self.assertIn("next-question-gate", names)
        self.assertIn("dynamic-action-1", names)
        self.assertNotIn("dynamic-open-scan", names)
        action_prompt = next(prompt for prompt, invocation in engine.calls if invocation.name == "dynamic-action-1")
        self.assertIn("오겹살", action_prompt)
        self.assertIn("후보 A", action_prompt)


if __name__ == "__main__":
    unittest.main()
