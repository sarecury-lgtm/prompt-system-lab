import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = load("psos_semantic_fix_test_os", ROOT / "scripts" / "problem_solving_os.py")
FIXES = load(
    "psos_semantic_fix_test_module",
    ROOT / "scripts" / "problem_solving_core_semantic_fixes.py",
)
FIXES.apply(OS)


def route_payload(*, selected="DIRECT", primary=None, secondary=None, constraints=None):
    reason = "가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "요청 해결",
            "current_goal_hypothesis": "요청한 결과를 만든다.",
            "fixed_constraints": [] if constraints is None else constraints,
            "current_position": "시작 단계",
            "selected_route": selected,
            "secondary_route": secondary,
            "route_reason": reason,
            "current_step": "실제 결과를 만든다.",
            "why_this_step_matters": "사용자가 결과를 필요로 한다.",
            "completion_condition": "바로 사용할 결과가 완성된다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": selected,
            "primary_route": primary,
            "secondary_route": secondary,
            "route_reason": reason,
        },
    }


def execution(status="completed", *, needed=None, handoff=None, limitations=None):
    return {
        "execution": {
            "status": status,
            "summary": "결과",
            "result_markdown": "완성 결과",
            "capabilities_used": [],
            "needed_capability": needed,
            "handoff": handoff,
            "artifacts": [],
            "evidence": [],
            "limitations": limitations or [],
        }
    }


class SemanticCoreFixTests(unittest.TestCase):
    def setUp(self):
        self.profile = OS.ModelProfile("test-model", "none", False, "read-only")
        self.capabilities = OS.EngineCapabilities(True, False, False, False)

    def test_router_accepts_no_user_fixed_constraints(self):
        validated = OS.validate_route_output(route_payload())
        self.assertEqual(validated["goal_ledger"]["fixed_constraints"], [])

    def test_single_route_rejects_non_null_primary(self):
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_route_output(route_payload(primary="DIRECT"))

    def test_router_prompt_explains_empty_constraints_and_hybrid_order(self):
        prompt = OS.build_router_prompt(
            "첨부 차트를 분석해줘", "", None, self.capabilities
        )
        self.assertIn("fixed_constraints는 빈 배열", prompt)
        self.assertIn("primary_route는 먼저 만들어야 하는 선행 결과", prompt)
        self.assertIn("첨부 이미지", prompt)

    def test_completed_execution_rejects_handoff(self):
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_execution_output(
                execution(handoff="다음에 하세요"),
                "DIRECT",
                self.profile,
                self.capabilities,
            )

    def test_blocked_execution_requires_actionable_handoff(self):
        with self.assertRaises(OS.ProblemSolvingError):
            OS.validate_execution_output(
                execution("blocked_by_capability", needed="웹 검색"),
                "DIRECT",
                self.profile,
                self.capabilities,
            )

    def test_hybrid_merge_preserves_both_limitations(self):
        primary = execution("partial", limitations=["주 경로 한계"])["execution"]
        secondary = execution("completed", limitations=["보조 경로 한계"])["execution"]
        merged = OS.merge_executions("RESEARCH", primary, "PROMPT", secondary)
        self.assertEqual(merged["status"], "partial")
        self.assertEqual(
            merged["limitations"], ["주 경로 한계", "보조 경로 한계"]
        )


if __name__ == "__main__":
    unittest.main()
