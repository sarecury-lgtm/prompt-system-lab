import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_chart_prompt_batch as BATCH  # noqa: E402
import problem_solving_chart_prompt_resume_judge as RESUME  # noqa: E402


class FakeAssessmentInvoker:
    def __init__(self):
        self.calls = []

    def __call__(self, prompt, run_dir, invocation_name, schema_path, images, profile):
        self.calls.append(
            {
                "prompt": prompt,
                "run_dir": run_dir,
                "name": invocation_name,
                "schema": schema_path,
                "images": list(images),
                "profile": profile,
            }
        )
        candidate_ids = ["A", "B", "C", "D"]
        return {
            "version": 1,
            "ranking": candidate_ids,
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "observation_fidelity": 5,
                    "multi_timeframe_synthesis": 4,
                    "decision_clarity": 4,
                    "plan_quality": 4,
                    "calibration": 4,
                    "format_cost": 2,
                    "critical_failures": [],
                    "finding": f"후보 {candidate_id} 판정",
                }
                for candidate_id in candidate_ids
            ],
            "preferred_candidate_ids": ["A"],
            "conclusion": "후보 A가 가장 낫다.",
        }


class ChartPromptResumeJudgeTests(unittest.TestCase):
    def _prepare_failed_run(self, root: Path) -> tuple[Path, list[Path]]:
        prompt_source = root / "prompt-source"
        image_source = root / "image-source"
        prompt_source.mkdir()
        image_source.mkdir()
        prompts = []
        for label in BATCH.EXPECTED_PROMPT_LABELS:
            path = prompt_source / f"{label}.md"
            path.write_text(f"# {label}\n차트를 분석하라.\n", encoding="utf-8")
            text = path.read_text(encoding="utf-8").strip()
            prompts.append(
                BATCH.PromptInput(
                    label=label,
                    source_path=path,
                    text=text,
                    sha256=BATCH._sha256_text(text),
                )
            )
        image_paths = [image_source / "daily.png", image_source / "hourly.jpg"]
        image_paths[0].write_bytes(b"fake-daily")
        image_paths[1].write_bytes(b"fake-hourly")
        images = BATCH.parse_images(image_paths, None)

        run_dir = root / "run"
        copied_prompts, copied_images, _ = BATCH._copy_inputs(
            run_dir,
            prompts,
            images,
            "",
        )
        digest = BATCH._bundle_digest(prompts, images, "")
        mapping = BATCH.candidate_mapping([item.label for item in prompts], digest)
        candidate_root = run_dir / "candidates"
        candidate_root.mkdir()
        for candidate_id in mapping:
            payload = {
                "version": 1,
                "answer_markdown": f"후보 {candidate_id}의 기존 분석 결과",
            }
            (candidate_root / f"{candidate_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        self.assertEqual(set(copied_prompts), set(BATCH.EXPECTED_PROMPT_LABELS))
        return run_dir, copied_images

    def test_resume_runs_only_one_assessment_and_reuses_candidates(self):
        fake = FakeAssessmentInvoker()
        with tempfile.TemporaryDirectory() as directory:
            run_dir, copied_images = self._prepare_failed_run(Path(directory))
            result = RESUME.resume_blind_assessment(
                run_dir,
                profile=BATCH.RunProfile(model="fake-model", reasoning_effort="medium"),
                invoker=fake,
            )
            report = Path(result["report_path"]).read_text(encoding="utf-8")

            self.assertEqual(1, len(fake.calls))
            self.assertEqual("chart-analysis-blind-assessment", fake.calls[0]["name"])
            self.assertEqual(copied_images, fake.calls[0]["images"])
            self.assertTrue((run_dir / "assessment.json").is_file())
            self.assertTrue((run_dir / "blind-report.md").is_file())
            self.assertTrue((run_dir / "resume-assessment-manifest.json").is_file())
            for label in BATCH.EXPECTED_PROMPT_LABELS:
                self.assertIn(label, report)

    def test_missing_candidate_blocks_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir, _ = self._prepare_failed_run(Path(directory))
            (run_dir / "candidates" / "A.json").unlink()
            with self.assertRaisesRegex(BATCH.ChartPromptBatchError, "기존 후보 결과"):
                RESUME.load_existing_run(run_dir)


if __name__ == "__main__":
    unittest.main()
