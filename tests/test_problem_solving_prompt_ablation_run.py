import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_ablation_run.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_ablation_run",
    MODULE_PATH,
)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

from tests.test_problem_solving_prompt_trace import make_prompt_run  # noqa: E402


class FakeAblationEngine:
    def __init__(self):
        self.calls = []

    def capabilities(self):
        return RUNNER.OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=False,
            workspace_read=True,
            workspace_write=False,
            detail="fake ablation engine",
        )

    def execute(self, prompt, run_dir, invocation):
        run_dir.mkdir(parents=True, exist_ok=True)
        self.calls.append(
            {
                "name": invocation.name,
                "phase": invocation.phase,
                "prompt": prompt,
            }
        )
        if invocation.phase == "assessment":
            candidate_ids = []
            for candidate_id in ("A", "B", "C", "D"):
                if f"[후보 {candidate_id}]" in prompt:
                    candidate_ids.append(candidate_id)
            return {
                "version": 1,
                "variants": [
                    {
                        "candidate_id": candidate_id,
                        "requirement_preservation": "satisfied",
                        "procedure_clarity": "strong" if index == 0 else "mixed",
                        "repetition_pressure": "low" if index == 0 else "medium",
                        "format_pressure": "low" if index == 0 else "medium",
                        "practical_reusability": "strong" if index == 0 else "mixed",
                        "finding": "핵심 절차와 조건 보존을 비교함",
                        "missing_conditions": [],
                    }
                    for index, candidate_id in enumerate(candidate_ids)
                ],
                "preferred_candidate_ids": [candidate_ids[0]],
                "conclusion": "첫 후보가 조건을 보존하면서 절차가 가장 선명함",
            }

        marker = {
            "ablation-without_raw_request": "원문 중복 제거",
            "ablation-compact_ledger": "축약 Ledger",
            "ablation-single_build_brief": "단일 brief",
        }[invocation.name]
        return {
            "execution": {
                "status": "completed",
                "summary": f"{marker} 결과",
                "result_markdown": (
                    f"# {marker} 프롬프트\n\n"
                    "먼저 핵심 판단 절차를 따른다. 차트의 추세와 현재 위치를 확인하고 "
                    "손절 구조와 가까운 목표를 비교해 진입 여부를 결정한다. "
                    "확인할 수 없는 숫자는 만들지 않는다."
                ),
                "capabilities_used": ["ai_reasoning", "prompt_compiler"],
                "needed_capability": None,
                "handoff": None,
                "artifacts": [],
                "evidence": [],
                "limitations": [],
            }
        }

    def trace(self):
        return []


def add_original_model_trace(run_dir):
    route_path = run_dir / "route.json"
    route = json.loads(route_path.read_text(encoding="utf-8"))
    route["run"] = {
        "engine_trace": [
            {
                "name": "primary-prompt",
                "phase": "executor",
                "route": "PROMPT",
                "model": "gpt-test",
                "reasoning_effort": "high",
                "web_search": False,
                "requested_sandbox": "read-only",
                "status": "completed",
            }
        ],
        "model_plan": [],
    }
    route_path.write_text(
        json.dumps(route, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class PromptAblationRunTests(unittest.TestCase):
    def test_executes_three_new_variants_and_blind_judge_without_overwriting_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_prompt_run(temp_dir)
            add_original_model_trace(run_dir)
            original_path = run_dir / "primary-prompt-output.json"
            original_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
            engine = FakeAblationEngine()
            profile = RUNNER.OS.ModelProfile(
                model="gpt-test",
                reasoning_effort="high",
                web_search=False,
                sandbox="read-only",
            )

            record = RUNNER.run_prompt_ablation(
                run_dir,
                engine=engine,
                profile_override=profile,
            )
            report = json.loads(
                (run_dir / record["report_path"]).read_text(encoding="utf-8")
            )
            markdown = (run_dir / record["markdown_path"]).read_text(encoding="utf-8")

            self.assertEqual(original_hash, hashlib.sha256(original_path.read_bytes()).hexdigest())
            self.assertEqual(4, len(engine.calls))
            self.assertEqual(
                {
                    "ablation-without_raw_request",
                    "ablation-compact_ledger",
                    "ablation-single_build_brief",
                    "ablation-blind-assessment",
                },
                {call["name"] for call in engine.calls},
            )
            self.assertTrue(record["assessment_completed"])
            self.assertEqual(set(RUNNER.VARIANT_ORDER), set(report["results"]))
            self.assertTrue(report["original_result_preserved"])
            self.assertIn("블라인드 평가", markdown)
            self.assertIn("실제 차트 이미지", markdown)
            for variant in RUNNER.VARIANT_ORDER:
                self.assertTrue((run_dir / report["results"][variant]["result_path"]).is_file())

    def test_reuses_cached_results_without_model_calls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_prompt_run(temp_dir)
            add_original_model_trace(run_dir)
            profile = RUNNER.OS.ModelProfile(
                model="gpt-test",
                reasoning_effort="high",
                web_search=False,
                sandbox="read-only",
            )
            first_engine = FakeAblationEngine()
            RUNNER.run_prompt_ablation(
                run_dir,
                engine=first_engine,
                profile_override=profile,
            )
            second_engine = FakeAblationEngine()
            record = RUNNER.run_prompt_ablation(
                run_dir,
                engine=second_engine,
                profile_override=profile,
            )

            self.assertEqual([], second_engine.calls)
            self.assertTrue(record["assessment_completed"])

    def test_resolves_exact_original_prompt_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_prompt_run(temp_dir)
            add_original_model_trace(run_dir)
            profile = RUNNER._actual_prompt_profile(run_dir)

        self.assertEqual("gpt-test", profile.model)
        self.assertEqual("high", profile.reasoning_effort)
        self.assertFalse(profile.web_search)
        self.assertEqual("read-only", profile.sandbox)


if __name__ == "__main__":
    unittest.main()
