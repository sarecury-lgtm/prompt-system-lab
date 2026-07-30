import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_prompt_trace", MODULE_PATH)
TRACE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TRACE
SPEC.loader.exec_module(TRACE)


def write_json(path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_prompt_run(root):
    run_dir = Path(root) / "prompt-trace"
    run_dir.mkdir()
    request = (
        "첨부된 여러 시간대 차트의 가격 구조, 추세, 거래량, 지지와 저항을 "
        "종합해 단타 매매 판단 프롬프트를 만들어 줘."
    )
    (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
    ledger = {
        "parent_goal": "차트 기반 단타 판단",
        "current_goal_hypothesis": "재사용 가능한 차트 분석 프롬프트 생성",
        "fixed_constraints": [
            "외부 뉴스는 사용하지 않음",
            "진입, 손절, 익절, 무효화 조건을 설명함",
            "확인할 수 없는 숫자를 만들지 않음",
        ],
        "current_position": "프롬프트 생성 전",
        "selected_route": "PROMPT",
        "secondary_route": None,
        "route_reason": "재사용 지침이 산출물",
        "current_step": "최종 프롬프트 생성",
        "why_this_step_matters": "반복 실행 가능한 결과가 필요함",
        "completion_condition": "복사해 사용할 수 있는 최종 프롬프트가 제공됨",
        "important_uncertainties": [],
    }
    write_json(run_dir / "goal_ledger.json", ledger)
    write_json(
        run_dir / "route.json",
        {
            "selected_route": "PROMPT",
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "재사용 지침이 산출물",
        },
    )
    baseline = {
        "version": "0.1",
        "request": request,
        "final_prompt": (
            "다음 사용자 요청을 수행하세요. 요청에 명시된 목표, 제약과 산출물을 "
            f"보존하세요.\n\n[사용자 요청]\n{request}\n\n"
            "[수행 및 출력 규칙]\n"
            "- 역할, 실제 목표, 고정 제약, 필요한 산출물을 분명히 구분하세요.\n"
            "- 초안의 누락과 모호함을 점검하고 수정한 뒤 요구사항 충족 여부를 다시 확인하세요.\n"
            "- 필수 필드, 값이 없을 때의 처리, 근거 규칙과 정확한 출력 형식을 정의하세요."
        ),
        "selected_mode": "pattern-only",
        "selection_reason": "패턴 적용",
        "used_patterns": [
            "Role + Task Frame",
            "Prompt Improvement Loop",
            "Structured Output / Extraction",
        ],
        "used_active_sources": [],
        "fallback": False,
        "fallback_reason": "",
    }
    executor = f"""당신은 Personal Problem-Solving OS의 PROMPT 실행기다.

라우터가 고정한 목표와 조건을 바꾸지 말고 현재 단계의 실제 결과를 만든다.

[공통 규칙]
1. 사용자에게 바로 쓸 수 있는 결과를 result_markdown에 넣는다.
2. 확인하지 않은 사실을 만들지 않는다.

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[사용자 요청]
{request}

[기존 Prompt Compiler baseline]
{json.dumps(baseline, ensure_ascii=False, indent=2)}
"""
    (run_dir / "primary-prompt-request.md").write_text(executor, encoding="utf-8")
    final_prompt = """# 차트 분석 프롬프트

## 분석 원칙

차트에서 확인되지 않은 숫자는 만들지 않는다.
가격 숫자가 선명하지 않으면 정확한 가격을 임의로 계산하지 않는다.
근거 없이 확실하다고 단정하지 않는다.
확률이나 성공률을 근거 없이 숫자로 표현하지 않는다.

## 시간대별 판단

높은 시간대에서 방향을 확인한다.
중간 시간대에서 진입 후보를 확인한다.
낮은 시간대에서 진입 신호를 확인한다.

## 진입 판단

손절 구조가 없으면 진입하지 않는다.
손절 기준을 정할 구조가 없으면 관망한다.

## 출력 형식

1. 결론
2. 시간대별 구조
3. 매수 근거
4. 반대 근거
5. 진입 계획
6. 손절 계획
7. 익절 계획
8. 확인 불가능한 정보

## 최종 주의사항

차트에서 확인되지 않은 내용을 사실처럼 단정하지 않는다.
확인할 수 없는 가격은 확인 불가라고 표시한다.
"""
    write_json(
        run_dir / "primary-prompt-output.json",
        {
            "execution": {
                "status": "completed",
                "summary": "프롬프트 생성",
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


class PromptGenerationTraceTests(unittest.TestCase):
    def test_trace_identifies_additive_and_repeated_generation_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_prompt_run(temp_dir)
            trace = TRACE.build_prompt_generation_trace(run_dir)

        self.assertEqual("PROMPT", trace["selected_route"])
        self.assertEqual(
            [
                "request",
                "goal_ledger",
                "prompt_compiler_baseline",
                "executor_input",
                "final_prompt",
            ],
            [stage["id"] for stage in trace["stages"]],
        )
        codes = {item["code"] for item in trace["structural_findings"]}
        self.assertIn("flat-ledger", codes)
        self.assertIn("additive-baseline", codes)
        self.assertIn("triple-input-surface", codes)
        self.assertIn("format-pressure", codes)
        self.assertGreater(len(trace["final_prompt_duplicate_pairs"]), 0)

    def test_trace_writes_reviewable_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = make_prompt_run(temp_dir)
            trace = TRACE.build_prompt_generation_trace(run_dir)
            record = TRACE.write_prompt_generation_trace(run_dir, trace)
            markdown = (run_dir / record["markdown_path"]).read_text(encoding="utf-8")
            saved = json.loads(
                (run_dir / record["json_path"]).read_text(encoding="utf-8")
            )

        self.assertEqual(trace, saved)
        self.assertIn("구조적 원인", markdown)
        self.assertIn("flat-ledger", markdown)
        self.assertGreater(record["finding_count"], 0)

    def test_non_prompt_run_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "request.txt").write_text("설명해 줘\n", encoding="utf-8")
            write_json(run_dir / "goal_ledger.json", {})
            write_json(
                run_dir / "route.json",
                {
                    "selected_route": "DIRECT",
                    "primary_route": None,
                    "secondary_route": None,
                },
            )
            self.assertIsNone(TRACE.build_prompt_generation_trace(run_dir))

    def test_core_trace_has_no_chart_specific_rules(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("피보나치", source)
        self.assertNotIn("이동평균", source)
        self.assertNotIn("복숭아", source)


if __name__ == "__main__":
    unittest.main()
