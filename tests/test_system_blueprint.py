import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "specs" / "PSOS_SYSTEM_BLUEPRINT.md"
POLICY = ROOT / "problem-solving-project" / "model-policy.json"


class SystemBlueprintTests(unittest.TestCase):
    def test_blueprint_points_to_existing_canonical_sources(self):
        text = BLUEPRINT.read_text(encoding="utf-8")
        canonical_paths = [
            "scripts/problem_solving_os.py",
            "scripts/problem_solving_web.py",
            "problem-solving-project/model-policy.json",
            "schemas/problem-solving-os-route.schema.json",
            "schemas/problem-solving-os-execution.schema.json",
            "scripts/problem_solving_feedback.py",
            "scripts/problem_solving_review.py",
            "scripts/problem_solving_policy_proposal.py",
            "scripts/problem_solving_policy_evaluation.py",
            "scripts/problem_solving_policy_change.py",
            "scripts/problem_solving_status.py",
        ]

        for relative in canonical_paths:
            with self.subTest(path=relative):
                self.assertIn(relative, text)
                self.assertTrue((ROOT / relative).is_file())

    def test_blueprint_covers_active_routes_and_safety_contract(self):
        text = BLUEPRINT.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))

        for route in policy["routes"]:
            with self.subTest(route=route):
                self.assertIn(f"`{route}`", text)
        for required_contract in (
            "model_output: untrusted_claim",
            "explicit_scoped_workspace_write_approval",
            "A model may propose a route, result, artifact, or policy change.",
            "A workspace change is not successful without a verified receipt.",
            "Policy cannot approve or apply itself.",
            "--write-scope",
            "cli-write-approval.json",
            "content_addressed_per_run",
            "legacy v1",
        ):
            with self.subTest(contract=required_contract):
                self.assertIn(required_contract, text)

    def test_entry_documents_link_to_blueprint(self):
        expected_link = "specs/PSOS_SYSTEM_BLUEPRINT.md"

        self.assertIn(
            expected_link,
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            expected_link,
            (ROOT / "USAGE.md").read_text(encoding="utf-8"),
        )

    def test_blueprint_explains_why_each_major_subsystem_was_built(self):
        text = BLUEPRINT.read_text(encoding="utf-8")
        purpose_ids = (
            "preserve-real-goal",
            "remove-method-selection-burden",
            "match-capability-and-cost",
            "produce-results-not-plans",
            "verify-model-claims",
            "make-file-change-safe",
            "learn-without-self-corruption",
            "make-operation-understandable",
        )

        self.assertIn("Why each subsystem was built", text)
        self.assertIn("purpose_to_build:", text)
        for purpose_id in purpose_ids:
            with self.subTest(purpose_id=purpose_id):
                self.assertIn(f"purpose_id: {purpose_id}", text)
        self.assertIn(
            "It is an execution kernel, a local operating surface, an",
            text,
        )
        self.assertIn(
            "evidence system, and a governed learning loop",
            text,
        )


if __name__ == "__main__":
    unittest.main()
