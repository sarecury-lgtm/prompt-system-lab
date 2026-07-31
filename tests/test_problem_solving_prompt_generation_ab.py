import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_prompt_generation_ab as AB  # noqa: E402


def execution_result(prompt_text: str) -> dict:
    return {
        "execution": {
            "status": "completed",
            "summary": "최종 프롬프트를 생성했다.",
            "result_markdown": (
                f"{AB.BRIEF.PROMPT_OUTPUT_START}\n"
                f"{prompt_text}\n"
                f"{AB.BRIEF.PROMPT_OUTPUT_END}"
            ),
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [],
            "limitations": [],
        }
    }


def answer_result(text: str) -> dict:
    return {"version": 1, "answer_markdown": text}


def assessment_result(case_id: str) -> dict:
    return {
        "version": 1,
        "case_id": case_id,
        "candidates": [
            {
                "candidate_id": "A",
                "requirement_preservation": 5,
                "task_correctness": 5,
                "actionability": 5,
                "calibration": 5,
                "format_cost": 1,
                "critical_failures": [],
                "finding": "핵심 결론과 실행 순서가 직접 보인다."
            },
            {
                "candidate_id": "B",
                "requirement_preservation": 4,
                "task_correctness": 4,
                "actionability": 3,
                "calibration": 4,
                "format_cost": 4,
                "critical_failures": [],
                "finding": "조건은 보존하지만 형식 부담이 크다."
            }
        ],
        "preferred_candidate_ids": ["A"],
        "conclusion": "후보 A가 더 실용적이다."
    }


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def capabilities(self):
        return AB.OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=False,
            workspace_read=True,
            workspace_write=False,
            detail="fake",
        )

    def execute(self, prompt, run_dir, invocation):
        self.calls.append(
            {
                "prompt": prompt,
                "run_dir": run_dir,
                "name": invocation.name,
                "phase": invocation.phase,
                "route": invocation.route,
                "schema": invocation.schema_path,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected engine call")
        return self.responses.pop(0)

    def trace(self):
        return []


class PromptGenerationABTests(unittest.TestCase):
    def profile(self):
        return AB.OS.ModelProfile(
            model="fake-model",
            reasoning_effort="medium",
            web_search=False,
            sandbox="read-only",
        )

    def test_fixture_has_three_distinct_domains(self):
        cases = AB.load_cases()
        self.assertEqual(
            [
                "chart-trade-plan",
                "comment-natural-reply",
                "product-evidence-choice",
            ],
            [case["id"] for case in cases],
        )
        self.assertTrue(all(case["application"]["criteria"] for case in cases))
        self.assertTrue(all(case["application"]["critical_failures"] for case in cases))

    def test_runner_separates_legacy_and_brief_then_blindly_judges_answers(self):
        case_id = "comment-natural-reply"
        engine = FakeEngine(
            [
                execution_result("# 구형 생성 프롬프트\n상대 주장과 답글을 작성한다."),
                answer_result("구형 경로의 적용 답변"),
                execution_result("# Brief 생성 프롬프트\n핵심 주장과 답글을 바로 작성한다."),
                answer_result("Brief 경로의 적용 답변"),
                assessment_result(case_id),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            result = AB.run_comparison(
                selected_case_ids=[case_id],
                output_dir=output,
                engine=engine,
                profile_override=self.profile(),
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            case = manifest["cases"][0]
            application_input = AB.load_cases()[1]["application"]["input_markdown"]

            self.assertTrue(Path(result["report_path"]).is_file())
            self.assertEqual(case_id, case["id"])
            self.assertEqual(
                [case["candidate_mapping"]["A"]],
                case["preferred_variants"],
            )
            self.assertTrue(
                (output / case_id / "legacy_merge" / "final_prompt.md").is_file()
            )
            self.assertTrue(
                (output / case_id / "prompt_build_brief" / "application_answer.md").is_file()
            )

        by_name = {item["name"]: item["prompt"] for item in engine.calls}
        legacy = by_name[f"generation-ab-{case_id}-legacy_merge"]
        brief = by_name[f"generation-ab-{case_id}-prompt_build_brief"]
        legacy_apply = by_name[f"generation-ab-apply-{case_id}-legacy_merge"]
        brief_apply = by_name[f"generation-ab-apply-{case_id}-prompt_build_brief"]
        judge = by_name[f"generation-ab-assess-{case_id}"]

        self.assertIn("[Goal Ledger]", legacy)
        self.assertIn("[사용자 요청]", legacy)
        self.assertIn("[기존 Prompt Compiler baseline]", legacy)
        self.assertIn("[Prompt Build Brief]", brief)
        self.assertNotIn("[Goal Ledger]", brief)
        self.assertNotIn("[사용자 요청]", brief)
        self.assertNotIn("[기존 Prompt Compiler baseline]", brief)
        self.assertIn(application_input, legacy_apply)
        self.assertIn(application_input, brief_apply)
        self.assertNotIn("legacy_merge", judge)
        self.assertNotIn("prompt_build_brief", judge)
        self.assertIn("[후보 A]", judge)
        self.assertIn("[후보 B]", judge)
        self.assertEqual([], engine.responses)

    def test_generation_only_skips_application_and_assessment(self):
        engine = FakeEngine(
            [
                execution_result("# 구형 프롬프트\n결과를 작성한다."),
                execution_result("# Brief 프롬프트\n결과를 작성한다."),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            result = AB.run_comparison(
                selected_case_ids=["chart-trade-plan"],
                output_dir=Path(directory) / "comparison",
                apply_prompts=False,
                judge=False,
                engine=engine,
                profile_override=self.profile(),
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )

        case = manifest["cases"][0]
        self.assertIsNone(case["assessment"])
        self.assertEqual([], case["preferred_variants"])
        self.assertEqual(2, len(engine.calls))
        self.assertTrue(all(call["phase"] == "executor" for call in engine.calls))

    def test_unknown_case_is_rejected_before_engine_use(self):
        engine = FakeEngine([])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AB.PromptGenerationABError, "알 수 없는 case id"):
                AB.run_comparison(
                    selected_case_ids=["missing-case"],
                    output_dir=Path(directory) / "comparison",
                    engine=engine,
                    profile_override=self.profile(),
                )
        self.assertEqual([], engine.calls)

    def test_comparison_profile_must_be_offline_read_only(self):
        engine = FakeEngine([])
        bad = AB.OS.ModelProfile(
            model="fake-model",
            reasoning_effort="medium",
            web_search=True,
            sandbox="read-only",
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AB.PromptGenerationABError, "web_search 없는 read-only"):
                AB.run_comparison(
                    selected_case_ids=["chart-trade-plan"],
                    output_dir=Path(directory) / "comparison",
                    engine=engine,
                    profile_override=bad,
                )


if __name__ == "__main__":
    unittest.main()
