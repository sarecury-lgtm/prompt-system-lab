import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_manual.py"
SPEC = importlib.util.spec_from_file_location("chart_prompt_manual", MODULE_PATH)
MANUAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MANUAL
SPEC.loader.exec_module(MANUAL)


REQUEST = (
    "첨부된 ETF 여러 시간대 차트만 분석하는 단타 매매 보조 프롬프트를 만들어줘. "
    "외부 뉴스, 기업가치, 실적 전망은 사용하지 말고 가격 구조, 추세, 거래량, "
    "지지·저항, 피보나치를 종합해 진입 여부, 손절, 분할익절, 무효화 조건을 "
    "초보자도 이해할 수 있게 설명하도록 해줘."
)
FINAL_PROMPT = """# 단타 차트 분석 프롬프트

첨부된 차트에 보이는 정보만 사용한다.

가격 구조, 추세, 거래량, 지지·저항, 피보나치를 종합해 다음을 제시한다.

1. 지금 진입할 가치가 있는지
2. 판단이 틀렸다고 인정할 손절·무효화 가격
3. 분할익절 구간
4. 각 판단의 차트상 근거

외부 뉴스, 기업가치, 실적 전망을 사용하지 않으며 근거 없는 확신을 피한다.
"""


def route_result():
    reason = "재사용할 지침 자체가 최종 산출물이므로 PROMPT가 가장 작은 충분 경로"
    return {
        "goal_ledger": {
            "parent_goal": "차트만 보는 단타 매매 분석 프롬프트를 만든다.",
            "current_goal_hypothesis": "첨부 차트로 진입·손절·익절을 판단하는 재사용 프롬프트가 필요하다.",
            "fixed_constraints": [
                "외부 뉴스, 기업가치, 실적 전망을 사용하지 않는다.",
                "첨부된 여러 시간대 차트에 보이는 정보만 분석한다.",
                "초보자도 이해할 수 있게 설명한다.",
            ],
            "current_position": "프롬프트 작성 전",
            "selected_route": "PROMPT",
            "secondary_route": None,
            "route_reason": reason,
            "current_step": "재사용 가능한 최종 차트 분석 프롬프트를 작성한다.",
            "why_this_step_matters": "실제 차트에 반복 적용할 지침이 필요하다.",
            "completion_condition": "진입·손절·분할익절·무효화 조건을 요구하는 전체 프롬프트가 복사 가능하게 완성된다.",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": "PROMPT",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": reason,
        },
    }


def execution_result():
    return {
        "execution": {
            "status": "completed",
            "summary": "차트 분석 프롬프트 완성",
            "result_markdown": FINAL_PROMPT,
            "capabilities_used": ["ai_reasoning"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": [],
            "limitations": [],
        }
    }


class ChartPromptManualFlowTests(unittest.TestCase):
    def test_chart_prompt_finishes_without_research_and_exposes_only_output(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                return_value="chart-prompt-flow",
            ):
                started = bridge.start(REQUEST, research_mode="none")

            self.assertEqual("awaiting_router", started["state"])
            routed = bridge.submit(
                "chart-prompt-flow",
                json.dumps(route_result(), ensure_ascii=False),
            )
            self.assertEqual("awaiting_primary", routed["state"])
            self.assertEqual("PROMPT", routed["route"])
            self.assertNotIn("Deep research", routed["prompt"])
            self.assertIn("기존 Prompt Compiler baseline", routed["prompt"])
            self.assertIn("외부 뉴스", routed["prompt"])

            finished = bridge.submit(
                "chart-prompt-flow",
                json.dumps(execution_result(), ensure_ascii=False),
            )
            run_dir = runs / "chart-prompt-flow"
            output = (run_dir / "output.md").read_text(encoding="utf-8")
            audit = (run_dir / "result.md").read_text(encoding="utf-8")
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))

        self.assertEqual("completed", finished["state"])
        self.assertEqual(FINAL_PROMPT.strip(), finished["output_markdown"].strip())
        self.assertEqual(FINAL_PROMPT.strip(), output.strip())
        self.assertIn("현재 목표:", audit)
        self.assertEqual("PROMPT", route["selected_route"])
        self.assertEqual("none", route["manual_bridge"]["research_mode"])


if __name__ == "__main__":
    unittest.main()
