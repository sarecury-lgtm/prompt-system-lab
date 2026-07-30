import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_evidence_review.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_evidence_review", MODULE_PATH)
REVIEW = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = REVIEW
SPEC.loader.exec_module(REVIEW)


def write_json(path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_run(root):
    run_dir = Path(root) / "psos-review-test"
    run_dir.mkdir()
    (run_dir / "request.txt").write_text("현재 후보를 비교해 줘\n", encoding="utf-8")
    (run_dir / "result.md").write_text(
        "# 원래 결과\n\n후보 A를 추천합니다.\n",
        encoding="utf-8",
    )
    write_json(
        run_dir / "goal_ledger.json",
        {
            "parent_goal": "조건에 맞는 후보 선택",
            "fixed_constraints": ["근거 없는 추천 금지"],
            "completion_condition": "검토 가능한 후보가 제시됨",
        },
    )
    write_json(
        run_dir / "route.json",
        {
            "selected_route": "RESEARCH",
            "execution_status": "completed",
            "run": {},
        },
    )
    write_json(
        run_dir / "result_contract.json",
        {
            "version": 1,
            "route": "RESEARCH",
            "result_type": "research",
            "must_preserve": ["근거 없는 추천 금지"],
            "required_outputs": [
                {
                    "id": "goal-completion",
                    "description": "검토 가능한 후보가 제시됨",
                    "verification": "text",
                }
            ],
            "evidence_requirements": {
                "minimum_sources": 1,
                "source_roles": ["current_listing"],
                "claim_source_mapping": True,
            },
            "user_review": {
                "needed": True,
                "evidence_types": ["web", "image"],
            },
            "failure_policy": "no_winner",
        },
    )
    bundle = {
        "version": 1,
        "contract_sha256": "a" * 64,
        "result_status": "completed",
        "subject_mapping": "result_only",
        "review_required": True,
        "subjects": [{"id": "result", "label": "후보 비교", "kind": "result"}],
        "requirements": [
            {
                "id": "goal-completion",
                "description": "검토 가능한 후보가 제시됨",
                "status": "satisfied",
                "evidence_item_ids": ["ev-web", "ev-image"],
            }
        ],
        "items": [
            {
                "id": "ev-web",
                "subject_id": "result",
                "kind": "web",
                "source": "https://example.test/product",
                "finding": "현재 상품 페이지",
                "role": "unclassified",
                "origin": "execution.evidence:0",
                "reviewable": True,
                "preview": {
                    "type": "link",
                    "source": "https://example.test/product",
                },
                "integrity": {"sha256": None},
                "review": {"decision": "unreviewed", "note": ""},
            },
            {
                "id": "ev-image",
                "subject_id": "result",
                "kind": "image",
                "source": "https://example.test/photo.jpg",
                "finding": "구매자 사진",
                "role": "visual_observation",
                "origin": "execution.evidence:1",
                "reviewable": True,
                "preview": {
                    "type": "image",
                    "source": "https://example.test/photo.jpg",
                },
                "integrity": {"sha256": None},
                "review": {"decision": "unreviewed", "note": ""},
            },
            {
                "id": "ev-context",
                "subject_id": "result",
                "kind": "provided_context",
                "source": "사용자 원문",
                "finding": "참고 문맥",
                "role": "unclassified",
                "origin": "execution.evidence:2",
                "reviewable": False,
                "preview": {"type": "none", "source": None},
                "integrity": {"sha256": None},
                "review": {"decision": "unreviewed", "note": ""},
            },
        ],
        "review": {
            "status": "pending",
            "allowed_decisions": ["keep", "question", "exclude"],
            "decision_file": "evidence_review.json",
            "review_markdown": "evidence_review.md",
        },
    }
    write_json(run_dir / "evidence_bundle.json", bundle)
    bundle_sha = hashlib.sha256(
        (run_dir / "evidence_bundle.json").read_bytes()
    ).hexdigest()
    write_json(
        run_dir / "evidence_review.json",
        {
            "version": 1,
            "bundle_sha256": bundle_sha,
            "allowed_decisions": ["keep", "question", "exclude"],
            "decisions": [
                {
                    "evidence_id": "ev-web",
                    "decision": "unreviewed",
                    "note": "",
                },
                {
                    "evidence_id": "ev-image",
                    "decision": "unreviewed",
                    "note": "",
                },
            ],
        },
    )
    return run_dir, bundle_sha


class EvidenceReviewTests(unittest.TestCase):
    def test_save_review_is_hash_bound_and_covers_every_reviewable_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = make_run(temp_dir)
            review, review_sha = REVIEW.save_review(
                run_dir,
                {
                    "bundle_sha256": bundle_sha,
                    "reviewer_note": "사진은 옵션이 달라 보임",
                    "decisions": [
                        {
                            "evidence_id": "ev-web",
                            "decision": "keep",
                            "note": "현재 페이지",
                        },
                        {
                            "evidence_id": "ev-image",
                            "decision": "question",
                            "note": "옵션 확인",
                        },
                    ],
                },
            )
            saved_bytes = (run_dir / "evidence_review.json").read_bytes()
            saved = json.loads(saved_bytes.decode("utf-8"))

        self.assertEqual("completed", review["review_status"])
        self.assertEqual(review, saved)
        self.assertEqual(hashlib.sha256(saved_bytes).hexdigest(), review_sha)

    def test_save_review_rejects_stale_hash_unknown_id_and_partial_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = make_run(temp_dir)
            valid = {
                "bundle_sha256": bundle_sha,
                "reviewer_note": "",
                "decisions": [
                    {"evidence_id": "ev-web", "decision": "keep", "note": ""},
                    {"evidence_id": "ev-image", "decision": "exclude", "note": ""},
                ],
            }
            stale = dict(valid)
            stale["bundle_sha256"] = "0" * 64
            with self.assertRaisesRegex(REVIEW.EvidenceReviewError, "바뀌었습니다"):
                REVIEW.save_review(run_dir, stale)

            unknown = json.loads(json.dumps(valid))
            unknown["decisions"][1]["evidence_id"] = "ev-unknown"
            with self.assertRaisesRegex(REVIEW.EvidenceReviewError, "검토할 수 없는"):
                REVIEW.save_review(run_dir, unknown)

            partial = json.loads(json.dumps(valid))
            partial["decisions"] = partial["decisions"][:1]
            with self.assertRaisesRegex(REVIEW.EvidenceReviewError, "모든 검토 가능"):
                REVIEW.save_review(run_dir, partial)

    def test_revision_context_preserves_original_and_encodes_review_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = make_run(temp_dir)
            original = (run_dir / "result.md").read_text(encoding="utf-8")
            REVIEW.save_review(
                run_dir,
                {
                    "bundle_sha256": bundle_sha,
                    "reviewer_note": "의심 사진 없이 다시 판단",
                    "decisions": [
                        {
                            "evidence_id": "ev-web",
                            "decision": "keep",
                            "note": "판매 페이지 유지",
                        },
                        {
                            "evidence_id": "ev-image",
                            "decision": "exclude",
                            "note": "다른 옵션 사진",
                        },
                    ],
                },
            )
            record = REVIEW.build_revision_context(run_dir)
            context = (run_dir / record["path"]).read_text(encoding="utf-8")
            request = REVIEW.build_revision_request(record["path"], run_dir.name)
            parent_after = (run_dir / "result.md").read_text(encoding="utf-8")

        self.assertEqual(original, parent_after)
        self.assertIn("keep", context)
        self.assertIn("question", context)
        self.assertIn("exclude", context)
        self.assertIn("https://example.test/product", context)
        self.assertIn("https://example.test/photo.jpg", context)
        self.assertIn("원본 실행 파일은 변경하지", request)
        self.assertEqual(1, record["actionable_decision_count"])

    def test_revision_context_requires_actionable_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = make_run(temp_dir)
            REVIEW.save_review(
                run_dir,
                {
                    "bundle_sha256": bundle_sha,
                    "reviewer_note": "전부 유지",
                    "decisions": [
                        {"evidence_id": "ev-web", "decision": "keep", "note": ""},
                        {"evidence_id": "ev-image", "decision": "keep", "note": ""},
                    ],
                },
            )
            with self.assertRaisesRegex(REVIEW.EvidenceReviewError, "의심.*제외"):
                REVIEW.build_revision_context(run_dir)


if __name__ == "__main__":
    unittest.main()
