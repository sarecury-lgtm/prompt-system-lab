import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_goal_aware_behavior_ab as AB  # noqa: E402


def answer_result(text: str) -> dict:
    return {"version": 1, "answer_markdown": text}


def assessment_result(case_id: str, preferred: str = "A") -> dict:
    return {
        "version": 1,
        "case_id": case_id,
        "candidates": [
            {
                "candidate_id": "A",
                "goal_fit": 5,
                "clarification_calibration": 5,
                "initiative": 5,
                "independent_judgment": 5,
                "evidence_priority": 5,
                "scope_control": 5,
                "tone": 5,
                "critical_failures": [],
                "finding": "필요한 행동만 직접 수행했다."
            },
            {
                "candidate_id": "B",
                "goal_fit": 3,
                "clarification_calibration": 3,
                "initiative": 2,
                "independent_judgment": 3,
                "evidence_priority": 3,
                "scope_control": 2,
                "tone": 4,
                "critical_failures": [],
                "finding": "핵심 행동이 약하거나 불필요한 설명이 있다."
            }
        ],
        "preferred_candidate_ids": [preferred],
        "conclusion": f"후보 {preferred}가 더 적합하다."
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


class GoalAwareBehaviorABTests(unittest.TestCase):
    def profile(self):
        return AB.OS.ModelProfile(
            model="fake-model",
            reasoning_effort="medium",
            web_search=False,
            sandbox="read-only",
        )

    def test_fixture_covers_behavior_and_overreach_guards(self):
        cases = AB.load_cases()
        self.assertEqual(8, len(cases))
        self.assertEqual(
            {
                "food",
                "chart",
                "product",
                "investment-research",
                "writing",
            },
            {case["domain"] for case in cases},
        )
        self.assertEqual(2, sum(1 for case in cases if case["guard_case"]))
        self.assertEqual(
            [2],
            [len(case["turns"]) for case in cases if case["id"] == "adapt-style-without-changing-truth"],
        )
        self.assertTrue(all(case["criteria"] for case in cases))
        self.assertTrue(all(case["critical_failures"] for case in cases))

    def test_candidate_prompt_adds_policy_without_changing_control_packet(self):
        case = AB.load_cases()[0]
        policy = AB.load_policy()
        baseline = AB.build_turn_prompt(
            case,
            case["turns"][0]["user_message"],
            [],
            None,
        )
        candidate = AB.build_turn_prompt(
            case,
            case["turns"][0]["user_message"],
            [],
            policy,
        )
        self.assertNotIn("[추가 행동 원칙]", baseline)
        self.assertIn("[추가 행동 원칙]", candidate)
        self.assertIn("핵심이 불분명", candidate)
        self.assertIn(case["context_markdown"], baseline)
        self.assertIn(case["context_markdown"], candidate)
        self.assertIn(case["turns"][0]["user_message"], baseline)
        self.assertIn(case["turns"][0]["user_message"], candidate)

    def test_two_turn_case_keeps_separate_histories_and_blindly_judges(self):
        case_id = "adapt-style-without-changing-truth"
        engine = FakeEngine(
            [
                answer_result("B가 더 낫습니다. 고장률이 더 낮습니다."),
                answer_result("A가 더 좋습니다."),
                answer_result("오래 쓰는 기준이면 B가 더 낫습니다."),
                answer_result("짧게 말하면 B입니다. 디자인을 더 중시할 때만 A를 고르세요."),
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
            blind_text = (output / case_id / "blind_review.md").read_text(encoding="utf-8")

            self.assertTrue(Path(result["report_path"]).is_file())
            self.assertTrue((output / case_id / "baseline" / "turn_02_answer.md").is_file())
            self.assertTrue((output / case_id / "goal_aware" / "turn_02_answer.md").is_file())
            self.assertTrue((output / case_id / "blind_assessment.json").is_file())
            self.assertNotIn("goal_aware", blind_text)
            self.assertNotIn("baseline", blind_text)
            self.assertIn("후보 A", blind_text)
            self.assertIn("후보 B", blind_text)
            self.assertEqual(
                [case["candidate_mapping"]["A"]],
                case["preferred_variants"],
            )
            self.assertIsNotNone(manifest["aggregate"])

        self.assertEqual(5, len(engine.calls))
        baseline_second = engine.calls[1]["prompt"]
        candidate_second = engine.calls[3]["prompt"]
        judge_prompt = engine.calls[4]["prompt"]
        self.assertIn("B가 더 낫습니다. 고장률이 더 낮습니다.", baseline_second)
        self.assertNotIn("오래 쓰는 기준이면 B가 더 낫습니다.", baseline_second)
        self.assertIn("오래 쓰는 기준이면 B가 더 낫습니다.", candidate_second)
        self.assertNotIn("goal_aware", judge_prompt)
        self.assertNotIn("baseline", judge_prompt)
        self.assertEqual([], engine.responses)

    def test_no_judge_still_writes_manual_blind_review(self):
        engine = FakeEngine(
            [
                answer_result("일정은 오늘 안으로 다시 안내드릴 수 있을 것 같습니다."),
                answer_result("일정은 오늘 안으로 다시 안내드릴 수 있을 것 같습니다."),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            result = AB.run_comparison(
                selected_case_ids=["do-not-overengineer-simple-request"],
                output_dir=output,
                judge=False,
                engine=engine,
                profile_override=self.profile(),
            )
            manifest = json.loads(
                Path(result["manifest_path"]).read_text(encoding="utf-8")
            )
            case = manifest["cases"][0]
            self.assertTrue((output / case["blind_review_path"]).is_file())
            self.assertIsNone(case["assessment"])
            self.assertIsNone(manifest["aggregate"])
        self.assertEqual(2, len(engine.calls))

    def test_unknown_case_is_rejected_before_engine_use(self):
        engine = FakeEngine([])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AB.GoalAwareBehaviorABError, "알 수 없는 case id"):
                AB.run_comparison(
                    selected_case_ids=["missing-case"],
                    output_dir=Path(directory) / "comparison",
                    engine=engine,
                    profile_override=self.profile(),
                )
        self.assertEqual([], engine.calls)

    def test_profile_must_be_offline_and_read_only(self):
        engine = FakeEngine([])
        bad = AB.OS.ModelProfile(
            model="fake-model",
            reasoning_effort="medium",
            web_search=True,
            sandbox="read-only",
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AB.GoalAwareBehaviorABError, "web_search 없는 read-only"):
                AB.run_comparison(
                    selected_case_ids=["do-not-overengineer-simple-request"],
                    output_dir=Path(directory) / "comparison",
                    engine=engine,
                    profile_override=bad,
                )


if __name__ == "__main__":
    unittest.main()
