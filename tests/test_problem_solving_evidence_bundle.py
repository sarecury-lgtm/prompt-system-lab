import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "problem_solving_evidence_bundle.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_evidence_bundle", MODULE_PATH)
BUNDLE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = BUNDLE
SPEC.loader.exec_module(BUNDLE)


def contract(review=True):
    return {
        "version": 1,
        "route": "RESEARCH",
        "result_type": "research",
        "must_preserve": ["사용자 조건 보존"],
        "required_outputs": [
            {
                "id": "goal-completion",
                "description": "검토 가능한 결과가 제공됨",
                "verification": "text",
            },
            {
                "id": "direct-url",
                "description": "직접 URL이 있음",
                "verification": "url",
            },
            {
                "id": "visual-proof",
                "description": "원본 사진을 검토할 수 있음",
                "verification": "visual",
            },
            {
                "id": "receipt-proof",
                "description": "검증 receipt가 있음",
                "verification": "receipt",
            },
        ],
        "evidence_requirements": {
            "minimum_sources": 1,
            "source_roles": ["current_listing"],
            "claim_source_mapping": True,
        },
        "user_review": {
            "needed": review,
            "evidence_types": ["web", "image"] if review else [],
        },
        "failure_policy": "no_winner",
    }


class EvidenceBundleTests(unittest.TestCase):
    def test_bundle_deduplicates_sources_and_preserves_visual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            receipt_path = run_dir / "executor-receipt.json"
            receipt_path.write_text(
                json.dumps({"verified": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            image_url = "https://example.test/review-photo.jpg"
            product_url = "https://example.test/product/123"
            execution = {
                "status": "completed",
                "summary": "완료",
                "result_markdown": (
                    f"[상품 페이지]({product_url})\n\n"
                    f"![구매자 단면 사진]({image_url})"
                ),
                "capabilities_used": ["web_search"],
                "needed_capability": None,
                "handoff": None,
                "artifacts": [],
                "evidence": [
                    {
                        "source": product_url,
                        "finding": "현재 판매 페이지",
                        "kind": "web",
                    },
                    {
                        "source": image_url,
                        "finding": "구매자 후기 사진",
                        "kind": "web",
                    },
                ],
                "limitations": [],
            }
            assessment = {
                "requirements": [
                    {
                        "id": "goal-completion",
                        "status": "satisfied",
                        "evidence_refs": ["result_markdown"],
                    },
                    {
                        "id": "direct-url",
                        "status": "satisfied",
                        "evidence_refs": ["evidence:0"],
                    },
                    {
                        "id": "visual-proof",
                        "status": "satisfied",
                        "evidence_refs": ["evidence:1"],
                    },
                    {
                        "id": "receipt-proof",
                        "status": "satisfied",
                        "evidence_refs": ["receipt:executor-receipt.json"],
                    },
                ]
            }
            bundle = BUNDLE.build_evidence_bundle(
                run_dir,
                "현재 후보를 조사해 줘",
                {"current_goal_hypothesis": "현재 후보를 비교하고 직접 검토"},
                contract(),
                "a" * 64,
                execution,
                assessment,
            )
            sources = [item["source"] for item in bundle["items"]]
            self.assertEqual(len(sources), len(set(sources)))
            image_item = next(item for item in bundle["items"] if item["source"] == image_url)
            self.assertEqual("image", image_item["kind"])
            self.assertEqual("image", image_item["preview"]["type"])
            self.assertEqual("pending", bundle["review"]["status"])
            visual = next(item for item in bundle["requirements"] if item["id"] == "visual-proof")
            self.assertEqual([image_item["id"]], visual["evidence_item_ids"])

            record = BUNDLE.write_evidence_bundle(run_dir, bundle)
            review = json.loads((run_dir / "evidence_review.json").read_text(encoding="utf-8"))
            markdown = (run_dir / "evidence_review.md").read_text(encoding="utf-8")
            self.assertEqual(
                hashlib.sha256((run_dir / "evidence_bundle.json").read_bytes()).hexdigest(),
                record["sha256"],
            )
            self.assertEqual(record["sha256"], review["bundle_sha256"])
            self.assertIn(image_url, markdown)
            self.assertIn("![ev-", markdown)
            self.assertIn("[ ] 유지", markdown)

    def test_bundle_does_not_invent_semantic_roles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            execution = {
                "status": "partial",
                "summary": "일부 결과",
                "result_markdown": "확인된 범위만 정리했습니다.",
                "capabilities_used": [],
                "needed_capability": None,
                "handoff": None,
                "artifacts": [],
                "evidence": [
                    {
                        "source": "사용자가 붙여넣은 원문",
                        "finding": "원문에서 확인한 내용",
                        "kind": "provided_context",
                    }
                ],
                "limitations": [],
            }
            bundle = BUNDLE.build_evidence_bundle(
                Path(temp_dir),
                "원문을 검토해 줘",
                {"parent_goal": "원문 검토"},
                contract(review=False),
                "b" * 64,
                execution,
                None,
            )
            context_item = next(
                item for item in bundle["items"] if item["kind"] == "provided_context"
            )
            self.assertEqual("unclassified", context_item["role"])
            self.assertFalse(context_item["reviewable"])
            self.assertEqual("not_assessed", bundle["requirements"][0]["status"])


if __name__ == "__main__":
    unittest.main()
