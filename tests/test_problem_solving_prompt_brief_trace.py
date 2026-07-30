import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = ROOT / "scripts" / "problem_solving_prompt_build_brief.py"
TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_brief_trace.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BRIEF = load_module("prompt_build_brief_for_trace_test", BRIEF_PATH)
TRACE = load_module("prompt_brief_trace_test", TRACE_PATH)

from tests.test_problem_solving_os_contract_runtime import (  # noqa: E402
    FakeEngine,
    OS,
    execution_result,
    route_result,
)
from tests.test_problem_solving_prompt_build_brief import valid_brief  # noqa: E402


class PromptBriefTraceTests(unittest.TestCase):
    def test_traces_legacy_input_brief_and_validated_output_separately(self):
        request = "여러 시간대 차트를 분석하는 재사용 프롬프트를 만들어줘."
        routed = route_result("PROMPT")
        ledger = routed["goal_ledger"]
        profile = OS.load_model_policy()["routes"]["PROMPT"]["primary"]
        capabilities = OS.EngineCapabilities(True, True, True, False, "fixture")
        baseline = {
            "version": "0.1",
            "request": request,
            "final_prompt": f"[사용자 요청]\n{request}\n\n[수행 및 출력 규칙]\n- 전부 보존",
            "selected_mode": "pattern-only",
            "selection_reason": "fixture",
            "used_patterns": [],
            "used_active_sources": [],
            "fallback": False,
            "fallback_reason": "",
        }
        original = OS.build_execution_prompt(
            "PROMPT",
            request,
            ledger,
            "",
            None,
            capabilities,
            profile,
            prompt_compiler_baseline=baseline,
        )
        engine = FakeEngine(
            [
                routed,
                valid_brief(ledger),
                execution_result("PROMPT", result="# 최초 프롬프트\n\n핵심 절차를 따른다."),
            ],
            capabilities=capabilities,
        )
        wrapped = BRIEF.PromptBuildBriefEngine(
            engine,
            request=request,
            os_module=OS,
        )
        router_invocation = OS.InvocationSpec(
            "router", "router", None, profile, OS.ROUTE_SCHEMA_PATH
        )
        executor_invocation = OS.InvocationSpec(
            "primary-prompt", "executor", "PROMPT", profile, OS.EXECUTION_SCHEMA_PATH
        )

        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
            (run_dir / "goal_ledger.json").write_text(
                json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            wrapped.execute("router", run_dir, router_invocation)
            result = wrapped.execute(original, run_dir, executor_invocation)
            final_prompt = engine.calls[-1]["prompt"]
            (run_dir / "primary-prompt-request.md").write_text(
                final_prompt,
                encoding="utf-8",
            )
            (run_dir / "primary-prompt-output.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            validated_execution = {
                **result["execution"],
                "result_markdown": "# 검증 후 최종 프롬프트\n\n중복을 제거한 결과다.",
            }
            payload = {
                "prompt_build_brief": wrapped.record(),
                "execution": validated_execution,
            }
            trace = TRACE.build_prompt_brief_trace(run_dir, payload)
            record = TRACE.attach_prompt_brief_trace(run_dir, payload)
            markdown = (run_dir / record["markdown_path"]).read_text(encoding="utf-8")

        self.assertEqual(2, trace["version"])
        self.assertEqual(
            "payload.execution.result_markdown",
            trace["final_prompt_source"],
        )
        self.assertTrue(
            trace["normalization"]["raw_parallel_surfaces_absent_from_executor"]
        )
        self.assertEqual(
            [
                "legacy_executor_input",
                "prompt_build_brief",
                "executor_input",
                "final_prompt",
            ],
            [item["id"] for item in trace["pipeline"]],
        )
        final_metrics = trace["pipeline"][-1]["metrics"]
        self.assertEqual(len(validated_execution["result_markdown"]), final_metrics["characters"])
        self.assertIn("이전 병렬 합류 입력", markdown)
        self.assertIn("Prompt Build Brief", markdown)
        self.assertIn("원문·전체 Ledger·baseline 표면 제거: 예", markdown)
        self.assertIn("payload.execution.result_markdown", markdown)


if __name__ == "__main__":
    unittest.main()
