import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_chart_prompt_batch as BATCH  # noqa: E402


class FakeInvoker:
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
        if schema_path == BATCH.ANSWER_SCHEMA_PATH:
            candidate_id = invocation_name.rsplit("-", 1)[-1]
            return {
                "version": 1,
                "answer_markdown": f"후보 {candidate_id}의 차트 분석 결과",
            }
        return {
            "version": 1,
            "ranking": ["A", "B", "C", "D"],
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
                    "finding": f"후보 {candidate_id}는 실행 가능한 결론을 제시했다.",
                }
                for candidate_id in ("A", "B", "C", "D")
            ],
            "preferred_candidate_ids": ["A"],
            "conclusion": "후보 A가 가장 직접적이다.",
        }


class ChartPromptBatchTests(unittest.TestCase):
    def _write_prompt_dir(self, root: Path) -> Path:
        prompt_dir = root / "prompts"
        prompt_dir.mkdir()
        names = {
            "current": "current(1).md",
            "without_raw_request": "without_raw_request(1).md",
            "compact_ledger": "compact_ledger(1).md",
            "single_build_brief": "single_build_brief(1).md",
        }
        for label, name in names.items():
            (prompt_dir / name).write_text(
                f"# {label}\n첨부된 차트를 분석하고 결론을 제시하라.\n",
                encoding="utf-8",
            )
        return prompt_dir

    def _write_images(self, root: Path) -> list[Path]:
        image_dir = root / "images"
        image_dir.mkdir()
        paths = [image_dir / "daily.png", image_dir / "hourly.jpg"]
        paths[0].write_bytes(b"fake-png-image")
        paths[1].write_bytes(b"fake-jpg-image")
        return paths

    def _profile(self):
        return BATCH.RunProfile(model="fake-model", reasoning_effort="medium")

    def test_prompt_dir_discovers_four_historical_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_dir = self._write_prompt_dir(Path(directory))
            prompts = BATCH.parse_prompt_specs([], prompt_dir)
        self.assertEqual(list(BATCH.EXPECTED_PROMPT_LABELS), [item.label for item in prompts])
        self.assertTrue(all(item.text for item in prompts))

    def test_batch_reuses_one_image_set_and_keeps_judge_blind(self):
        fake = FakeInvoker()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = BATCH.parse_prompt_specs([], self._write_prompt_dir(root))
            images = BATCH.parse_images(self._write_images(root), None)
            output = root / "result"
            result = BATCH.run_chart_prompt_comparison(
                prompts=prompts,
                images=images,
                context="보유 중이며 평균 진입가는 제공된 차트에 표시되어 있다.",
                output_dir=output,
                profile=self._profile(),
                invoker=fake,
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            blind = (output / "blind-report.md").read_text(encoding="utf-8")
            revealed = (output / "report.md").read_text(encoding="utf-8")

            self.assertEqual(5, len(fake.calls))
            copied_images = fake.calls[0]["images"]
            self.assertEqual(2, len(copied_images))
            self.assertTrue(all(path.is_file() for path in copied_images))
            self.assertTrue(all(call["images"] == copied_images for call in fake.calls))
            self.assertTrue(all(call["profile"] == self._profile() for call in fake.calls))

            judge_prompt = fake.calls[-1]["prompt"]
            for label in BATCH.EXPECTED_PROMPT_LABELS:
                self.assertNotIn(label, judge_prompt)
                self.assertNotIn(label, blind)
                self.assertIn(label, revealed)
            self.assertIn("[후보 A]", judge_prompt)
            self.assertIn("[후보 D]", judge_prompt)
            self.assertEqual(set(BATCH.EXPECTED_PROMPT_LABELS), set(manifest["candidate_mapping"].values()))
            self.assertEqual(result["report_path"], str(output / "report.md"))

    def test_no_judge_runs_each_prompt_once(self):
        fake = FakeInvoker()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = BATCH.parse_prompt_specs([], self._write_prompt_dir(root))
            images = BATCH.parse_images(self._write_images(root), None)
            output = root / "result"
            result = BATCH.run_chart_prompt_comparison(
                prompts=prompts,
                images=images,
                context="",
                output_dir=output,
                profile=self._profile(),
                judge=False,
                invoker=fake,
            )
        self.assertEqual(4, len(fake.calls))
        self.assertFalse(result["assessment_completed"])
        self.assertTrue(all(call["schema"] == BATCH.ANSWER_SCHEMA_PATH for call in fake.calls))

    def test_assessment_requires_every_candidate_exactly_once(self):
        bad = {
            "version": 1,
            "ranking": ["A", "A", "C", "D"],
            "candidates": [],
            "preferred_candidate_ids": ["A"],
            "conclusion": "잘못된 결과",
        }
        with self.assertRaisesRegex(BATCH.ChartPromptBatchError, "ranking"):
            BATCH.validate_assessment(bad, {"A", "B", "C", "D"})

    def test_image_limits_and_extensions_are_checked_before_model_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "chart.bmp"
            bad.write_bytes(b"not-supported")
            with self.assertRaisesRegex(BATCH.ChartPromptBatchError, "지원하지 않는"):
                BATCH.parse_images([bad], None)

    def test_codex_invoker_passes_every_image_with_image_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = self._write_images(root)
            run_dir = root / "run"
            run_dir.mkdir()
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                if "--help" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout="--image --output-schema --output-last-message",
                    )
                output_index = command.index("--output-last-message") + 1
                Path(command[output_index]).write_text(
                    json.dumps({"version": 1, "answer_markdown": "분석"}),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, stdout="ok")

            with mock.patch.object(BATCH.OS, "find_codex", return_value="codex"), mock.patch.object(
                BATCH.subprocess, "run", side_effect=fake_run
            ):
                invoker = BATCH.CodexImageInvoker(ROOT)
                payload = invoker(
                    "분석하라",
                    run_dir,
                    "test",
                    BATCH.ANSWER_SCHEMA_PATH,
                    images,
                    self._profile(),
                )

        self.assertEqual("분석", payload["answer_markdown"])
        execution_command = commands[-1]
        self.assertEqual(2, execution_command.count("--image"))
        for image in images:
            self.assertIn(str(image), execution_command)
        self.assertIn("read-only", execution_command)


if __name__ == "__main__":
    unittest.main()
