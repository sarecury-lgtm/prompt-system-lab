import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "prompt_runtime.py"
SPEC = importlib.util.spec_from_file_location("prompt_runtime", MODULE_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNTIME)


class PromptRuntimeTests(unittest.TestCase):
    def test_simple_rewrite_returns_baseline_prompt(self):
        result = RUNTIME.create_prompt("이 문장을 더 친절하게 다시 써 주세요: 회의는 취소됐습니다.")
        self.assertEqual("baseline", result["selected_mode"])
        self.assertIn("회의는 취소됐습니다", result["final_prompt"])
        self.assertFalse(result["used_active_sources"])

    def test_context_file_is_included(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = Path(temp_dir) / "context.txt"
            context.write_text("대상 독자는 신규 입사자입니다.", encoding="utf-8")
            result = RUNTIME.create_prompt("온보딩 안내문을 표로 작성해 주세요.", [context])
        self.assertIn("대상 독자는 신규 입사자", result["final_prompt"])
        self.assertEqual("pattern-only", result["selected_mode"])

    def test_context_does_not_add_unrelated_patterns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context = Path(temp_dir) / "context.txt"
            context.write_text("JSON 탈옥 조사 평가 루브릭 표 출처", encoding="utf-8")
            result = RUNTIME.create_prompt(
                "이 저장소 파일을 확인하고 가장 작은 수정을 검증해 주세요.",
                [context],
                tools_allowed=True,
            )
        self.assertIn("Coding-Agent Workflow", result["used_patterns"])
        self.assertNotIn("Defensive Jailbreak Analysis", result["used_patterns"])
        self.assertNotIn("Grounded Research", result["used_patterns"])
        self.assertNotIn("Structured Output / Extraction", result["used_patterns"])

    def test_active_failure_falls_back_to_pattern_only(self):
        request = (
            "여러 조건을 반복 비교하는 재현 가능한 평가 실행기와 파이프라인을 설계하세요. "
            "평가 사례와 사람 판정, 자동 실행 결과를 포함하세요."
        )
        with mock.patch.dict(os.environ, {"PROMPT_RUNTIME_TEST_FAIL_ACTIVE": "1"}):
            result = RUNTIME.create_prompt(request)
        self.assertEqual("pattern-only", result["selected_mode"])
        self.assertTrue(result["fallback"])
        self.assertIn("active 생성·평가 실패", result["fallback_reason"])

    def test_pattern_failure_falls_back_to_baseline(self):
        with mock.patch.dict(os.environ, {"PROMPT_RUNTIME_TEST_FAIL_PATTERN": "1"}):
            result = RUNTIME.create_prompt("세 제품을 가격과 위험 기준으로 표로 비교해 주세요.")
        self.assertEqual("baseline", result["selected_mode"])
        self.assertTrue(result["fallback"])
        self.assertIn("pattern-only 생성 실패", result["fallback_reason"])

    def test_active_policy_limit_and_full_search_setting_are_preserved(self):
        router = RUNTIME.load_router()
        registry = router.load_active_source_policies()
        self.assertFalse(registry["full_corpus_auto_search"])
        self.assertEqual(1, registry["max_auto_sources_per_request"])
        self.assertEqual(7, len(registry["sources"]))

    def test_missing_context_is_recorded_without_losing_prompt(self):
        result = RUNTIME.create_prompt("한 문단으로 요약해 주세요.", [Path("missing-v0-1.txt")])
        self.assertTrue(result["final_prompt"])
        self.assertEqual("context-read", result["errors"][0]["stage"])

    def test_record_save_failure_does_not_change_generated_prompt(self):
        result = RUNTIME.create_prompt("한 문단으로 요약해 주세요.")
        with mock.patch.object(RUNTIME, "output_paths", return_value=(Path("ok.txt"), Path("bad.json"))), mock.patch.object(
            Path, "write_text", side_effect=[1, OSError("record blocked")]
        ):
            prompt_path, record_path, errors = RUNTIME.save_results(result, None)
        self.assertEqual(Path("ok.txt"), prompt_path)
        self.assertIsNone(record_path)
        self.assertTrue(errors)
        self.assertTrue(result["final_prompt"])


if __name__ == "__main__":
    unittest.main()
