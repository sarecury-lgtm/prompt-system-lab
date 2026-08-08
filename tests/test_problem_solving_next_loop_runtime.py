import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_next_loop_runtime.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_next_loop_runtime", MODULE_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)


def candidate(*, verification="unverified"):
    return {
        "id": "candidate-001",
        "name": "후보 A",
        "source_family": "MARKETPLACE",
        "source_url": "https://example.test/a",
        "why_actionable": "현재 후보",
        "attributes": {},
        "evidence": [],
        "strengths": [],
        "risks": [],
        "status": "kept",
        "verification_status": verification,
        "exclusion_reason": None,
    }


def state(*, verification="unverified"):
    return {
        "version": 1,
        "run_id": "next-test",
        "state": "completed",
        "request": "후보를 찾아줘",
        "context": "",
        "framing": {},
        "source_scout": {},
        "candidate_working_set": {
            "version": 1,
            "run_id": "next-test",
            "request": "후보를 찾아줘",
            "goal": "후보를 압축한다",
            "constraints": {},
            "source_plan": {
                "strategy": "MARKET_SCAN",
                "primary_source_family": "MARKETPLACE",
                "secondary_source_family": None,
                "next_action": "후보를 검증한다.",
                "probes": [
                    {
                        "family": "MARKETPLACE",
                        "score": 9,
                        "signal_summary": "현재 후보 확인",
                        "verification_need": "current_state",
                    }
                ],
            },
            "candidates": [candidate(verification=verification)],
            "user_corrections": [],
            "unresolved_requirements": [],
            "state": "completed",
            "next_action": None,
            "revision": 1,
        },
        "pending_questions": [],
        "dynamic_state": {"state": "completed"},
        "latest_correction": {"planned_action": "VERIFY_COMPLETION"},
        "engine_trace": [],
    }


class FakeEngine:
    def trace(self):
        return []


class NextLoopRuntimeTests(unittest.TestCase):
    def test_unverified_candidate_returns_to_correction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "result.md").write_text("결과", encoding="utf-8")
            _run_dir, updated = RUNTIME._enforce_verified_completion(
                run_dir,
                state(verification="unverified"),
                engine=FakeEngine(),
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("awaiting_correction", updated["state"])
        self.assertIn("검증된 유지 후보", result)

    def test_verified_candidate_can_remain_completed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "result.md").write_text("최종 결과", encoding="utf-8")
            _run_dir, updated = RUNTIME._enforce_verified_completion(
                run_dir,
                state(verification="verified"),
                engine=FakeEngine(),
            )

        self.assertEqual("completed", updated["state"])


if __name__ == "__main__":
    unittest.main()
