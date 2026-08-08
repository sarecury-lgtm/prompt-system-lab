import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_candidate_working_set as WORKING
import problem_solving_next_loop_replacement_runtime as RUNTIME


def sample_working_set() -> dict:
    return WORKING.validate_working_set(
        {
            "version": 1,
            "run_id": "replacement-test",
            "request": "2주 안에 오를 미국 주식 후보를 찾아줘",
            "goal": "미국 주식 후보 비교",
            "constraints": {},
            "source_plan": {
                "strategy": "REUSE_EXISTING",
                "primary_source_family": "REUSE_INDEX",
                "secondary_source_family": "BROAD_WEB",
                "next_action": "collect",
                "probes": [],
            },
            "candidates": [
                {
                    "id": "candidate-001",
                    "name": "Reddit AIPortfolios 주간 변동 예측 목록",
                    "source_family": "COMMUNITY",
                    "source_url": "https://example.com/reddit-list",
                    "why_actionable": "종목 단서를 찾을 수 있는 정보원",
                    "attributes": {},
                    "evidence": [
                        {
                            "source": "https://example.com/reddit-list",
                            "finding": "종목 단서",
                            "kind": "source-scout-lead",
                        }
                    ],
                    "strengths": [],
                    "risks": ["정찰 단계 단서"],
                    "status": "needs_check",
                    "verification_status": "unverified",
                    "exclusion_reason": None,
                },
                {
                    "id": "candidate-002",
                    "name": "Nasdaq 2026 Trading Calendar",
                    "source_family": "PRIMARY",
                    "source_url": "https://example.com/calendar",
                    "why_actionable": "실적 일정을 확인하는 정보원",
                    "attributes": {},
                    "evidence": [
                        {
                            "source": "https://example.com/calendar",
                            "finding": "실적 일정",
                            "kind": "source-scout-lead",
                        }
                    ],
                    "strengths": [],
                    "risks": ["정찰 단계 단서"],
                    "status": "needs_check",
                    "verification_status": "unverified",
                    "exclusion_reason": None,
                },
            ],
            "user_corrections": [],
            "unresolved_requirements": [],
            "state": "awaiting_correction",
            "next_action": None,
            "revision": 0,
        }
    )


class FakeEngine:
    def trace(self):
        return []


class NextLoopReplacementRuntimeTests(unittest.TestCase):
    def test_explicit_remove_and_regenerate_is_detected(self):
        text = (
            "기사·Reddit·캘린더는 후보에서 제거하고, 위 자료에서 실제 미국 주식 "
            "후보 5~8개를 새로 뽑아줘."
        )
        self.assertTrue(RUNTIME.replacement_requested(text, sample_working_set()))

    def test_plain_exclusion_is_not_promoted_to_replacement(self):
        self.assertFalse(
            RUNTIME.replacement_requested(
                "candidate-001 제외",
                sample_working_set(),
            )
        )

    def test_replacement_correction_excludes_sources_and_keeps_research_action(self):
        working = sample_working_set()
        state = {"candidate_working_set": working}
        correction = RUNTIME.build_replacement_correction(
            state,
            "기사와 캘린더를 후보에서 제거하고 실제 미국 주식 후보를 새로 뽑아줘",
        )
        updated = RUNTIME._apply_replacement_correction(
            WORKING.apply_correction,
            working,
            correction,
        )

        self.assertEqual("PARTIAL_RESEARCH", updated["next_action"])
        self.assertEqual("researching", updated["state"])
        self.assertEqual(
            {"excluded"},
            {candidate["status"] for candidate in updated["candidates"]},
        )

    def test_empty_awaiting_state_is_downgraded_to_partial(self):
        working = sample_working_set()
        for candidate in working["candidates"]:
            candidate["status"] = "excluded"
            candidate["exclusion_reason"] = "교체"
        state = {
            "version": 1,
            "run_id": "replacement-test",
            "state": "awaiting_correction",
            "request": working["request"],
            "context": "",
            "framing": {},
            "source_scout": {},
            "candidate_working_set": WORKING.validate_working_set(working),
            "pending_questions": [],
            "dynamic_state": None,
            "latest_correction": None,
            "engine_trace": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            _resolved, guarded = RUNTIME._guard_empty_awaiting(
                run_dir,
                copy.deepcopy(state),
                engine=FakeEngine(),
            )
            self.assertEqual("partial", guarded["state"])
            self.assertEqual("partial", guarded["candidate_working_set"]["state"])
            self.assertIn("중단 이유", (run_dir / "result.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
