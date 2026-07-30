#!/usr/bin/env python3
"""Local fixture server for the PSOS visual-evidence browser smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import problem_solving_evidence_review as evidence_review
import problem_solving_quality_web as quality_web
import problem_solving_visual_evidence as visual_evidence


RUN_ID = "psos-visual-e2e"
HOST = "127.0.0.1"
PORT = 8765
RUN_DIR: Path


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(name)
        checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", checksum)

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


REVIEW_IMAGE = _png(640, 480, (234, 166, 124))
SMALL_IMAGE = _png(80, 60, (170, 190, 180))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _initial_bundle() -> dict[str, Any]:
    return {
        "version": 1,
        "contract_sha256": "a" * 64,
        "result_status": "completed",
        "subject_mapping": "result_only",
        "review_required": True,
        "subjects": [{"id": "result", "label": "시각 근거 E2E", "kind": "result"}],
        "requirements": [
            {
                "id": "visual-review",
                "description": "사용자가 선택한 사진을 직접 검토할 수 있다.",
                "status": "satisfied",
                "evidence_item_ids": ["ev-web"],
            }
        ],
        "items": [
            {
                "id": "ev-web",
                "subject_id": "result",
                "kind": "web",
                "source": f"http://{HOST}:{PORT}/shop",
                "finding": "브라우저 E2E용 상품·후기 페이지",
                "role": "current_listing",
                "origin": "e2e_fixture",
                "reviewable": True,
                "preview": {"type": "link", "source": f"http://{HOST}:{PORT}/shop"},
                "integrity": {"sha256": None},
                "review": {"decision": "unreviewed", "note": ""},
            }
        ],
        "review": {
            "status": "pending",
            "allowed_decisions": ["keep", "question", "exclude"],
            "decision_file": "evidence_review.json",
            "review_markdown": "evidence_review.md",
        },
    }


def prepare_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "request.txt").write_text("브라우저 시각 근거 E2E\n", encoding="utf-8")
    (run_dir / "result.md").write_text("# E2E 결과\n\n사진 근거를 검토합니다.\n", encoding="utf-8")
    _write_json(
        run_dir / "route.json",
        {"selected_route": "RESEARCH", "execution_status": "completed", "run": {}},
    )
    _write_json(run_dir / "evidence_bundle.json", _initial_bundle())
    bundle, bundle_sha = evidence_review.load_bundle(run_dir)
    _write_json(run_dir / "evidence_review.json", evidence_review.empty_review(bundle, bundle_sha))


def _safe_run_dir(run_id: str) -> Path:
    if run_id != RUN_ID:
        raise FileNotFoundError("E2E 실행을 찾을 수 없습니다.")
    return RUN_DIR


def fixture_archiver(
    run_dir: Path,
    images: list[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Archive the fixture image without weakening the production network policy."""

    results: dict[str, dict[str, Any]] = {}
    for image in images:
        source = str(image.get("src") or "")
        path = urlparse(source).path
        if path != "/images/review.png":
            results[source] = {
                "status": "unavailable",
                "path": None,
                "sha256": None,
                "media_type": None,
                "byte_count": None,
                "final_url": None,
                "error": "E2E fixture가 제공하지 않는 이미지입니다.",
            }
            continue
        digest = hashlib.sha256(REVIEW_IMAGE).hexdigest()
        relative = Path("evidence") / "images" / f"{digest}.png"
        target = run_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(REVIEW_IMAGE)
        results[source] = {
            "status": "archived",
            "path": relative.as_posix(),
            "sha256": digest,
            "media_type": "image/png",
            "byte_count": len(REVIEW_IMAGE),
            "final_url": source,
            "error": None,
        }
    return results


def public_visual_import(run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    run_dir = _safe_run_dir(run_id)
    result = visual_evidence.import_visual_evidence(
        run_dir,
        payload,
        archiver=fixture_archiver,
    )
    quality_web._update_route_record(run_dir, "evidence_bundle", result["bundle_record"])
    quality_web._update_route_record(run_dir, "visual_evidence_import", result["import"])
    public = quality_web.load_public_evidence(run_id)
    public["import"] = result["import"]
    return public


SHOP_HTML = f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>후보 A 구매 후기</title></head>
<body>
  <main>
    <article class="buyer-review-card">
      <a href="/detail#review-1">
        <img id="review-photo" src="/images/review.png" alt="후보 A 실구매 절단면" width="640" height="480">
      </a>
      <p>구매자가 올린 실제 절단면 사진입니다.</p>
    </article>
    <img id="small-icon" src="/images/small.png" alt="작은 아이콘" width="80" height="60">
  </main>
</body>
</html>
"""

REVIEW_HTML = f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>PSOS E2E Review</title></head>
<body>
  <section id="completed-result">
    <code id="run-id">{RUN_ID}</code>
    <div id="evidence-panel"></div>
  </section>
  <script src="/quality-review.js"></script>
</body>
</html>
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "PSOSVisualE2E/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_bytes(self, content: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length가 올바르지 않습니다.") from exc
        if length <= 0 or length > 2 * 1024 * 1024:
            raise ValueError("요청 본문 크기가 올바르지 않습니다.")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("요청 본문은 JSON 객체여야 합니다.")
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send_json({"ok": True})
            return
        if path == "/shop":
            self._send_bytes(SHOP_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/review":
            self._send_bytes(REVIEW_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/quality-review.js":
            self._send_bytes(
                (ROOT / "web" / "quality-review.js").read_bytes(),
                "text/javascript; charset=utf-8",
            )
            return
        if path == "/images/review.png":
            self._send_bytes(REVIEW_IMAGE, "image/png")
            return
        if path == "/images/small.png":
            self._send_bytes(SMALL_IMAGE, "image/png")
            return

        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "evidence-review":
            try:
                self._send_json(quality_web.load_public_evidence(unquote(parts[2])))
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if len(parts) == 5 and parts[:2] == ["api", "runs"] and parts[3] == "evidence-items":
            try:
                image = quality_web.safe_evidence_image(unquote(parts[2]), unquote(parts[4]))
                self._send_bytes(image.read_bytes(), "image/png")
            except (FileNotFoundError, ValueError, OSError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "visual-evidence":
            try:
                payload = self._read_json()
                self._send_json(
                    public_visual_import(unquote(parts[2]), payload),
                    HTTPStatus.CREATED,
                )
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()

    global RUN_DIR
    RUN_DIR = args.run_dir.expanduser().resolve()
    prepare_run(RUN_DIR)
    quality_web.base_web.safe_run_dir = _safe_run_dir

    server = ThreadingHTTPServer((HOST, PORT), FixtureHandler)
    print(f"READY http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
