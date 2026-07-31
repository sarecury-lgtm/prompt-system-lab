import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLIED_PATH = ROOT / "scripts" / "problem_solving_prompt_applied_patch_review.py"
APPROVED_PATH = ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


APPLIED = load_module("prompt_applied_patch_review_test", APPLIED_PATH)
APPROVED = load_module("approved_comment_asset_test", APPROVED_PATH)


def comment_case():
    return {
        "id": "comment-natural-reply",
        "title": "댓글",
        "request": "상대 댓글을 분석해 자연스러운 답글을 만드는 재사용 프롬프트를 만들어줘.",
        "used_patterns": ["Role + Task Frame"],
        "ledger": {
            "current_goal_hypothesis": "댓글 답글",
            "fixed_constraints": ["상대가 하지 않은 말을 만들지 않는다."],
            "completion_condition": "답글을 만든다.",
            "important_uncertainties": [],
        },
        "brief": {
            "version": 1,
            "goal": "상대 댓글을 정확히 읽고 자연스러운 답글을 만든다.",
            "core_procedure": ["상대 주장과 사용자 의도를 구분한다."],
            "supporting_inputs": ["상대 댓글", "사용자 초안"],
            "fixed_constraints": ["상대가 하지 않은 말을 만들지 않는다."],
            "output_contract": ["복사할 답글을 출력한다."],
            "defaults_and_exceptions": ["맥락이 결론을 바꿀 때만 질문한다."],
            "exclusions": ["공문체로 바꾸지 않는다."],
            "upstream_context": [],
        },
        "application": {
            "input_markdown": "상대 댓글과 사용자 초안",
            "criteria": ["자연스러운 답글"],
            "critical_failures": ["없는 주장을 만든다."],
        },
    }


class PromptAppliedPatchReviewTests(unittest.TestCase):
    def test_baseline_performs_task_instead_of_repeating_meta_request(self):
        rendered = APPLIED.applied_baseline_prompt(comment_case())
        self.assertIn("상대 댓글을 정확히 읽고 자연스러운 답글", rendered)
        self.assertIn("상대 주장과 사용자 의도를 구분", rendered)
        self.assertIn("복사할 답글을 출력", rendered)
        self.assertNotIn("재사용 프롬프트를 만들어줘", rendered)
        self.assertNotIn("[사용자 요청]", rendered)

    def test_prepare_writes_direct_applied_baseline_without_ai_runner(self):
        payload = {"version": 1, "cases": [comment_case()]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.json"
            cases_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            run_dir = APPLIED.prepare_review(
                case_ids=["comment-natural-reply"],
                output_dir=root / "run",
                cases_path=cases_path,
            )
            baseline = (
                run_dir
                / "cases"
                / "comment-natural-reply"
                / "prompts"
                / "baseline.md"
            ).read_text(encoding="utf-8")
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertIn("자연스러운 답글", baseline)
        self.assertNotIn("재사용 프롬프트를 만들어줘", baseline)
        self.assertFalse(manifest["ai_runner_invoked"])
        self.assertEqual("none", manifest["engine"])

    def test_repository_registry_selects_approved_comment_prompt(self):
        selected = APPROVED.select_approved_prompt(
            "상대 댓글을 분석해서 내 말투로 자연스러운 답글을 만드는 프롬프트"
        )
        unrelated = APPROVED.select_approved_prompt(
            "온라인 상품의 옵션과 후기를 조사하는 프롬프트"
        )

        self.assertEqual("comment-natural-reply", selected["id"])
        self.assertIn("원문에 없는 근거나 논리를 새로 보충하지 않는다", selected["prompt"])
        self.assertIsNone(unrelated)


if __name__ == "__main__":
    unittest.main()
