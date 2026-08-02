import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_source_scout_experiment.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_source_scout_experiment", MODULE_PATH)
SCOUT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = SCOUT
SPEC.loader.exec_module(SCOUT)


def probe(
    family,
    *,
    specificity="concrete",
    recency="current",
    actionability="lead",
    access="open",
    verification="none",
    leads=1,
):
    return {
        "family": family,
        "queries": [f"{family} query"],
        "concrete_leads": [
            {
                "name": f"{family} lead {index}",
                "url": f"https://example.test/{family.lower()}/{index}",
                "why_actionable": "실제 다음 행동으로 연결된다",
            }
            for index in range(leads)
        ],
        "repeated_specificity": specificity,
        "recency": recency,
        "actionability": actionability,
        "access": access,
        "verification_need": verification,
        "signal_summary": f"{family}에 구체적인 신호가 있다.",
    }


def payload(*probes, external=True):
    return {
        "source_scout": {
            "request_summary": "가장 빠른 정보원을 찾는다",
            "external_research_needed": external,
            "searches_used": len(probes),
            "probes": list(probes),
            "scouting_limitations": [],
        }
    }


class FakeEngine:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def capabilities(self):
        return SCOUT.OS.EngineCapabilities(
            ai_reasoning=True,
            web_search=True,
            workspace_read=True,
            workspace_write=False,
            detail="fake",
        )

    def execute(self, prompt, run_dir, invocation):
        self.calls.append((prompt, invocation))
        return self.output

    def trace(self):
        return [
            {"name": invocation.name, "phase": invocation.phase}
            for _prompt, invocation in self.calls
        ]


class SourceScoutExperimentTests(unittest.TestCase):
    def test_headphones_reuse_strong_community_without_extra_verification(self):
        community = probe("COMMUNITY", actionability="decision_ready", leads=2)
        marketplace = probe(
            "MARKETPLACE",
            specificity="vague",
            actionability="lead",
            leads=1,
        )
        decision = SCOUT.select_strategy(
            SCOUT.validate_probe(payload(community, marketplace), max_searches=4)
        )

        self.assertEqual("COMMUNITY_REUSE", decision["strategy"])
        self.assertEqual("COMMUNITY", decision["primary_source_family"])
        self.assertIsNone(decision["secondary_source_family"])

    def test_shopping_community_lead_uses_marketplace_for_current_verification(self):
        community = probe(
            "COMMUNITY",
            actionability="decision_ready",
            verification="current_state",
            leads=2,
        )
        marketplace = probe("MARKETPLACE", actionability="lead", leads=2)
        decision = SCOUT.select_strategy(
            SCOUT.validate_probe(payload(community, marketplace), max_searches=4)
        )

        self.assertEqual("COMMUNITY_THEN_VERIFY", decision["strategy"])
        self.assertEqual("MARKETPLACE", decision["secondary_source_family"])

    def test_development_idea_prefers_existing_project_index(self):
        reuse = probe("REUSE_INDEX", actionability="decision_ready", leads=2)
        broad = probe(
            "BROAD_WEB",
            specificity="vague",
            recency="unknown",
            actionability="lead",
        )
        decision = SCOUT.select_strategy(
            SCOUT.validate_probe(payload(reuse, broad), max_searches=4)
        )

        self.assertEqual("REUSE_EXISTING", decision["strategy"])
        self.assertEqual("REUSE_INDEX", decision["primary_source_family"])

    def test_blocked_source_loses_to_open_actionable_source(self):
        blocked = probe(
            "COMMUNITY",
            actionability="decision_ready",
            access="blocked",
            leads=2,
        )
        market = probe("MARKETPLACE", actionability="lead", leads=1)
        decision = SCOUT.select_strategy(
            SCOUT.validate_probe(payload(blocked, market), max_searches=4)
        )

        self.assertEqual("MARKET_SCAN", decision["strategy"])

    def test_search_budget_is_rejected(self):
        output = payload(
            probe("COMMUNITY"),
            probe("MARKETPLACE"),
            probe("PRIMARY"),
            probe("BROAD_WEB"),
        )
        output["source_scout"]["searches_used"] = 7
        with self.assertRaisesRegex(SCOUT.SourceScoutError, "최대 4회"):
            SCOUT.validate_probe(output, max_searches=4)

    def test_duplicate_family_and_zero_query_side_discovery_are_merged(self):
        github = probe("REUSE_INDEX", actionability="decision_ready", leads=2)
        product_index = probe("REUSE_INDEX", actionability="lead", leads=1)
        community = probe("COMMUNITY", actionability="lead", leads=1)
        community["queries"] = []
        output = payload(github, product_index, community)
        output["source_scout"]["searches_used"] = 2

        scout = SCOUT.validate_probe(output, max_searches=4)
        decision = SCOUT.select_strategy(scout)

        self.assertEqual(2, len(scout["probes"]))
        self.assertEqual("REUSE_EXISTING", decision["strategy"])
        reuse = next(item for item in scout["probes"] if item["family"] == "REUSE_INDEX")
        self.assertEqual(2, len(reuse["queries"]))
        self.assertEqual(2, len(reuse["concrete_leads"]))

    def test_runner_writes_compact_state_and_result(self):
        engine = FakeEngine(
            payload(
                probe("REUSE_INDEX", actionability="decision_ready", leads=2),
                probe("BROAD_WEB", specificity="vague", recency="unknown"),
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, state = SCOUT.run_source_scout(
                "내 아이디어와 비슷한 기존 프로젝트를 먼저 찾아줘",
                engine=engine,
                output_root=Path(temp_dir),
                context="개발 자체보다 기존 해결책 재사용이 중요하다",
                policy={
                    "routes": {
                        "RESEARCH": {
                            "primary": SCOUT.OS.ModelProfile(
                                model="fake",
                                reasoning_effort="low",
                                web_search=True,
                                sandbox="read-only",
                            )
                        }
                    }
                },
            )
            result = (run_dir / "result.md").read_text(encoding="utf-8")
            saved = (run_dir / "source-scout-state.json").read_text(encoding="utf-8")

        self.assertEqual("REUSE_EXISTING", state["decision"]["strategy"])
        self.assertIn("REUSE_EXISTING", result)
        self.assertIn("source-scout", saved)
        self.assertIn("최대 4회", engine.calls[0][0])


if __name__ == "__main__":
    unittest.main()
