import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_build_brief.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_build_brief",
    MODULE_PATH,
)
BRIEF = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = BRIEF
SPEC.loader.exec_module(BRIEF)

from tests.test_problem_solving_os_contract_runtime import (  # noqa: E402
    FakeEngine,
    OS,
    execution_result,
    route_result,
)


def valid_brief(ledger):
    return {
        "version": 1,
        "goal": "다른 AI가 여러 시간대 차트에서 매매 결정을 만들게 한다.",
        "core_procedure": [
            "상위 시간대의 방향과 핵심 가격 구간을 확인한다.",
            "현재 위치와 무효화 구조를 확인한다.",
            "가까운 목표와 손절 위험을 비교해 진입·대기·비추천 중 하나를 선택한다.",
        ],
        "supporting_inputs": ["가격 구조", "거래량", "지지·저항", "피보나치"],
        "fixed_constraints": list(ledger["fixed_constraints"]),
        "output_contract": [ledger["completion_condition"], "실행 가능한 매매 계획"],
        "defaults_and_exceptions": ["숫자를 읽을 수 없으면 조건과 구간으로 표현한다."],
        "exclusions": ["뉴스와 실적을 임의로 추가하지 않는다."],
        "upstream_context": [],
    }


class PromptBuildBriefTests(unittest.TestCase):
    def setUp(self):
        self.request = (
            "여러 시간대 차트의 추세, 거래량, 지지·저항, 피보나치를 종합해 "
            "진입·손절·분할익절·무효화 조건을 설명하는 재사용 프롬프트를 만들어줘."
        )
        self.routed = route_result("PROMPT")
        self.ledger = self.routed["goal_ledger"]
        self.profile = OS.load_model_policy()["routes"]["PROMPT"]["primary"]
        self.capabilities = OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fixture",
        )
        self.baseline = {
            "version": "0.1",
            "request": self.request,
            "final_prompt": (
                "다음 사용자 요청을 수행하세요.\n\n"
                f"[사용자 요청]\n{self.request}\n\n"
                "[수행 및 출력 규칙]\n- 역할과 산출물을 구분하세요."
            ),
            "selected_mode": "pattern-only",
            "selection_reason": "fixture",
            "used_patterns": ["Role + Task Frame"],
            "used_active_sources": [],
            "fallback": False,
            "fallback_reason": "",
        }

    def executor_prompt(self):
        prompt = OS.build_execution_prompt(
            "PROMPT",
            self.request,
            self.ledger,
            "",
            None,
            self.capabilities,
            self.profile,
            prompt_compiler_baseline=self.baseline,
        )
        return (
            prompt.rstrip()
            + "\n\n[Result Contract]\n검증용 계약\n"
            + json.dumps({"required_outputs": ["goal-completion"]}, ensure_ascii=False)
        )

    def test_validates_exact_constraints_and_completion(self):
        validated = BRIEF.validate_prompt_build_brief(
            valid_brief(self.ledger),
            self.ledger,
        )
        self.assertEqual(self.ledger["fixed_constraints"], validated["fixed_constraints"])
        self.assertEqual(
            self.ledger["completion_condition"],
            validated["output_contract"][0],
        )

        invalid = valid_brief(self.ledger)
        invalid["fixed_constraints"] = []
        with self.assertRaises(BRIEF.PromptBuildBriefError):
            BRIEF.validate_prompt_build_brief(invalid, self.ledger)

    def test_executor_receives_only_brief_surface_and_contract(self):
        engine = FakeEngine(
            [
                self.routed,
                valid_brief(self.ledger),
                execution_result("PROMPT", result="# 최종 프롬프트"),
            ],
            capabilities=self.capabilities,
        )
        wrapped = BRIEF.PromptBuildBriefEngine(
            engine,
            request=self.request,
            os_module=OS,
        )
        router_invocation = OS.InvocationSpec(
            name="router",
            phase="router",
            route=None,
            profile=self.profile,
            schema_path=OS.ROUTE_SCHEMA_PATH,
        )
        executor_invocation = OS.InvocationSpec(
            name="primary-prompt",
            phase="executor",
            route="PROMPT",
            profile=self.profile,
            schema_path=OS.EXECUTION_SCHEMA_PATH,
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            wrapped.execute("router prompt", run_dir, router_invocation)
            result = wrapped.execute(self.executor_prompt(), run_dir, executor_invocation)
            record = wrapped.record()
            brief_exists = (run_dir / record["entries"][0]["brief_path"]).is_file()
            original_exists = (
                run_dir / record["entries"][0]["original_executor_input_path"]
            ).is_file()

        final_prompt = engine.calls[-1]["prompt"]
        self.assertEqual("# 최종 프롬프트", result["execution"]["result_markdown"])
        self.assertEqual("prompt_brief", engine.calls[1]["invocation"].phase)
        self.assertIn(BRIEF.BRIEF_MARKER, final_prompt)
        self.assertIn("가까운 목표와 손절 위험", final_prompt)
        self.assertIn("[Result Contract]", final_prompt)
        self.assertNotIn("[Goal Ledger]", final_prompt)
        self.assertNotIn(BRIEF.BASELINE_MARKER, final_prompt)
        self.assertNotIn(f"[사용자 요청]\n{self.request}", final_prompt)
        self.assertTrue(brief_exists)
        self.assertTrue(original_exists)
        self.assertTrue(record["entries"][0]["delivered_to_executor"])

    def test_invalid_model_brief_uses_bounded_fallback(self):
        engine = FakeEngine(
            [
                self.routed,
                {"version": 1},
                execution_result("PROMPT", result="# fallback 결과"),
            ],
            capabilities=self.capabilities,
        )
        wrapped = BRIEF.PromptBuildBriefEngine(
            engine,
            request=self.request,
            os_module=OS,
        )
        router_invocation = OS.InvocationSpec(
            name="router",
            phase="router",
            route=None,
            profile=self.profile,
            schema_path=OS.ROUTE_SCHEMA_PATH,
        )
        executor_invocation = OS.InvocationSpec(
            name="primary-prompt",
            phase="executor",
            route="PROMPT",
            profile=self.profile,
            schema_path=OS.EXECUTION_SCHEMA_PATH,
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            wrapped.execute("router prompt", run_dir, router_invocation)
            wrapped.execute(self.executor_prompt(), run_dir, executor_invocation)
            record = wrapped.record()

        final_prompt = engine.calls[-1]["prompt"]
        self.assertEqual("deterministic_fallback", record["entries"][0]["generation"])
        self.assertIn(self.ledger["current_step"], final_prompt)
        self.assertIn(self.ledger["completion_condition"], final_prompt)

    def test_non_prompt_executor_is_unchanged(self):
        engine = FakeEngine([execution_result("DIRECT")], capabilities=self.capabilities)
        wrapped = BRIEF.PromptBuildBriefEngine(
            engine,
            request="캐시를 설명해줘",
            os_module=OS,
        )
        invocation = OS.InvocationSpec(
            name="primary-direct",
            phase="executor",
            route="DIRECT",
            profile=OS.load_model_policy()["routes"]["DIRECT"]["primary"],
            schema_path=OS.EXECUTION_SCHEMA_PATH,
        )
        wrapped.execute("unchanged prompt", Path("."), invocation)
        self.assertEqual("unchanged prompt", engine.calls[0]["prompt"])
        self.assertIsNone(wrapped.record())


if __name__ == "__main__":
    unittest.main()
