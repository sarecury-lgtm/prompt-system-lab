import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_prompt_patch_review.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_prompt_patch_review",
    MODULE_PATH,
)
REVIEW = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)


def fixture_payload():
    cases = []
    for case_id, title in (
        ("chart-trade-plan", "차트"),
        ("comment-natural-reply", "댓글"),
        ("product-evidence-choice", "상품"),
    ):
        cases.append(
            {
                "id": case_id,
                "title": title,
                "request": f"{title} 재사용 프롬프트를 만들어줘.",
                "used_patterns": ["Role + Task Frame"],
                "ledger": {
                    "current_goal_hypothesis": title,
                    "fixed_constraints": ["범위를 바꾸지 않는다."],
                    "completion_condition": "재사용 프롬프트 완성",
                    "important_uncertainties": [],
                },
                "brief": {
                    "version": 1,
                    "goal": title,
                    "core_procedure": ["핵심 절차를 수행한다."],
                    "supporting_inputs": [],
                    "fixed_constraints": ["범위를 바꾸지 않는다."],
                    "output_contract": ["재사용 프롬프트 완성"],
                    "defaults_and_exceptions": [],
                    "exclusions": [],
                    "upstream_context": [],
                },
                "application": {
                    "input_markdown": f"{title} 통제 입력",
                    "criteria": ["요구를 보존한다."],
                    "critical_failures": ["없는 사실을 만든다."],
                },
            }
        )
    return {"version": 1, "cases": cases}


def complete_case(run_dir, case_id, preferred_variant=None, critical_variant=None):
    case_dir = run_dir / "cases" / case_id
    mapping = json.loads(
        (case_dir / "mapping.private.json").read_text(encoding="utf-8")
    )["candidate_to_variant"]
    for candidate_id in ("A", "B"):
        (case_dir / "answers" / f"{candidate_id}.md").write_text(
            f"{candidate_id} 실제 답변\n",
            encoding="utf-8",
        )
    candidates = []
    for candidate_id in ("A", "B"):
        variant = mapping[candidate_id]
        candidates.append(
            {
                "candidate_id": candidate_id,
                "requirement_preservation": 5,
                "task_correctness": 5,
                "actionability": 5,
                "calibration": 5,
                "format_cost": 1,
                "critical_failures": (
                    ["치명적 실패"] if variant == critical_variant else []
                ),
                "finding": f"{variant} 평가",
            }
        )
    preferred_ids = [
        candidate_id
        for candidate_id, variant in mapping.items()
        if variant == preferred_variant
    ]
    review = {
        "version": 1,
        "case_id": case_id,
        "candidates": candidates,
        "preferred_candidate_ids": preferred_ids,
        "conclusion": "블라인드 판정 완료",
    }
    (case_dir / "review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class PromptPatchReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases_path = self.root / "cases.json"
        self.cases_path.write_text(
            json.dumps(fixture_payload(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_uses_no_ai_runner_and_retains_missing_patches(self):
        run_dir = REVIEW.prepare_review(
            output_dir=self.root / "run",
            cases_path=self.cases_path,
        )
        manifest = json.loads(
            (run_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertFalse(manifest["ai_runner_invoked"])
        self.assertEqual("none", manifest["engine"])
        self.assertEqual(3, len(manifest["cases"]))
        self.assertTrue(
            all(item["proposal_status"] == "baseline_retained" for item in manifest["cases"])
        )
        self.assertTrue((run_dir / "review-pack.md").is_file())

    def test_identical_prompt_is_recorded_as_baseline_retained(self):
        run_dir = REVIEW.prepare_review(
            case_ids=["chart-trade-plan"],
            output_dir=self.root / "run-identical",
            cases_path=self.cases_path,
        )
        complete_case(run_dir, "chart-trade-plan", preferred_variant="patched")
        report = REVIEW.finalize_review(run_dir)
        finalized = json.loads(
            (run_dir / "finalized.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            "baseline_retained",
            finalized["results"][0]["decision"],
        )
        self.assertIn("baseline_retained", report.read_text(encoding="utf-8"))

    def test_changed_patch_is_promoted_only_after_blind_preference(self):
        patch_dir = self.root / "patches"
        patch_dir.mkdir()
        (patch_dir / "comment-natural-reply.md").write_text(
            "# 패치 프롬프트\n\n상대 주장과 사용자 의도를 구분한다.\n",
            encoding="utf-8",
        )
        run_dir = REVIEW.prepare_review(
            case_ids=["comment-natural-reply"],
            patch_dir=patch_dir,
            output_dir=self.root / "run-promote",
            cases_path=self.cases_path,
        )
        complete_case(run_dir, "comment-natural-reply", preferred_variant="patched")
        REVIEW.finalize_review(run_dir)
        finalized = json.loads(
            (run_dir / "finalized.json").read_text(encoding="utf-8")
        )
        self.assertEqual("promote_patch", finalized["results"][0]["decision"])

    def test_patch_critical_failure_forces_baseline(self):
        patch_dir = self.root / "patches-fail"
        patch_dir.mkdir()
        (patch_dir / "product-evidence-choice.md").write_text(
            "# 패치 프롬프트\n\n상품을 비교한다.\n",
            encoding="utf-8",
        )
        run_dir = REVIEW.prepare_review(
            case_ids=["product-evidence-choice"],
            patch_dir=patch_dir,
            output_dir=self.root / "run-fail",
            cases_path=self.cases_path,
        )
        complete_case(
            run_dir,
            "product-evidence-choice",
            preferred_variant="patched",
            critical_variant="patched",
        )
        REVIEW.finalize_review(run_dir)
        finalized = json.loads(
            (run_dir / "finalized.json").read_text(encoding="utf-8")
        )
        self.assertEqual("keep_baseline", finalized["results"][0]["decision"])

    def test_placeholder_answers_block_finalize(self):
        run_dir = REVIEW.prepare_review(
            case_ids=["chart-trade-plan"],
            output_dir=self.root / "run-empty",
            cases_path=self.cases_path,
        )
        with self.assertRaises(REVIEW.PromptPatchReviewError):
            REVIEW.finalize_review(run_dir)


if __name__ == "__main__":
    unittest.main()
