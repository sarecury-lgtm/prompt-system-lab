import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

MODULE_PATH = SCRIPTS / "problem_solving_visual_evidence.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_visual_evidence", MODULE_PATH)
VISUAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = VISUAL
SPEC.loader.exec_module(VISUAL)

REVIEW_TEST_PATH = ROOT / "tests" / "test_problem_solving_evidence_review.py"
REVIEW_SPEC = importlib.util.spec_from_file_location("visual_review_fixture", REVIEW_TEST_PATH)
FIXTURE = importlib.util.module_from_spec(REVIEW_SPEC)
assert REVIEW_SPEC.loader is not None
sys.modules[REVIEW_SPEC.name] = FIXTURE
REVIEW_SPEC.loader.exec_module(FIXTURE)


PNG = b"\x89PNG\r\n\x1a\n" + b"visual-evidence-fixture"


def import_payload(bundle_sha, *, subject="후보 A", src="https://cdn.example.test/photo-a.jpg"):
    return {
        "version": 1,
        "bundle_sha256": bundle_sha,
        "subject_label": subject,
        "source_kind": "buyer_review",
        "page_url": "https://shop.example.test/item/123",
        "page_title": "후보 A 구매 후기",
        "captured_at": "2026-07-30T18:40:00+00:00",
        "images": [
            {
                "src": src,
                "alt": "절단면 사진",
                "width": 1200,
                "height": 900,
                "nearby_text": "구매자가 올린 실제 사진",
                "link_url": "https://shop.example.test/item/123#review-9",
            }
        ],
    }


def fake_archiver(run_dir, images):
    digest = hashlib.sha256(PNG).hexdigest()
    relative = Path("evidence") / "images" / f"{digest}.png"
    target = run_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PNG)
    return {
        image["src"]: {
            "status": "archived",
            "path": relative.as_posix(),
            "sha256": digest,
            "media_type": "image/png",
            "byte_count": len(PNG),
            "final_url": image["src"],
            "error": None,
        }
        for image in images
    }


class VisualEvidenceTests(unittest.TestCase):
    def test_import_upgrades_bundle_and_preserves_existing_decisions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            VISUAL.evidence_review.save_review(
                run_dir,
                {
                    "bundle_sha256": bundle_sha,
                    "reviewer_note": "기존 판정 보존",
                    "decisions": [
                        {"evidence_id": "ev-web", "decision": "keep", "note": "페이지 확인"},
                        {"evidence_id": "ev-image", "decision": "question", "note": "옵션 의심"},
                    ],
                },
            )

            result = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(bundle_sha),
                archive=False,
            )
            bundle = json.loads((run_dir / "evidence_bundle.json").read_text(encoding="utf-8"))
            review = json.loads((run_dir / "evidence_review.json").read_text(encoding="utf-8"))
            history = json.loads((run_dir / "visual_evidence_imports.json").read_text(encoding="utf-8"))

        candidate = next(subject for subject in bundle["subjects"] if subject["kind"] == "candidate")
        imported = next(item for item in bundle["items"] if item.get("capture"))
        decisions = {item["evidence_id"]: item for item in review["decisions"]}
        self.assertEqual(2, bundle["version"])
        self.assertEqual("explicit", bundle["subject_mapping"])
        self.assertEqual("후보 A", candidate["label"])
        self.assertEqual(candidate["id"], imported["subject_id"])
        self.assertEqual("buyer_review", imported["capture"]["source_kind"])
        self.assertNotIn("archive", imported)
        self.assertEqual("keep", decisions["ev-web"]["decision"])
        self.assertEqual("question", decisions["ev-image"]["decision"])
        self.assertEqual("unreviewed", decisions[imported["id"]]["decision"])
        self.assertEqual(result["bundle_record"]["sha256"], review["bundle_sha256"])
        self.assertEqual(result["import"]["import_id"], history["imports"][0]["import_id"])

    def test_import_archives_image_and_preserves_original_url(self):
        original_url = "https://cdn.example.test/photo-a.png"
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            result = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(bundle_sha, src=original_url),
                archiver=fake_archiver,
            )
            imported = next(item for item in result["bundle"]["items"] if item.get("capture"))
            archived_path = run_dir / imported["source"]
            archived_exists = archived_path.is_file()
            archived_bytes = archived_path.read_bytes()
            markdown = (run_dir / "evidence_review.md").read_text(encoding="utf-8")

        self.assertTrue(archived_exists)
        self.assertEqual(PNG, archived_bytes)
        self.assertEqual("archived", imported["archive"]["status"])
        self.assertEqual(original_url, imported["archive"]["original_url"])
        self.assertEqual(imported["archive"]["sha256"], imported["integrity"]["sha256"])
        self.assertEqual([imported["id"]], result["import"]["archived_item_ids"])
        self.assertIn("로컬 보존", markdown)
        self.assertIn(original_url, markdown)

    def test_import_rejects_stale_hash_unsafe_url_and_same_subject_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            stale = import_payload("0" * 64)
            with self.assertRaisesRegex(VISUAL.VisualEvidenceError, "바뀌었습니다"):
                VISUAL.import_visual_evidence(run_dir, stale, archive=False)

            unsafe = import_payload(bundle_sha)
            unsafe["images"][0]["src"] = "data:image/png;base64,AAAA"
            with self.assertRaisesRegex(VISUAL.VisualEvidenceError, "http"):
                VISUAL.validate_import_payload(unsafe)

            first = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(bundle_sha),
                archive=False,
            )
            duplicate = import_payload(first["bundle_record"]["sha256"])
            with self.assertRaisesRegex(VISUAL.VisualEvidenceError, "이미"):
                VISUAL.import_visual_evidence(run_dir, duplicate, archive=False)

    def test_same_image_can_be_explicitly_linked_to_another_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            first = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(bundle_sha, subject="후보 A"),
                archive=False,
            )
            second = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(first["bundle_record"]["sha256"], subject="후보 B"),
                archive=False,
            )
            bundle = second["bundle"]

        candidates = [subject for subject in bundle["subjects"] if subject["kind"] == "candidate"]
        captured = [item for item in bundle["items"] if item.get("capture")]
        self.assertEqual({"후보 A", "후보 B"}, {item["label"] for item in candidates})
        self.assertEqual(2, len(captured))
        self.assertEqual(1, len({VISUAL._original_source(item) for item in captured}))
        self.assertEqual(2, len({item["subject_id"] for item in captured}))

    def test_revision_context_includes_explicit_candidate_capture_and_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            imported = VISUAL.import_visual_evidence(
                run_dir,
                import_payload(bundle_sha),
                archiver=fake_archiver,
            )
            new_item_id = imported["import"]["added_item_ids"][0]
            review = VISUAL.evidence_review.load_review(run_dir)
            decisions = []
            for item in review["decisions"]:
                decision = "question" if item["evidence_id"] == new_item_id else "keep"
                decisions.append(
                    {"evidence_id": item["evidence_id"], "decision": decision, "note": "검토"}
                )
            VISUAL.evidence_review.save_review(
                run_dir,
                {
                    "bundle_sha256": imported["bundle_record"]["sha256"],
                    "reviewer_note": "후보별로 다시 판단",
                    "decisions": decisions,
                },
            )
            base = VISUAL.evidence_review.build_revision_context(run_dir)
            enriched = VISUAL.enrich_revision_context(run_dir, base)
            context = (run_dir / enriched["path"]).read_text(encoding="utf-8")

        self.assertIn("후보별 시각 근거 연결", context)
        self.assertIn("후보 A", context)
        self.assertIn("buyer_review", context)
        self.assertIn("original_url", context)
        self.assertEqual(1, enriched["visual_subject_count"])
        self.assertEqual(1, enriched["visual_item_count"])
        self.assertEqual(1, enriched["archived_visual_item_count"])


if __name__ == "__main__":
    unittest.main()
