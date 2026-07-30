import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUALITY_PATH = ROOT / "scripts" / "problem_solving_os_quality_runtime.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_os_quality_runtime", QUALITY_PATH)
QUALITY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = QUALITY
SPEC.loader.exec_module(QUALITY)

from tests.test_problem_solving_os_contract_runtime import (  # noqa: E402
    FakeEngine,
    assessment_response,
    compiled_contract,
    execution_result,
    route_result,
)


class QualityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy = QUALITY.OS.load_model_policy()

    def test_quality_runtime_attaches_reviewable_bundle_to_run(self):
        detailed_contract = compiled_contract("RESEARCH")
        detailed_contract["user_review"] = {
            "needed": True,
            "evidence_types": ["web"],
        }
        engine = FakeEngine(
            [
                route_result("RESEARCH"),
                detailed_contract,
                execution_result("RESEARCH", url=True),
                assessment_response({}),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = QUALITY.run_request(
                "현재 구매 가능한 개별 대상을 비교해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="quality-evidence-bundle",
            )
            bundle_path = run_dir / "evidence_bundle.json"
            review_path = run_dir / "evidence_review.json"
            markdown_path = run_dir / "evidence_review.md"
            route_record = json.loads(
                (run_dir / "route.json").read_text(encoding="utf-8")
            )
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

            self.assertTrue(bundle_path.is_file())
            self.assertTrue(review_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertEqual("pending", bundle["review"]["status"])
            self.assertEqual(
                hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                payload["evidence_bundle"]["sha256"],
            )
            self.assertEqual(
                payload["evidence_bundle"]["sha256"],
                route_record["evidence_bundle"]["sha256"],
            )
            self.assertEqual(
                payload["evidence_bundle"],
                payload["run"]["evidence_bundle"],
            )

    def test_simple_direct_does_not_create_empty_bundle(self):
        engine = FakeEngine(
            [
                route_result("DIRECT"),
                execution_result("DIRECT"),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, payload = QUALITY.run_request(
                "캐시가 무엇인지 설명해 줘.",
                output_root=Path(temp_dir),
                engine=engine,
                model_policy=self.policy,
                run_id="quality-simple-direct",
            )
            self.assertFalse((run_dir / "evidence_bundle.json").exists())
            self.assertNotIn("evidence_bundle", payload)


if __name__ == "__main__":
    unittest.main()
