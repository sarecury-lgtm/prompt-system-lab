import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_controller_session as BASE
import problem_solving_controller_session_verified as VERIFIED
import problem_solving_domain_adapters as DOMAINS
import problem_solving_evidence_verifier as VERIFIER
import problem_solving_request_contract as REQUEST


FIXTURE = (
    ROOT
    / "evaluation"
    / "psos-controller"
    / "fixtures"
    / "stock-timing-msft-failure"
)


def stock_contract(request="오늘 사면 좋은 주식 하나를 추천해 줘."):
    adapter_id = DOMAINS.detect_adapter_id(request)
    contract = REQUEST.build_request_contract(
        request,
        domain_hint=adapter_id or "generic",
    )
    contract = DOMAINS.augment_contract(contract, adapter_id)
    obligations = [
        *REQUEST.build_evidence_obligations(contract),
        *DOMAINS.additional_obligations(contract, adapter_id),
    ]
    return adapter_id, contract, obligations


def complete_stock_result():
    evidence = [
        {"id": "px-aaa", "source": "official market data", "finding": "AAA current price"},
        {"id": "px-bbb", "source": "official market data", "finding": "BBB current price"},
        {"id": "px-ccc", "source": "official market data", "finding": "CCC current price"},
        {"id": "fund-aaa", "source": "issuer filing", "finding": "AAA operating evidence"},
    ]
    return {
        "version": 1,
        "session_id": "stock-pass",
        "action_id": "stock-pass-a1",
        "route": "RESEARCH",
        "status": "completed",
        "completion": {"met": True, "missing": []},
        "evidence": evidence,
        "coverage": {
            "search_scope": {
                "description": "Screened liquid US common stocks before comparing finalists.",
                "universe": "US-listed liquid common stocks available through the user's broker",
                "screened_count": 120,
                "filters": ["liquidity", "fresh catalyst", "current downside control"],
                "finalist_ids": ["AAA", "BBB", "CCC"],
            },
            "current_state": {
                "checked_at": "2026-08-06T22:15:00+09:00",
                "items": [
                    {"subject_id": "AAA", "evidence_refs": ["px-aaa"]},
                    {"subject_id": "BBB", "evidence_refs": ["px-bbb"]},
                    {"subject_id": "CCC", "evidence_refs": ["px-ccc"]},
                ],
            },
            "comparison": {
                "criteria": ["current entry fit", "upside/downside", "fresh evidence"],
                "candidate_ids": ["AAA", "BBB", "CCC"],
                "records": [
                    {"candidate_id": "AAA", "summary": "best current fit"},
                    {"candidate_id": "BBB", "summary": "weaker downside"},
                    {"candidate_id": "CCC", "summary": "less certain catalyst"},
                ],
            },
            "selection": {
                "selected_ids": ["AAA"],
                "selected_id": "AAA",
                "action": "Buy only inside the stated entry zone.",
                "reason": "Best current evidence-adjusted upside/downside among finalists.",
            },
            "action_fit": {
                "selected_id": "AAA",
                "requested_action": "act_now",
                "time_basis": "current session market check",
                "upside_reference": "first resistance and estimate range",
                "downside_reference": "support below entry",
                "invalidation": "close below stated support",
                "evidence_refs": ["px-aaa", "fund-aaa"],
            },
            "assumptions": [
                {
                    "name": "holding horizon",
                    "value": "2 to 6 weeks",
                    "basis": "user",
                    "material": True,
                    "sensitivity": "",
                }
            ],
            "obligation_evidence": [],
            "domain": {
                "stock_decision": {
                    "screening_record": {
                        "universe": "US-listed liquid common stocks available through the user's broker",
                        "as_of": "2026-08-06T22:15:00+09:00",
                        "screened_count": 120,
                        "filters": ["liquidity", "fresh catalyst", "current downside control"],
                        "finalist_ids": ["AAA", "BBB", "CCC"],
                    },
                    "selected_entry_fit": {
                        "ticker": "AAA",
                        "current_price": 101.5,
                        "checked_at": "2026-08-06T22:15:00+09:00",
                        "entry_zone": "100 to 102",
                        "invalidation": "daily close below 96",
                        "upside_reference": "112 first target",
                        "downside_reference": "96 invalidation",
                        "risk_reward": 2.1,
                        "chase_risk": "Do not enter above 103 without a new setup.",
                        "evidence_refs": ["px-aaa", "fund-aaa"],
                    },
                }
            },
        },
        "artifacts": [],
        "limitations": [],
        "continuation": {
            "objective": "",
            "suggested_route": None,
            "changed_dimension": "none",
            "question": "",
        },
    }


def raw_action_result(state, payload, answer="structured answer"):
    packet = state["current_action"]["packet"]
    value = dict(payload)
    value["session_id"] = state["session_id"]
    value["action_id"] = packet["action_id"]
    value["route"] = packet["route"]
    return (
        answer
        + "\n\n"
        + BASE.START_MARKER
        + "\n```json\n"
        + json.dumps(value, ensure_ascii=False)
        + "\n```\n"
        + BASE.END_MARKER
    )


class RequestVerificationTests(unittest.TestCase):
    def test_current_open_selection_generates_obligations_without_stock_words(self):
        contract = REQUEST.build_request_contract("오늘 쓸 수 있는 러닝화 하나를 추천해 줘")
        obligations = REQUEST.build_evidence_obligations(contract)
        ids = {item["id"] for item in obligations}

        self.assertEqual("current", contract["decision_time"])
        self.assertEqual("open_set", contract["target_scope"]["kind"])
        self.assertEqual(1, contract["selection_count"])
        self.assertIn("candidate_search_scope", ids)
        self.assertIn("current_state_record", ids)
        self.assertIn("final_selection", ids)
        self.assertNotIn("stock_candidate_universe", ids)

    def test_direct_analysis_is_not_burdened_with_candidate_or_stock_obligations(self):
        request = "주어진 댓글의 논리적 비약을 분석해 줘"
        contract = REQUEST.build_request_contract(request)
        obligations = REQUEST.build_evidence_obligations(contract)
        ids = {item["id"] for item in obligations}

        self.assertEqual("specified_or_bounded", contract["target_scope"]["kind"])
        self.assertFalse(contract["current_conditions_required"])
        self.assertEqual({"goal_fidelity", "assumption_traceability"}, ids)
        self.assertIsNone(DOMAINS.detect_adapter_id(request))

    def test_supplied_msft_answer_fails_observable_completion(self):
        adapter_id, contract, obligations = stock_contract()
        answer = (FIXTURE / "legacy_answer.md").read_text(encoding="utf-8")
        result = {
            "status": "completed",
            "completion": {"met": True, "missing": []},
            "evidence": [
                {"id": "e-msft-q4", "source": "Microsoft Investor Relations"},
                {"id": "e-msft-price", "source": "MarketWatch"},
            ],
            "coverage": {},
        }
        verdict = VERIFIER.verify_result(
            contract,
            obligations,
            answer,
            result,
            domain_adapter=DOMAINS.get_adapter(adapter_id),
        )
        joined = "\n".join(verdict["missing_conditions"])

        self.assertFalse(verdict["satisfied"])
        self.assertIn("후보군", joined)
        self.assertIn("현재가", joined)
        self.assertIn("보유 기간", joined)
        self.assertTrue((FIXTURE / "request.txt").is_file())

    def test_complete_stock_evidence_can_pass_without_fixed_ticker_or_no_buy_rule(self):
        adapter_id, contract, obligations = stock_contract()
        result = complete_stock_result()
        verdict = VERIFIER.verify_result(
            contract,
            obligations,
            "AAA is the current first choice with a bounded entry plan.",
            result,
            domain_adapter=DOMAINS.get_adapter(adapter_id),
        )

        self.assertTrue(verdict["satisfied"], verdict["missing_conditions"])
        self.assertEqual([], verdict["missing_conditions"])

    def test_verified_session_downgrades_unsupported_completed_and_creates_next_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir, state = VERIFIED.create_session(
                "오늘 사면 좋은 주식 하나를 추천해 줘.",
                output_root=Path(temp_dir),
                session_id="stock-regression-session",
            )
            unsupported = {
                "version": 1,
                "session_id": state["session_id"],
                "action_id": state["current_action"]["packet"]["action_id"],
                "route": state["current_action"]["packet"]["route"],
                "status": "completed",
                "completion": {"met": True, "missing": []},
                "evidence": [],
                "coverage": VERIFIER.empty_coverage(),
                "artifacts": [],
                "limitations": [],
                "continuation": {
                    "objective": "",
                    "suggested_route": None,
                    "changed_dimension": "none",
                    "question": "",
                },
            }
            state = VERIFIED.submit_action_result(
                session_dir,
                raw_action_result(state, unsupported, answer="MSFT is the winner."),
            )
            public = VERIFIED.public_session(state, session_dir=session_dir)

            self.assertEqual("awaiting_execution", state["status"])
            self.assertFalse(public["last_verification"]["satisfied"])
            self.assertIn("candidate", state["current_action"]["packet"]["objective"].lower())
            self.assertIn("request_contract", state["current_action"]["packet"])
            self.assertIn("evidence_obligations", state["current_action"]["packet"])


if __name__ == "__main__":
    unittest.main()
