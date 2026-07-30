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
MODULE_PATH = SCRIPTS / "problem_solving_quality_web.py"
SPEC = importlib.util.spec_from_file_location("problem_solving_quality_web", MODULE_PATH)
WEB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = WEB
SPEC.loader.exec_module(WEB)

REVIEW_TEST_PATH = ROOT / "tests" / "test_problem_solving_evidence_review.py"
REVIEW_SPEC = importlib.util.spec_from_file_location("review_test_fixture", REVIEW_TEST_PATH)
FIXTURE = importlib.util.module_from_spec(REVIEW_SPEC)
assert REVIEW_SPEC.loader is not None
sys.modules[REVIEW_SPEC.name] = FIXTURE
REVIEW_SPEC.loader.exec_module(FIXTURE)


PNG = b"\x89PNG\r\n\x1a\n" + b"quality-web-archive"


class FakeJobs:
    def __init__(self):
        self.calls = []

    def submit(self, request, search_enabled):
        self.calls.append((request, search_enabled))
        return {
            "job_id": "job-revision",
            "run_id": "psos-child",
            "state": "queued",
        }


class QualityWebTests(unittest.TestCase):
    def setUp(self):
        self.original_safe_run_dir = WEB.base_web.safe_run_dir
        self.original_visual_import = WEB.visual_evidence.import_visual_evidence

        def import_without_network(run_dir, payload):
            return self.original_visual_import(run_dir, payload, archive=False)

        WEB.visual_evidence.import_visual_evidence = import_without_network

    def tearDown(self):
        WEB.base_web.safe_run_dir = self.original_safe_run_dir
        WEB.visual_evidence.import_visual_evidence = self.original_visual_import

    def bind_run(self, run_dir):
        WEB.base_web.safe_run_dir = lambda run_id: run_dir

    def review_payload(self, bundle_sha, *, image_decision="question", search=False):
        return {
            "bundle_sha256": bundle_sha,
            "reviewer_note": "사진 근거를 다시 확인",
            "search_enabled": search,
            "decisions": [
                {
                    "evidence_id": "ev-web",
                    "decision": "keep",
                    "note": "페이지 유지",
                },
                {
                    "evidence_id": "ev-image",
                    "decision": image_decision,
                    "note": "옵션 의심",
                },
            ],
        }

    def visual_payload(self, bundle_sha):
        return {
            "version": 1,
            "bundle_sha256": bundle_sha,
            "subject_label": "후보 A",
            "source_kind": "seller",
            "page_url": "https://shop.example.test/item/123",
            "page_title": "후보 A 상품 페이지",
            "captured_at": "2026-07-30T18:40:00+00:00",
            "images": [
                {
                    "src": "https://cdn.example.test/product.jpg",
                    "alt": "상품 단면",
                    "width": 1000,
                    "height": 800,
                    "nearby_text": "상품 상세 이미지",
                    "link_url": "https://shop.example.test/item/123",
                }
            ],
        }

    def fake_archiver(self, run_dir, images):
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

    def test_public_bundle_exposes_review_and_external_image_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            self.bind_run(run_dir)
            payload = WEB.load_public_evidence(run_dir.name)

        image = next(
            item for item in payload["bundle"]["items"] if item["id"] == "ev-image"
        )
        self.assertEqual(bundle_sha, payload["bundle_sha256"])
        self.assertEqual("https://example.test/photo.jpg", image["preview_url"])
        self.assertEqual("pending", payload["review"]["review_status"])
        self.assertEqual("후보 비교", image["subject_label"])

    def test_local_image_preview_is_bound_to_bundle_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, _bundle_sha = FIXTURE.make_run(temp_dir)
            image_path = run_dir / "photo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            bundle_path = run_dir / "evidence_bundle.json"
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            image = next(item for item in bundle["items"] if item["id"] == "ev-image")
            image["source"] = "photo.png"
            image["preview"]["source"] = "photo.png"
            FIXTURE.write_json(bundle_path, bundle)
            new_sha = WEB.evidence_review.sha256_file(bundle_path)
            review_path = run_dir / "evidence_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["bundle_sha256"] = new_sha
            FIXTURE.write_json(review_path, review)
            self.bind_run(run_dir)

            public = WEB.load_public_evidence(run_dir.name)
            resolved = WEB.safe_evidence_image(run_dir.name, "ev-image")
            expected_image_path = image_path.resolve()

        public_image = next(
            item for item in public["bundle"]["items"] if item["id"] == "ev-image"
        )
        self.assertTrue(
            public_image["preview_url"].endswith("/evidence-items/ev-image")
        )
        self.assertEqual(expected_image_path, resolved)

    def test_archived_visual_import_uses_local_preview_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            imported = self.original_visual_import(
                run_dir,
                self.visual_payload(bundle_sha),
                archiver=self.fake_archiver,
            )
            self.bind_run(run_dir)
            public = WEB.load_public_evidence(run_dir.name)
            item_id = imported["import"]["archived_item_ids"][0]
            resolved = WEB.safe_evidence_image(run_dir.name, item_id)

        item = next(entry for entry in public["bundle"]["items"] if entry["id"] == item_id)
        self.assertTrue(item["preview_url"].endswith(f"/evidence-items/{item_id}"))
        self.assertEqual(PNG, resolved.read_bytes())
        self.assertEqual("archived", item["archive"]["status"])

    def test_save_review_updates_route_anchor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            self.bind_run(run_dir)
            result = WEB.save_public_review(
                run_dir.name,
                self.review_payload(bundle_sha),
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))

        self.assertEqual("completed", result["review"]["review_status"])
        self.assertEqual(result["record"], route["evidence_review"])
        self.assertEqual(result["record"], route["run"]["evidence_review"])

    def test_visual_import_updates_bundle_route_and_public_subject_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            self.bind_run(run_dir)
            result = WEB.import_public_visual_evidence(
                run_dir.name,
                self.visual_payload(bundle_sha),
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))

        imported = next(item for item in result["bundle"]["items"] if item.get("capture"))
        self.assertEqual("후보 A", imported["subject_label"])
        self.assertEqual(result["bundle_sha256"], route["evidence_bundle"]["sha256"])
        self.assertEqual(
            result["import"]["import_id"],
            route["visual_evidence_import"]["import_id"],
        )
        self.assertEqual(route["evidence_bundle"], route["run"]["evidence_bundle"])

    def test_revision_submission_creates_child_without_overwriting_parent_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            self.bind_run(run_dir)
            original = (run_dir / "result.md").read_text(encoding="utf-8")
            jobs = FakeJobs()
            payload = WEB.submit_review_revision(
                jobs,
                run_dir.name,
                self.review_payload(bundle_sha, search=True),
            )
            route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
            parent_after = (run_dir / "result.md").read_text(encoding="utf-8")
            context_exists = (run_dir / "evidence_revision_context.md").is_file()
            request_exists = (run_dir / "evidence_revision_request.json").is_file()

        self.assertEqual(original, parent_after)
        self.assertEqual(1, len(jobs.calls))
        self.assertTrue(jobs.calls[0][1])
        self.assertIn("원본 실행", jobs.calls[0][0])
        self.assertEqual("psos-child", payload["job"]["run_id"])
        self.assertEqual("psos-child", route["evidence_revision"]["child_run_id"])
        self.assertTrue(context_exists)
        self.assertTrue(request_exists)

    def test_revision_rejects_all_keep_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir, bundle_sha = FIXTURE.make_run(temp_dir)
            self.bind_run(run_dir)
            with self.assertRaisesRegex(
                WEB.evidence_review.EvidenceReviewError,
                "의심.*제외",
            ):
                WEB.submit_review_revision(
                    FakeJobs(),
                    run_dir.name,
                    self.review_payload(bundle_sha, image_decision="keep"),
                )


if __name__ == "__main__":
    unittest.main()
