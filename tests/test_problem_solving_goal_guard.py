import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_goal_guard as GUARD


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class GoalGuardTests(unittest.TestCase):
    def setUp(self):
        self.active = load_json(ROOT / "ACTIVE_GOAL.json")
        self.scope = load_json(ROOT / "governance" / "PSOS_CHANGE_SCOPE.json")
        self.regression = load_json(
            ROOT / "governance" / "PSOS_CROSS_DOMAIN_REGRESSION.json"
        )

    def test_repository_governance_and_representative_paths_pass(self):
        result = GUARD.run_guard(
            [
                "ACTIVE_GOAL.json",
                "scripts/problem_solving_os.py",
                "web/chatgpt-manual-fallback-v5.js",
                "scripts/problem_solving_adaptive_shopping.py",
                "scripts/problem_solving_candidate_working_set.py",
                "tests/test_problem_solving_goal_guard.py",
            ]
        )
        self.assertEqual("pass", result["status"])
        self.assertGreaterEqual(result["distinct_regression_domains"], 4)
        self.assertEqual(2, len(result["classified_files"]["CORE"]))
        self.assertEqual(1, len(result["classified_files"]["ADAPTER"]))
        self.assertEqual(1, len(result["classified_files"]["DOMAIN"]))
        self.assertEqual(2, len(result["classified_files"]["TEST"]))

    def test_unclassified_file_is_rejected(self):
        with self.assertRaisesRegex(GUARD.GoalGuardError, "분류되지 않은"):
            GUARD.validate_changed_files(["scripts/new_shopping_core.py"], self.scope)

    def test_shopping_implementation_cannot_be_declared_core(self):
        scope = copy.deepcopy(self.scope)
        component = next(
            item for item in scope["components"] if item["id"] == "shopping-domain-prototype"
        )
        component["change_class"] = "CORE"
        component["promotion_status"] = "candidate"
        with self.assertRaisesRegex(GUARD.GoalGuardError, "DOMAIN으로 분류"):
            GUARD.validate_scope(scope)

    def test_domain_or_test_component_cannot_be_default_enabled(self):
        scope = copy.deepcopy(self.scope)
        component = next(
            item for item in scope["components"] if item["id"] == "bounded-loop-experiments"
        )
        component["runtime_default_enabled"] = True
        with self.assertRaisesRegex(GUARD.GoalGuardError, "기본 실행 경로"):
            GUARD.validate_scope(scope)

    def test_core_promotion_requires_four_distinct_domains(self):
        regression = copy.deepcopy(self.regression)
        regression["cases"] = regression["cases"][:3]
        with self.assertRaisesRegex(GUARD.GoalGuardError, "사례 수가 부족"):
            GUARD.validate_regression(regression, self.active)

    def test_repeated_cases_from_one_domain_do_not_count_as_general(self):
        regression = copy.deepcopy(self.regression)
        first_domain = regression["cases"][0]["domain"]
        for case in regression["cases"]:
            case["domain"] = first_domain
        with self.assertRaisesRegex(GUARD.GoalGuardError, "도메인이 1개"):
            GUARD.validate_regression(regression, self.active)

    def test_weak_continuation_must_only_continue_current_task(self):
        active = copy.deepcopy(self.active)
        active["continuation_policy"]["meaning"] = (
            "Treat a short continuation as approval for any useful adjacent work."
        )
        with self.assertRaisesRegex(GUARD.GoalGuardError, "current_task만"):
            GUARD.validate_active_goal(active)

    def test_scope_records_the_previous_drift_as_domain_and_test(self):
        records = {
            item["subject"]: item["classification"]
            for item in self.scope["explicit_reclassification"]
        }
        self.assertEqual("DOMAIN", records["adaptive shopping collector"])
        self.assertEqual(
            "TEST",
            records["candidate working set and correction loop"],
        )
        self.assertEqual(
            "ADAPTER",
            records["manual ChatGPT and Codex job packet paths"],
        )


if __name__ == "__main__":
    unittest.main()
