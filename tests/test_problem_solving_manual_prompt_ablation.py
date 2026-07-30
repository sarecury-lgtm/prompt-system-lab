import hashlib
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

import problem_solving_manual as MANUAL  # noqa: E402
import problem_solving_manual_prompt_ablation as ABLATION  # noqa: E402
import problem_solving_manual_semantic_fixes as MANUAL_FIXES  # noqa: E402

from tests.test_problem_solving_manual_web import (  # noqa: E402
    execution_result,
    route_result,
)

MANUAL_FIXES.apply(MANUAL)


def assessment_result():
    return {
        "version": 1,
        "variants": [
            {
                "candidate_id": candidate_id,
                "requirement_preservation": "satisfied",
                "procedure_clarity": "strong" if candidate_id == "D" else "mixed",
                "repetition_pressure": "low" if candidate_id == "D" else "medium",
                "format_pressure": "low" if candidate_id == "D" else "medium",
                "practical_reusability": "strong" if candidate_id == "D" else "mixed",
                "finding": "목표와 조건을 보존하면서 핵심 절차가 더 먼저 보인다.",
                "missing_conditions": [],
            }
            for candidate_id in ("A", "B", "C", "D")
        ],
        "preferred_candidate_ids": ["D"],
        "conclusion": "한 후보가 조건을 유지하면서 규칙과 출력 형식의 반복을 가장 잘 줄였다.",
    }


class ManualPromptAblationTests(unittest.TestCase):
    def make_parent(self, runs, bridge, route="PROMPT"):
        bridge.start(
            "여러 시간대 차트의 추세, 거래량, 지지·저항, 피보나치를 종합해 "
            "진입·손절·분할익절·무효화 조건을 설명하는 재사용 프롬프트를 만들어줘.",
            research_mode="none",
        )
        bridge.submit(
            "manual-parent",
            json.dumps(route_result(route), ensure_ascii=False),
        )
        return bridge.submit(
            "manual-parent",
            json.dumps(
                execution_result(
                    result=(
                        "# 기존 차트 프롬프트\n\n"
                        "## 분석 원칙\n확인할 수 없는 숫자를 만들지 않는다.\n\n"
                        "## 출력 형식\n1. 결론\n2. 시간대별 구조\n3. 진입 계획\n"
                    )
                ),
                ensure_ascii=False,
            ),
        )

    def test_runs_three_variants_then_blind_assessment_and_preserves_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            comparison = ABLATION.ManualPromptAblation(
                bridge,
                MANUAL,
                MANUAL.problem_os,
            )
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                side_effect=["manual-parent", "manual-comparison"],
            ):
                parent = self.make_parent(runs, bridge)
                parent_output = runs / "manual-parent" / "output.md"
                parent_hash = hashlib.sha256(parent_output.read_bytes()).hexdigest()

                session = comparison.start("manual-parent")
                self.assertEqual("manual-comparison", session["run_id"])
                self.assertEqual("prompt_ablation", session["session_kind"])
                self.assertEqual(
                    "ablation_without_raw_request",
                    session["phase"],
                )
                self.assertEqual(1, session["prompt"].count(parent["request"]))

                session = comparison.submit(
                    "manual-comparison",
                    json.dumps(
                        execution_result(
                            result=(
                                "# 원문 중복 제거\n\n"
                                "추세와 현재 위치를 보고 손절 구조와 가까운 목표를 비교한다. "
                                "확인할 수 없는 숫자는 만들지 않는다."
                            )
                        ),
                        ensure_ascii=False,
                    ),
                )
                self.assertEqual("ablation_compact_ledger", session["phase"])
                self.assertIn("[Compact Goal Contract]", session["prompt"])

                session = comparison.submit(
                    "manual-comparison",
                    json.dumps(
                        execution_result(
                            result=(
                                "# 축약 Ledger\n\n"
                                "상위 시간대 방향, 현재 위치, 무효화 구조와 가까운 목표를 "
                                "순서대로 확인해 진입 여부를 정한다."
                            )
                        ),
                        ensure_ascii=False,
                    ),
                )
                self.assertEqual("ablation_single_build_brief", session["phase"])
                self.assertIn("[Prompt Build Brief]", session["prompt"])
                self.assertEqual(0, session["prompt"].count(parent["request"]))

                session = comparison.submit(
                    "manual-comparison",
                    json.dumps(
                        execution_result(
                            result=(
                                "# 단일 Build Brief\n\n"
                                "현재 위치 → 손절 가능한 구조 → 가까운 목표 → 진입 결론 "
                                "순서로 판단하고 거래량과 피보나치는 보조 근거로만 사용한다."
                            )
                        ),
                        ensure_ascii=False,
                    ),
                )
                self.assertEqual("ablation_assessment", session["phase"])
                for candidate_id in ("A", "B", "C", "D"):
                    self.assertIn(f"[후보 {candidate_id}]", session["prompt"])
                self.assertNotIn("single_build_brief", session["prompt"])

                finished = comparison.submit(
                    "manual-comparison",
                    json.dumps(assessment_result(), ensure_ascii=False),
                )

            self.assertEqual("completed", finished["state"])
            self.assertEqual("prompt_ablation", finished["session_kind"])
            self.assertIn("PROMPT 입력 구조 비교", finished["output_markdown"])
            self.assertIn("블라인드 평가", finished["output_markdown"])
            self.assertIn("실제 차트 이미지", finished["output_markdown"])
            self.assertEqual(parent_hash, hashlib.sha256(parent_output.read_bytes()).hexdigest())
            comparison_dir = runs / "manual-comparison" / "prompt_ablation"
            self.assertTrue((comparison_dir / "comparison.json").is_file())
            self.assertTrue((comparison_dir / "results" / "blind_assessment.json").is_file())
            state = MANUAL.read_state(runs / "manual-comparison")
            self.assertEqual(
                list(ABLATION.NEW_VARIANTS),
                state["ablation"]["completed_variants"],
            )

    def test_rejects_non_prompt_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            comparison = ABLATION.ManualPromptAblation(
                bridge,
                MANUAL,
                MANUAL.problem_os,
            )
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                return_value="manual-parent",
            ):
                self.make_parent(runs, bridge, route="DIRECT")
            with self.assertRaisesRegex(
                ABLATION.ManualPromptAblationError,
                "PROMPT 단일 경로",
            ):
                comparison.start("manual-parent")

    def test_invalid_assessment_keeps_current_stage_and_original_results(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory) / "runs"
            bridge = MANUAL.ManualBridge(runs_dir=runs)
            comparison = ABLATION.ManualPromptAblation(
                bridge,
                MANUAL,
                MANUAL.problem_os,
            )
            with mock.patch.object(
                MANUAL.problem_os,
                "make_run_id",
                side_effect=["manual-parent", "manual-comparison"],
            ):
                self.make_parent(runs, bridge)
                comparison.start("manual-parent")
                for result in ("후보 1", "후보 2", "후보 3"):
                    comparison.submit(
                        "manual-comparison",
                        json.dumps(execution_result(result=result), ensure_ascii=False),
                    )
            with self.assertRaises(ABLATION.ManualPromptAblationError):
                comparison.submit(
                    "manual-comparison",
                    json.dumps({"version": 1}, ensure_ascii=False),
                )
            session = bridge.get("manual-comparison")
            self.assertEqual("ablation_assessment", session["phase"])
            self.assertIn("필드가 계약과 일치", session["error"])
            self.assertFalse((runs / "manual-comparison" / "output.md").is_file())


if __name__ == "__main__":
    unittest.main()
