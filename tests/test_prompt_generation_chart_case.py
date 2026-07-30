import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "prompt-generation-chart-case.json"
SPEC = importlib.util.spec_from_file_location("problem_solving_prompt_trace_chart", MODULE_PATH)
TRACE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TRACE
SPEC.loader.exec_module(TRACE)


def write_json(path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_chart_run(root):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    run_dir = Path(root) / "chart-prompt-case"
    run_dir.mkdir()
    request = fixture["request"]
    ledger = fixture["ledger"]
    baseline = fixture["baseline"]
    final_prompt = fixture["final_prompt"]

    (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
    write_json(run_dir / "goal_ledger.json", ledger)
    write_json(
        run_dir / "route.json",
        {
            "selected_route": "PROMPT",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": ledger["route_reason"],
        },
    )
    executor = f"""당신은 Personal Problem-Solving OS의 PROMPT 실행기다.

라우터가 고정한 목표와 조건을 바꾸지 말고 현재 단계의 실제 결과를 만든다.

[이 경로의 행동]
기존 Prompt Compiler baseline을 출발점으로 삼아 다른 AI가 반복 실행할 최종 프롬프트 하나를 완성한다. baseline을 바꿀 때는 목적·제약·출력 계약을 보존한다.

[공통 규칙]
1. 사용자에게 바로 쓸 수 있는 결과를 result_markdown에 넣는다.
2. 확인하지 않은 사실을 만들지 않는다.
3. 완료 상태에서는 요청된 최종 내용 자체를 쓴다.

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[사용자 요청]
{request}

[기존 Prompt Compiler baseline]
{json.dumps(baseline, ensure_ascii=False, indent=2)}
"""
    (run_dir / "primary-prompt-request.md").write_text(executor, encoding="utf-8")
    write_json(
        run_dir / "primary-prompt-output.json",
        {
            "execution": {
                "status": "completed",
                "summary": "단타 차트 분석 프롬프트 생성",
                "result_markdown": final_prompt,
                "capabilities_used": ["ai_reasoning", "prompt_compiler"],
                "needed_capability": None,
                "handoff": None,
                "artifacts": [],
                "evidence": [],
                "limitations": [],
            }
        },
    )
    return run_dir


class RealChartPromptGenerationCaseTests(unittest.TestCase):
    def test_real_chart_case_exposes_where_the_prompt_expands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            trace = TRACE.build_prompt_generation_trace(make_chart_run(temp_dir))

        stages = {stage["id"]: stage["metrics"] for stage in trace["stages"]}
        findings = {item["code"]: item for item in trace["structural_findings"]}
        largest = findings["largest-expansion"]
        summary = {
            "stage_characters": {
                stage_id: metrics["characters"] for stage_id, metrics in stages.items()
            },
            "stage_headings": {
                stage_id: metrics["headings"] for stage_id, metrics in stages.items()
            },
            "final_safety_marker_hits": stages["final_prompt"]["safety_marker_hits"],
            "final_rule_marker_hits": stages["final_prompt"]["rule_marker_hits"],
            "duplicate_pair_count": len(trace["final_prompt_duplicate_pairs"]),
            "largest_expansion_stage": largest["stage"],
            "largest_expansion_finding": largest["finding"],
            "finding_codes": sorted(findings),
        }
        print("CHART_PROMPT_TRACE=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))

        self.assertGreater(
            stages["final_prompt"]["characters"],
            stages["request"]["characters"] * 10,
        )
        self.assertGreater(stages["final_prompt"]["headings"], 8)
        self.assertGreaterEqual(stages["final_prompt"]["safety_marker_hits"], 8)
        self.assertGreater(len(trace["final_prompt_duplicate_pairs"]), 0)
        self.assertTrue(
            {
                "flat-ledger",
                "additive-baseline",
                "triple-input-surface",
                "final-semantic-repetition",
                "format-pressure",
                "safety-rule-dominance",
                "coverage-reward",
                "largest-expansion",
            }.issubset(findings)
        )

    def test_real_case_fixture_remains_a_prompt_not_a_system_report(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        final_prompt = fixture["final_prompt"]
        self.assertTrue(final_prompt.startswith("# 단타 차트 분석 프롬프트"))
        self.assertNotIn("수동 ChatGPT 브리지는", final_prompt)
        self.assertNotIn("남은 핵심 한계", final_prompt)


if __name__ == "__main__":
    unittest.main()
