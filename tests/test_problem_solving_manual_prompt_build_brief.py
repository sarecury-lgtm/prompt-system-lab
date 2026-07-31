import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_core_semantic_fixes as CORE_FIXES  # noqa: E402
import problem_solving_manual as MANUAL  # noqa: E402
import problem_solving_manual_prompt_brief as PROMPT_BRIEF_MANUAL  # noqa: E402
import problem_solving_manual_semantic_fixes as MANUAL_FIXES  # noqa: E402

from tests.test_problem_solving_manual_web import (  # noqa: E402
    execution_result,
    route_result,
)


CORE_FIXES.apply(MANUAL.problem_os)
MANUAL_FIXES.apply(MANUAL)


def brief_result(ledger):
    return {
        "version": 1,
        "goal": "다른 AI가 사용자의 요청을 반복 실행할 최종 프롬프트를 만들게 한다.",
        "core_procedure": [
            "핵심 판단 순서를 먼저 정한다.",
            "보조 규칙과 출력 형식을 핵심 절차에 종속시킨다.",
        ],
        "supporting_inputs": ["사용자가 제공한 입력"],
        "fixed_constraints": list(ledger["fixed_constraints"]),
        "output_contract": [ledger["completion_condition"]],
        "defaults_and_exceptions": [],
        "exclusions": ["같은 의미의 규칙을 반복하지 않는다."],
        "upstream_context": [],
    }


class ManualPromptBuildBriefTests(unittest.TestCase):
    def test_prompt_route_adds_brief_then_final_stage_and_preserves_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = PROMPT_BRIEF_MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                return_value="manual-prompt-brief",
            ):
                bridge.start(
                    "여러 시간대 차트를 분석하는 재사용 프롬프트를 만들어줘.",
                    research_mode="none",
                )
            routed_payload = route_result("PROMPT")
            brief_stage = bridge.submit(
                "manual-prompt-brief",
                json.dumps(routed_payload, ensure_ascii=False),
            )

            self.assertEqual("awaiting_primary_prompt_brief", brief_stage["state"])
            self.assertEqual("primary_prompt_brief", brief_stage["phase"])
            self.assertIn("Prompt Build Brief 컴파일러", brief_stage["prompt"])
            self.assertIn('"core_procedure"', brief_stage["prompt"])
            self.assertIn('"fixed_constraints"', brief_stage["prompt"])

            ledger = routed_payload["goal_ledger"]
            final_stage = bridge.submit(
                "manual-prompt-brief",
                json.dumps(brief_result(ledger), ensure_ascii=False),
            )

            self.assertEqual("awaiting_primary_prompt_final", final_stage["state"])
            self.assertEqual("primary_prompt_final", final_stage["phase"])
            self.assertIn("[Prompt Build Brief]", final_stage["prompt"])
            self.assertIn("<!-- PSOS_PROMPT_START -->", final_stage["prompt"])
            self.assertNotIn("[Goal Ledger]", final_stage["prompt"])
            self.assertNotIn("[기존 Prompt Compiler baseline]", final_stage["prompt"])
            self.assertNotIn("[사용자 요청]", final_stage["prompt"])

            finished = bridge.submit(
                "manual-prompt-brief",
                json.dumps(
                    execution_result(
                        result=(
                            "<!-- PSOS_PROMPT_START -->\n"
                            "# 최종 재사용 프롬프트\n\n"
                            "핵심 절차를 실행한다.\n"
                            "<!-- PSOS_PROMPT_END -->"
                        )
                    ),
                    ensure_ascii=False,
                ),
            )

            run_dir = runs / "manual-prompt-brief"
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            state = MANUAL.read_state(run_dir)
            output = (run_dir / "output.md").read_text(encoding="utf-8")
            brief_file_exists = (
                run_dir / "prompt_build_brief" / "primary" / "brief.json"
            ).is_file()
            legacy_input_exists = (
                run_dir
                / "prompt_build_brief"
                / "primary"
                / "original_executor_input.md"
            ).is_file()

        self.assertEqual("completed", finished["state"])
        self.assertIn("# 최종 재사용 프롬프트", output)
        self.assertNotIn("PSOS_PROMPT_START", output)
        self.assertIn("prompt_build_brief", route_record)
        self.assertEqual(
            "completed",
            route_record["prompt_build_brief"]["entries"]["primary"]["status"],
        )
        self.assertTrue(brief_file_exists)
        self.assertTrue(legacy_input_exists)
        self.assertEqual(
            ["router", "primary_prompt_brief", "primary_prompt_final"],
            [item["phase"] for item in state["history"]],
        )
        prompt_stages = [
            item["stage"]
            for item in route_record["run"]["model_plan"]
            if item.get("route") == "PROMPT"
        ]
        self.assertEqual(
            ["primary_prompt_brief", "primary_prompt_final"],
            prompt_stages,
        )

    def test_invalid_brief_keeps_brief_stage_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = PROMPT_BRIEF_MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                return_value="manual-invalid-brief",
            ):
                bridge.start("재사용 프롬프트를 만들어줘", research_mode="none")
            bridge.submit(
                "manual-invalid-brief",
                json.dumps(route_result("PROMPT"), ensure_ascii=False),
            )

            with self.assertRaises(PROMPT_BRIEF_MANUAL.manual.ManualBridgeError):
                bridge.submit(
                    "manual-invalid-brief",
                    json.dumps({"version": 1}, ensure_ascii=False),
                )
            session = bridge.get("manual-invalid-brief")

        self.assertEqual("awaiting_primary_prompt_brief", session["state"])
        self.assertEqual("primary_prompt_brief", session["phase"])
        self.assertIn("필드가 schema와 일치", session["error"])

    def test_non_prompt_route_keeps_existing_manual_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = PROMPT_BRIEF_MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                return_value="manual-direct-unchanged",
            ):
                bridge.start("바로 답해줘", research_mode="none")
            session = bridge.submit(
                "manual-direct-unchanged",
                json.dumps(route_result("DIRECT"), ensure_ascii=False),
            )

        self.assertEqual("awaiting_primary", session["state"])
        self.assertEqual("primary", session["phase"])
        self.assertNotIn("Prompt Build Brief 컴파일러", session["prompt"])


if __name__ == "__main__":
    unittest.main()
