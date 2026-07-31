import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_approved_prompt_baseline.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_approved_prompt_baseline",
    MODULE_PATH,
)
APPROVED = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = APPROVED
SPEC.loader.exec_module(APPROVED)


def write_registry(root: Path, prompt_text: str, *, sha_override=None):
    approved_dir = root / "approved-prompts"
    approved_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = approved_dir / "chart.md"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    sha = APPROVED._sha256_text(prompt_text)
    payload = {
        "version": 1,
        "entries": [
            {
                "id": "chart",
                "status": "approved",
                "prompt_path": "approved-prompts/chart.md",
                "prompt_sha256": sha_override or sha,
                "match": {
                    "all_terms": ["차트"],
                    "any_terms": ["매매", "손절"],
                    "none_terms": ["데이터 시각화"],
                },
                "evidence": {
                    "decision": "approved_baseline",
                    "source_kind": "blind_applied_comparison",
                },
            }
        ],
    }
    registry_path = approved_dir / "registry.json"
    registry_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return registry_path


class ApprovedPromptBaselineTests(unittest.TestCase):
    def test_selects_one_matching_approved_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = write_registry(root, "# 승인 차트 프롬프트\n")
            selected = APPROVED.select_approved_prompt(
                "다중 시간대 차트의 진입과 손절을 판단하는 매매 프롬프트",
                registry_path=registry,
                repository_root=root,
            )
            unrelated = APPROVED.select_approved_prompt(
                "상품을 조사하는 프롬프트",
                registry_path=registry,
                repository_root=root,
            )

        self.assertEqual("chart", selected["id"])
        self.assertIn("승인 차트 프롬프트", selected["prompt"])
        self.assertIsNone(unrelated)

    def test_sha_mismatch_blocks_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = write_registry(
                root,
                "# 승인 차트 프롬프트\n",
                sha_override="0" * 64,
            )
            with self.assertRaises(APPROVED.ApprovedPromptBaselineError):
                APPROVED.load_registry(
                    registry,
                    repository_root=root,
                )

    def test_rewrites_only_compiler_baseline_json(self):
        approved = {
            "id": "chart",
            "prompt_path": "approved-prompts/chart.md",
            "prompt_sha256": "a" * 64,
            "prompt": "# 승인 프롬프트",
            "evidence": {"decision": "approved_baseline"},
        }
        original = (
            "앞부분\n"
            "[기존 Prompt Compiler baseline]\n"
            + json.dumps(
                {"version": "0.1", "final_prompt": "# 짧은 baseline"},
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n[다음 블록]\n그대로"
        )
        rewritten, changed = APPROVED.rewrite_compiler_baseline(
            original,
            approved,
        )
        baseline_start = rewritten.index("{", rewritten.index(APPROVED.BASELINE_MARKER))
        baseline, _ = json.JSONDecoder().raw_decode(rewritten[baseline_start:])

        self.assertTrue(changed)
        self.assertEqual("# 승인 프롬프트", baseline["final_prompt"])
        self.assertEqual("chart", baseline["approved_baseline"]["id"])
        self.assertIn("[다음 블록]\n그대로", rewritten)

    def test_wrapper_records_injected_asset(self):
        class BaseEngine:
            def __init__(self, delegate, *, request, os_module):
                self.calls = []
                self.request = request

            def execute(self, prompt, run_dir, invocation):
                self.calls.append(prompt)
                return {"execution": {"result_markdown": "ok"}}

            def record(self):
                return {
                    "version": 2,
                    "status": "applied",
                    "entries": [{}],
                }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = write_registry(root, "# 승인 차트 프롬프트\n")
            Wrapped = APPROVED.approved_engine_class(
                BaseEngine,
                registry_path=registry,
                repository_root=root,
            )
            engine = Wrapped(
                object(),
                request="차트 매매 손절 프롬프트",
                os_module=object(),
            )

            invocation = types.SimpleNamespace(phase="executor", route="PROMPT")
            prompt = (
                "[기존 Prompt Compiler baseline]\n"
                + json.dumps({"final_prompt": "old"}, ensure_ascii=False)
            )
            engine.execute(prompt, root, invocation)
            record = engine.record()

        self.assertIn("승인 차트 프롬프트", engine.calls[0])
        self.assertEqual("chart", record["approved_baseline"]["id"])
        self.assertEqual(
            "approved_registry",
            record["entries"][0]["baseline_source"],
        )


if __name__ == "__main__":
    unittest.main()
