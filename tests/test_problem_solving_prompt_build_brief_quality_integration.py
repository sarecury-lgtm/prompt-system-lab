import json
import tempfile
import unittest
from pathlib import Path


from tests.test_problem_solving_os_contract_runtime import (
    FakeEngine,
    compiled_contract,
    execution_result,
    route_result,
)
from tests.test_problem_solving_os_quality_runtime import QUALITY, semantically_linked_assessment
from tests.test_problem_solving_prompt_build_brief import valid_brief


class RecordingFakeEngine(FakeEngine):
    def execute(self, prompt, run_dir, invocation):
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / f"{invocation.name}-request.md").write_text(
            prompt,
            encoding="utf-8",
        )
        response = super().execute(prompt, run_dir, invocation)
        (run_dir / f"{invocation.name}-output.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return response


class PromptBuildBriefQualityIntegrationTests(unittest.TestCase):
    def test_full_prompt_route_uses_single_brief_and_persists_diagnostics(self):
        routed = route_result("PROMPT")
        ledger = routed["goal_ledger"]
        engine = RecordingFakeEngine(
            [
                routed,
                compiled_contract("PROMPT"),
                valid_brief(ledger),
                execution_result(
                    "PROMPT",
                    result=(
                        "<!-- PSOS_PROMPT_START -->\n"
                        "# 재사용 프롬프트\n\n"
                        "핵심 절차를 먼저 수행하고 필요한 조건만 출력한다.\n"
                        "<!-- PSOS_PROMPT_END -->"
                    ),
                ),
                semantically_linked_assessment,
            ]
        )
        policy = QUALITY.OS.load_model_policy()

        with tempfile.TemporaryDirectory() as directory:
            run_dir, payload = QUALITY.run_request(
                "여러 시간대 차트를 분석하는 재사용 프롬프트를 만들어줘.",
                output_root=Path(directory),
                engine=engine,
                model_policy=policy,
                run_id="prompt-build-brief-integration",
            )
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            trace = json.loads(
                (run_dir / "prompt_generation_trace.json").read_text(
                    encoding="utf-8"
                )
            )
            output = (run_dir / "output.md").read_text(encoding="utf-8")

        executor_calls = [
            call
            for call in engine.calls
            if call["invocation"].phase == "executor"
            and call["invocation"].route == "PROMPT"
        ]
        self.assertEqual(1, len(executor_calls))
        executor_prompt = executor_calls[0]["prompt"]
        self.assertIn("[Prompt Build Brief]", executor_prompt)
        self.assertIn("<!-- PSOS_PROMPT_START -->", executor_prompt)
        self.assertIn("<!-- PSOS_PROMPT_END -->", executor_prompt)
        self.assertNotIn("[Goal Ledger]", executor_prompt)
        self.assertNotIn("[기존 Prompt Compiler baseline]", executor_prompt)
        self.assertNotIn("[사용자 요청]", executor_prompt)
        self.assertIn("# 재사용 프롬프트", output)
        self.assertNotIn("PSOS_PROMPT_START", output)
        self.assertEqual("applied", payload["prompt_build_brief"]["status"])
        self.assertEqual(2, trace["version"])
        self.assertTrue(
            trace["normalization"]["raw_parallel_surfaces_absent_from_executor"]
        )
        self.assertEqual(
            "intervention_applied",
            payload["prompt_generation_causal_audit"]["status"],
        )
        self.assertEqual(
            "superseded_by_prompt_build_brief",
            payload["prompt_ablation"]["status"],
        )
        self.assertEqual(payload["prompt_build_brief"], route_record["prompt_build_brief"])
        self.assertEqual(
            ["router", "contract", "prompt_brief", "executor", "assessment"],
            [call["invocation"].phase for call in engine.calls],
        )


if __name__ == "__main__":
    unittest.main()
