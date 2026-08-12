import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_dynamic_loop_experiment.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_dynamic_loop_experiment", MODULE_PATH)
LOOP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = LOOP
SPEC.loader.exec_module(LOOP)


def framing(*, external=True):
    return {
        "framing": {
            "goal_hypothesis": "실제로 사용할 수 있는 선택을 한다",
            "explicit_constraints": ["원문에 없는 취향을 확정하지 않는다"],
            "unknowns": [
                {
                    "question_area": "사용 목적",
                    "why_it_may_change_outcome": "선택 가능한 형태가 달라진다",
                    "externally_discoverable": False,
                }
            ],
            "external_landscape_matters": external,
        }
    }


def scan():
    return {
        "scan": {
            "terrain_summary": "문자 그대로의 명칭 밖에도 인접 선택지가 있다.",
            "vocabulary": ["인접 명칭"],
            "adjacent_possibilities": [
                {
                    "name": "예상 밖 후보",
                    "relation": "같은 사용 목적을 만족할 수 있음",
                    "source": "https://example.test/adjacent",
                }
            ],
            "observations": [
                {
                    "finding": "직접 확인된 시장 표현",
                    "source": "https://example.test/market",
                    "decision_relevance": "후보 범위를 넓힘",
                    "evidence_strength": "direct",
                }
            ],
            "source_gaps": [],
        }
    }


def question_gate(*, ask=False, proceed=True):
    questions = []
    if ask:
        questions = [
            {
                "id": "purpose",
                "text": "주된 사용 목적은 무엇인가요?",
                "why_changes_decision": "선택 형태가 달라진다",
                "observable_consequence": "제품의 형태와 규격을 바꾼다",
                "options": ["A", "B"],
            }
        ]
    return {
        "question_gate": {
            "questions": questions,
            "can_proceed_without_answers": proceed,
            "reason": "선택을 바꿀 질문만 남겼다.",
        }
    }


def plan(identifier, route, method, *, difference=None):
    return {
        "plan": {
            "candidate_actions": [
                {
                    "id": identifier,
                    "description": f"{method}을 실제 수행",
                    "method": method,
                    "route": route,
                    "information_target": "판단을 바꾸는 정보",
                    "expected_value": "높음",
                    "cost": "낮음",
                },
                {
                    "id": f"{identifier}-other",
                    "description": "다른 방식으로 확인",
                    "method": "대안 확인",
                    "route": "DIRECT",
                    "information_target": "반례",
                    "expected_value": "중간",
                    "cost": "낮음",
                },
            ],
            "selected_action_id": identifier,
            "selection_reason": "현재 가장 정보 가치가 높다.",
            "difference_from_previous": difference,
        }
    }


def execution(route="DIRECT", *, status="completed", result="사용 가능한 결과"):
    evidence = []
    if route == "RESEARCH":
        evidence = [
            {
                "source": "https://example.test/direct",
                "finding": "현재 상태를 직접 확인함",
                "kind": "web",
            }
        ]
    return {
        "execution": {
            "status": status,
            "summary": result,
            "result_markdown": result,
            "capabilities_used": [],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": evidence,
            "limitations": [] if status == "completed" else ["정보가 부족함"],
        }
    }


def assessment(verdict, *, change=None, questions=None):
    return {
        "assessment": {
            "verdict": verdict,
            "reason": "실제 결과와 근거만 평가했다.",
            "meaningful_information": [
                {
                    "claim": "선택을 바꾸는 직접 정보",
                    "source": "https://example.test/direct",
                    "decision_effect": "후보 우선순위를 바꿈",
                    "semantic_scope": "현재 상태",
                    "reliability": "strong",
                }
            ],
            "discarded_information": [],
            "missing_information": [] if verdict == "STOP" else ["다른 정보원"],
            "questions": questions or [],
            "required_change": change,
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
            raise AssertionError("unexpected engine call")
        return self.outputs.pop(0)

    def trace(self):
        return [
            {"name": invocation.name, "phase": invocation.phase}
            for _prompt, invocation in self.calls
        ]


class DynamicLoopExperimentTests(unittest.TestCase):
    def test_open_scan_is_independent_and_question_answer_reaches_action(self):
        engine = FakeEngine(
            [
                framing(external=True),
                scan(),
                question_gate(ask=True, proceed=False),
                plan("research", "RESEARCH", "시장 데이터 수집"),
                execution("RESEARCH", result="인접 후보까지 포함한 결과"),
                assessment("STOP"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = LOOP.run_dynamic_loop(
                "원문 요청",
                output_root=Path(temp_dir),
                engine=engine,
                answers={"purpose": "A"},
                context="이전에 실패한 제품은 템포크",
            )
            saved = (run_dir / "result.md").read_text(encoding="utf-8")

        scan_prompt = next(
            prompt for prompt, invocation in engine.calls if invocation.name == "dynamic-open-scan"
        )
        action_prompt = next(
            prompt for prompt, invocation in engine.calls if invocation.name == "dynamic-action-1"
        )
        self.assertEqual("completed", state["state"])
        self.assertNotIn("실제로 사용할 수 있는 선택을 한다", scan_prompt)
        self.assertNotIn("템포크", scan_prompt)
        self.assertIn("이전에 실패한 제품은 템포크", action_prompt)
        self.assertIn('"purpose": "A"', action_prompt)
        self.assertIn("인접 후보", saved)

    def test_change_requires_and_executes_a_materially_different_action(self):
        engine = FakeEngine(
            [
                framing(external=False),
                question_gate(),
                plan("direct", "DIRECT", "내부 추론"),
                execution("DIRECT", status="partial", result="불충분한 첫 결과"),
                assessment(
                    "CHANGE",
                    change={"dimension": "source", "instruction": "외부 직접 출처를 사용한다."},
                ),
                plan(
                    "research",
                    "RESEARCH",
                    "외부 직접 출처 조사",
                    difference="정보원을 내부 추론에서 직접 출처로 변경",
                ),
                execution("RESEARCH", result="직접 출처로 보완한 결과"),
                assessment("STOP"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            _run_dir, state = LOOP.run_dynamic_loop(
                "원문 요청",
                output_root=Path(temp_dir),
                engine=engine,
            )

        self.assertEqual("completed", state["state"])
        self.assertEqual(2, len(state["attempts"]))
        self.assertEqual("DIRECT", state["attempts"][0]["selected_action"]["route"])
        self.assertEqual("RESEARCH", state["attempts"][1]["selected_action"]["route"])

    def test_missing_required_answer_stops_before_action(self):
        engine = FakeEngine(
            [
                framing(external=False),
                question_gate(ask=True, proceed=False),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = LOOP.run_dynamic_loop(
                "원문 요청",
                output_root=Path(temp_dir),
                engine=engine,
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("awaiting_user", state["state"])
        self.assertEqual(1, len(state["pending_questions"]))
        self.assertIn("주된 사용 목적", result)
        self.assertFalse(any(call[1].name.startswith("dynamic-action") for call in engine.calls))

    def test_resume_uses_saved_scan_and_continues_after_answer(self):
        first_engine = FakeEngine(
            [
                framing(external=True),
                scan(),
                question_gate(ask=True, proceed=False),
            ]
        )
        second_engine = FakeEngine(
            [
                plan("research", "RESEARCH", "저장된 지형을 바탕으로 조사"),
                execution("RESEARCH", result="재검색 없이 이어서 만든 결과"),
                assessment("STOP"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, waiting = LOOP.run_dynamic_loop(
                "원문 요청",
                output_root=Path(temp_dir),
                engine=first_engine,
            )
            resumed_dir, state = LOOP.resume_dynamic_loop(
                run_dir,
                engine=second_engine,
                answers={"purpose": "A"},
            )
            saved = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("awaiting_user", waiting["state"])
        self.assertEqual(run_dir, resumed_dir)
        self.assertEqual("completed", state["state"])
        self.assertEqual(1, len(state["attempts"]))
        self.assertEqual(
            ["dynamic-action-1", "dynamic-executor-1", "dynamic-assessment-1"],
            [invocation.name for _prompt, invocation in second_engine.calls],
        )
        self.assertIn("재검색 없이", saved)
        self.assertEqual(6, len(state["engine_trace"]))

    def test_change_budget_returns_partial_instead_of_looping(self):
        engine = FakeEngine(
            [
                framing(external=False),
                question_gate(),
                plan("direct", "DIRECT", "내부 추론"),
                execution("DIRECT", status="partial", result="여전히 불충분"),
                assessment(
                    "CHANGE",
                    change={"dimension": "method", "instruction": "다른 방법을 사용한다."},
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = LOOP.run_dynamic_loop(
                "원문 요청",
                output_root=Path(temp_dir),
                engine=engine,
                max_changes=0,
            )
            saved = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("partial", state["state"])
        self.assertIn("허용된 방법 변경", state["final_execution"]["limitations"][-1])
        self.assertTrue(saved.startswith("## 미완료 — 완료 검증 미통과"))
        self.assertIn("최종 추천으로 사용하지 말 것", saved)


if __name__ == "__main__":
    unittest.main()
