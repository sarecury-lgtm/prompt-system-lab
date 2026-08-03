import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_next_loop_materialized_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_next_loop_materialized_runtime",
    MODULE_PATH,
)
RUNTIME = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)


class FakeEngine:
    def trace(self):
        return []


def source_candidate():
    return {
        "id": "candidate-001",
        "name": "주간 종목 기사",
        "source_family": "BROAD_WEB",
        "source_url": "https://example.test/article",
        "why_actionable": "MPWR와 STX를 언급한다.",
        "attributes": {},
        "evidence": [
            {
                "source": "https://example.test/article",
                "finding": "MPWR와 STX를 언급한다.",
                "kind": "source-scout-lead",
            }
        ],
        "strengths": [],
        "risks": [RUNTIME.CANDIDATE_UPDATE.SCOUT_RISK],
        "status": "needs_check",
        "verification_status": "unverified",
        "exclusion_reason": None,
    }


def state():
    return {
        "version": 1,
        "run_id": "next-materialize",
        "state": "awaiting_correction",
        "request": "2주 안에 기대값 높은 미국 주식을 찾아줘",
        "context": "",
        "framing": {},
        "source_scout": {"source_scout": {"probes": []}, "decision": {}},
        "candidate_working_set": {
            "version": 1,
            "run_id": "next-materialize",
            "request": "2주 안에 기대값 높은 미국 주식을 찾아줘",
            "goal": "실제 투자 후보를 압축한다",
            "constraints": {},
            "source_plan": {
                "strategy": "REUSE_EXISTING",
                "primary_source_family": "BROAD_WEB",
                "secondary_source_family": None,
                "next_action": "후보를 찾는다",
                "probes": [],
            },
            "candidates": [source_candidate()],
            "user_corrections": [],
            "unresolved_requirements": [],
            "state": "awaiting_correction",
            "next_action": None,
            "revision": 0,
        },
        "pending_questions": [],
        "dynamic_state": None,
        "latest_correction": None,
        "engine_trace": [],
    }


def update():
    return {
        "updates": [
            {
                "candidate_id": "",
                "name": "Monolithic Power Systems (MPWR)",
                "source_family": "BROAD_WEB",
                "source_url": "https://example.test/article",
                "why_actionable": "기사에서 단기 변동 후보로 직접 언급됨",
                "attributes": [
                    {
                        "key": "ticker",
                        "value": "MPWR",
                        "source": "https://example.test/article",
                    }
                ],
                "evidence": [
                    {
                        "source": "https://example.test/article",
                        "finding": "MPWR를 단기 변동 후보로 제시",
                        "kind": "candidate-mention",
                    }
                ],
                "strengths": ["실적 촉매 후보"],
                "risks": ["추가 검증 필요"],
                "status": "needs_check",
                "verification_status": "unverified",
            }
        ],
        "resolved_requirements": [],
        "unresolved_requirements": ["실제 기대수익과 하방 위험 검증"],
        "completion_recommendation": "awaiting_correction",
        "reason": "정보원에서 실제 종목 후보를 분리함",
    }


class MaterializedRuntimeTests(unittest.TestCase):
    def test_source_leads_require_materialization(self):
        self.assertTrue(RUNTIME.needs_decision_materialization(state()))

    def test_materialization_replaces_source_pages_with_actual_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            _run_dir, updated = RUNTIME.apply_materialized_update(
                run_dir,
                state(),
                update(),
                engine=FakeEngine(),
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        candidates = updated["candidate_working_set"]["candidates"]
        self.assertEqual(1, len(candidates))
        self.assertEqual("Monolithic Power Systems (MPWR)", candidates[0]["name"])
        self.assertNotEqual("주간 종목 기사", candidates[0]["name"])
        self.assertEqual("MPWR", candidates[0]["attributes"]["ticker"])
        self.assertEqual("awaiting_correction", updated["state"])
        self.assertIn("Monolithic Power Systems", result)
        self.assertNotIn("주간 종목 기사", result)
        self.assertEqual(
            "INITIAL_MATERIALIZATION",
            updated["candidate_update_history"][-1]["action"],
        )


if __name__ == "__main__":
    unittest.main()
