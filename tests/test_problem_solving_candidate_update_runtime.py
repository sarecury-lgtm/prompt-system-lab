import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_candidate_update_runtime.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_candidate_update_runtime", MODULE_PATH)
UPDATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = UPDATE
SPEC.loader.exec_module(UPDATE)


def candidate(identifier, name, url, *, status="needs_check", verification="unverified"):
    return {
        "id": identifier,
        "name": name,
        "source_family": "MARKETPLACE",
        "source_url": url,
        "why_actionable": "정찰 후보",
        "attributes": {},
        "evidence": [],
        "strengths": [],
        "risks": [UPDATE.SCOUT_RISK],
        "status": status,
        "verification_status": verification,
        "exclusion_reason": "사용자 제외" if status == "excluded" else None,
    }


def working():
    return {
        "version": 1,
        "run_id": "next-test",
        "request": "후보를 찾아줘",
        "goal": "실제로 고를 후보를 압축한다",
        "constraints": {},
        "source_plan": {"strategy": "MARKET_SCAN"},
        "candidates": [
            candidate("candidate-001", "후보 A", "https://example.test/a/", status="excluded"),
            candidate("candidate-002", "후보 B", "https://example.test/b"),
        ],
        "user_corrections": [],
        "unresolved_requirements": ["가격 확인", "판매 상태 확인"],
        "state": "completed",
        "next_action": None,
        "revision": 1,
    }


def update_payload(updates, *, resolved=None, unresolved=None, recommendation="awaiting_correction"):
    return {
        "updates": updates,
        "resolved_requirements": resolved or [],
        "unresolved_requirements": unresolved or [],
        "completion_recommendation": recommendation,
        "reason": "실제 조사 결과를 후보에 반영했다.",
    }


def update_item(
    *,
    candidate_id="",
    name="후보 C",
    url="https://example.test/c",
    status="needs_check",
    verification="unverified",
    attributes=None,
):
    return {
        "candidate_id": candidate_id,
        "name": name,
        "source_family": "MARKETPLACE",
        "source_url": url,
        "why_actionable": "조사에서 직접 확인된 후보",
        "attributes": attributes or [],
        "evidence": [
            {
                "source": url,
                "finding": "현재 후보로 확인",
                "kind": "web",
            }
        ],
        "strengths": [],
        "risks": [],
        "status": status,
        "verification_status": verification,
    }


class FakeEngine:
    def trace(self):
        return [{"name": "candidate-update", "phase": "next-candidate-update"}]


class CandidateUpdateRuntimeTests(unittest.TestCase):
    def test_duplicate_url_updates_existing_candidate_and_resolves_requirement(self):
        payload = update_payload(
            [
                update_item(
                    name="후보 A 최신",
                    url="https://EXAMPLE.test/a",
                    status="kept",
                    verification="verified",
                    attributes=[
                        {
                            "key": "price_per_100g",
                            "value": "1000",
                            "source": "https://example.test/a",
                        }
                    ],
                )
            ],
            resolved=["가격 확인"],
        )
        merged, stats = UPDATE.merge_candidate_update(working(), payload)

        self.assertEqual(0, stats["added"])
        self.assertEqual(1, stats["updated"])
        self.assertEqual("excluded", merged["candidates"][0]["status"])
        self.assertEqual("사용자 제외", merged["candidates"][0]["exclusion_reason"])
        self.assertEqual(1000, merged["candidates"][0]["attributes"]["price_per_100g"])
        self.assertEqual(["판매 상태 확인"], merged["unresolved_requirements"])

    def test_new_candidate_gets_next_stable_id(self):
        merged, stats = UPDATE.merge_candidate_update(
            working(),
            update_payload([update_item()]),
        )

        self.assertEqual(1, stats["added"])
        self.assertEqual("candidate-003", merged["candidates"][-1]["id"])

    def test_verified_candidate_is_not_downgraded_by_weaker_update(self):
        current = working()
        current["candidates"][1]["verification_status"] = "verified"
        merged, _stats = UPDATE.merge_candidate_update(
            current,
            update_payload(
                [
                    update_item(
                        candidate_id="candidate-002",
                        name="후보 B",
                        url="https://example.test/b",
                        verification="unverified",
                    )
                ]
            ),
        )

        self.assertEqual("verified", merged["candidates"][1]["verification_status"])

    def test_partial_research_returns_to_correction_after_merging_candidates(self):
        state = {
            "state": "completed",
            "request": "후보를 찾아줘",
            "candidate_working_set": working(),
            "latest_correction": {"planned_action": "PARTIAL_RESEARCH"},
            "dynamic_state": {"state": "completed"},
            "engine_trace": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "result.md").write_text("동적 조사 결과", encoding="utf-8")
            _run_dir, updated = UPDATE.apply_update_to_state(
                run_dir,
                state,
                update_payload([update_item()]),
                engine=FakeEngine(),
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual("awaiting_correction", updated["state"])
        self.assertEqual("awaiting_correction", updated["candidate_working_set"]["state"])
        self.assertIn("최근 조사 반영", result)

    def test_verify_completion_cannot_complete_with_unresolved_requirements(self):
        state = {
            "state": "completed",
            "request": "후보를 찾아줘",
            "candidate_working_set": working(),
            "latest_correction": {"planned_action": "VERIFY_COMPLETION"},
            "dynamic_state": {"state": "completed"},
            "engine_trace": [],
        }
        payload = update_payload(
            [
                update_item(
                    candidate_id="candidate-002",
                    name="후보 B",
                    url="https://example.test/b",
                    status="kept",
                    verification="verified",
                )
            ],
            recommendation="completed",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "result.md").write_text("결과", encoding="utf-8")
            _run_dir, updated = UPDATE.apply_update_to_state(
                run_dir,
                state,
                payload,
                engine=FakeEngine(),
            )

        self.assertEqual("awaiting_correction", updated["state"])


if __name__ == "__main__":
    unittest.main()
