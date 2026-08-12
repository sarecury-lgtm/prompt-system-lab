#!/usr/bin/env python3
"""Serve the canonical PSOS UI with quality, review, and visual evidence actions."""

from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import sys
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_evidence_review as evidence_review
import problem_solving_connected_browser as connected_browser
import problem_solving_os_quality_runtime as quality_runtime
import problem_solving_visual_evidence as visual_evidence
import problem_solving_web as base_web


ROOT = SCRIPT_DIR.parent
WEB_DIR = ROOT / "web"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
MAX_PREVIEW_BYTES = 20 * 1024 * 1024
QUALITY_ASSETS = {
    "app.js": "quality-review.js",
    "styles.css": "quality-review.css",
}


def _trace_record(trace: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    path_text = next(
        (
            item.get(name)
            for item in reversed(trace)
            if isinstance(item.get(name), str)
        ),
        None,
    )
    if path_text is None:
        return None
    path = Path(path_text)
    return base_web.read_json(path) if path.is_file() else None


def run_quality_request(
    request: str,
    search_enabled: bool,
    run_id: str,
    workspace_write: bool,
    allowed_write_paths: list[str],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use the complete quality runtime while preserving the canonical web job contract."""

    engine = quality_runtime.OS.CodexEngine(
        ROOT,
        allow_workspace_write=workspace_write,
        allowed_write_paths=allowed_write_paths if workspace_write else None,
        write_approval=approval,
        enable_search=search_enabled,
    )
    run_dir, payload = quality_runtime.run_request(
        request,
        output_root=quality_runtime.OS.RUNS_DIR,
        engine=engine,
        run_id=run_id,
    )
    execution = payload["execution"]
    trace = engine.trace()
    return {
        "run_id": run_dir.name,
        "route": payload["route"]["selected_route"],
        "execution_status": execution["status"],
        "result_markdown": (run_dir / "result.md").read_text(encoding="utf-8"),
        "artifacts": execution["artifacts"],
        "evidence": execution["evidence"],
        "limitations": execution["limitations"],
        "workspace_receipt": _trace_record(trace, "workspace_receipt"),
        "workspace_rollback": _trace_record(trace, "workspace_rollback"),
    }


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def load_public_evidence(run_id: str) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    bundle, bundle_sha = evidence_review.load_bundle(run_dir)
    review = evidence_review.load_review(run_dir)
    public_bundle = copy.deepcopy(bundle)
    subject_labels = {
        subject.get("id"): subject.get("label")
        for subject in public_bundle.get("subjects", [])
        if isinstance(subject, Mapping)
    }
    for item in public_bundle.get("items", []):
        source = str(item.get("source") or "")
        preview = item.get("preview") if isinstance(item.get("preview"), dict) else {}
        preview_type = preview.get("type")
        if preview_type == "image":
            item["preview_url"] = (
                source
                if _is_url(source)
                else f"/api/runs/{run_id}/evidence-items/{item['id']}"
            )
        else:
            item["preview_url"] = None
        item["open_url"] = source if _is_url(source) else None
        item["subject_label"] = subject_labels.get(item.get("subject_id"), "결과 전체")
    return {
        "run_id": run_id,
        "bundle_sha256": bundle_sha,
        "bundle": public_bundle,
        "review": review,
    }


def safe_evidence_image(run_id: str, evidence_id: str) -> Path:
    run_dir = base_web.safe_run_dir(run_id)
    bundle, _bundle_sha = evidence_review.load_bundle(run_dir)
    item = next(
        (
            candidate
            for candidate in bundle.get("items", [])
            if isinstance(candidate, Mapping) and candidate.get("id") == evidence_id
        ),
        None,
    )
    if item is None or item.get("reviewable") is not True or item.get("kind") != "image":
        raise FileNotFoundError("검토 가능한 이미지 근거를 찾을 수 없습니다.")
    source = item.get("source")
    if not isinstance(source, str) or not source.strip() or _is_url(source):
        raise FileNotFoundError("로컬 이미지 근거가 아닙니다.")

    raw = Path(source).expanduser()
    candidates = [raw] if raw.is_absolute() else [run_dir / raw, ROOT / raw]
    root = ROOT.resolve()
    resolved_run = run_dir.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            within_root = resolved.is_relative_to(root)
            within_run = resolved.is_relative_to(resolved_run)
        except (OSError, ValueError):
            continue
        if not (within_root or within_run):
            continue
        if ".git" in resolved.parts or candidate.is_symlink() or not resolved.is_file():
            continue
        if resolved.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if resolved.stat().st_size > MAX_PREVIEW_BYTES:
            raise ValueError("이미지 미리보기 크기가 20MB를 초과합니다.")
        return resolved
    raise FileNotFoundError("허용된 위치에서 이미지 파일을 찾을 수 없습니다.")


def _update_route_record(
    run_dir: Path,
    key: str,
    record: Mapping[str, Any],
) -> None:
    route_path = run_dir / "route.json"
    route = base_web.read_json(route_path)
    route[key] = dict(record)
    run_record = route.get("run")
    if isinstance(run_record, dict):
        run_record[key] = dict(record)
    quality_runtime.OS.write_json(route_path, route)


def save_public_review(run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    review, review_sha = evidence_review.save_review(run_dir, payload)
    record = {
        "path": "evidence_review.json",
        "sha256": review_sha,
        "status": review["review_status"],
        "updated_at": review["updated_at"],
    }
    _update_route_record(run_dir, "evidence_review", record)
    return {"review": review, "record": record}


def import_public_visual_evidence(
    run_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    result = visual_evidence.import_visual_evidence(run_dir, payload)
    _update_route_record(run_dir, "evidence_bundle", result["bundle_record"])
    _update_route_record(run_dir, "visual_evidence_import", result["import"])
    public = load_public_evidence(run_id)
    public["import"] = result["import"]
    return public


def submit_review_revision(
    jobs: base_web.JobManager,
    run_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    search_enabled = payload.get("search_enabled", False)
    if not isinstance(search_enabled, bool):
        raise evidence_review.EvidenceReviewError(
            "수정 실행의 웹 검색 설정이 올바르지 않습니다."
        )
    review_result = save_public_review(run_id, payload)
    context_record = evidence_review.build_revision_context(run_dir)
    context_record = visual_evidence.enrich_revision_context(run_dir, context_record)
    context_path = (run_dir / str(context_record["path"])).resolve()
    try:
        visible_context_path = context_path.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        visible_context_path = str(context_path)
    request = evidence_review.build_revision_request(visible_context_path, run_id)
    job = jobs.submit(request, search_enabled)
    revision_record = evidence_review.record_revision_submission(
        run_dir,
        context_record=context_record,
        child_job=job,
        search_enabled=search_enabled,
        request=request,
    )
    _update_route_record(run_dir, "evidence_revision", revision_record)
    return {
        "review": review_result["review"],
        "context": context_record,
        "revision": revision_record,
        "job": job,
    }


def create_connected_browser_queue(
    run_id: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    reset = bool((payload or {}).get("reset", False))
    return connected_browser.create_queue(run_dir, reset=reset)


def submit_connected_browser_receipt(
    jobs: base_web.JobManager,
    run_id: str,
    target_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = base_web.safe_run_dir(run_id)
    queue = connected_browser.submit_receipt(run_dir, target_id, payload)
    revision = None
    if queue["state"] == "completed" and not queue.get("revision"):
        request = connected_browser.build_revision_request(run_dir, queue)
        revision = jobs.submit(request, True)
        queue = connected_browser.record_revision(run_dir, revision)
    return {"queue": queue, "revision": revision}


class QualityRequestHandler(base_web.PsosRequestHandler):
    server_version = "PSOSQualityWeb/2"

    @property
    def app(self) -> "QualityHTTPServer":
        return self.server  # type: ignore[return-value]

    def send_static(self, relative: str, content_type: str) -> None:
        path = (self.app.web_dir / relative).resolve()
        try:
            path.relative_to(self.app.web_dir.resolve())
            content = path.read_bytes()
            addon_name = QUALITY_ASSETS.get(relative)
            if addon_name:
                addon_path = (self.app.web_dir / addon_name).resolve()
                addon_path.relative_to(self.app.web_dir.resolve())
                content += b"\n\n" + addon_path.read_bytes()
        except (ValueError, OSError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' https: data:; connect-src 'self'",
        )
        self.end_headers()
        self.wfile.write(content)

    def send_image(self, path: Path) -> None:
        try:
            content = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "private, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "runs"]:
            run_id, action = unquote(parts[2]), parts[3]
            if action == "evidence-review":
                try:
                    self.send_json(load_public_evidence(run_id))
                except FileNotFoundError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                except (ValueError, OSError, json.JSONDecodeError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if action == "browser-verification":
                try:
                    run_dir = base_web.safe_run_dir(run_id)
                    self.send_json(connected_browser.load_queue(run_dir))
                except FileNotFoundError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                except (ValueError, OSError, json.JSONDecodeError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
        if (
            len(parts) == 5
            and parts[:2] == ["api", "runs"]
            and parts[3] == "evidence-items"
        ):
            try:
                image = safe_evidence_image(unquote(parts[2]), unquote(parts[4]))
                self.send_image(image)
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if (
            len(parts) == 5
            and parts[:2] == ["api", "runs"]
            and parts[3] == "browser-verification"
        ):
            try:
                self.send_json(
                    submit_connected_browser_receipt(
                        self.app.jobs,
                        unquote(parts[2]),
                        unquote(parts[4]),
                        self.read_json_body(),
                    )
                )
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if len(parts) == 4 and parts[:2] == ["api", "runs"]:
            run_id, action = unquote(parts[2]), parts[3]
            if action == "browser-verification":
                try:
                    self.send_json(
                        create_connected_browser_queue(run_id, self.read_json_body()),
                        HTTPStatus.CREATED,
                    )
                except FileNotFoundError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                except (ValueError, OSError, json.JSONDecodeError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                except Exception as exc:
                    self.send_json(
                        {"error": str(exc).strip() or exc.__class__.__name__},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return
            if action in {"evidence-review", "evidence-revision", "visual-evidence"}:
                try:
                    payload = self.read_json_body()
                    if action == "evidence-review":
                        self.send_json(save_public_review(run_id, payload))
                    elif action == "visual-evidence":
                        self.send_json(
                            import_public_visual_evidence(run_id, payload),
                            HTTPStatus.CREATED,
                        )
                    else:
                        self.send_json(
                            submit_review_revision(self.app.jobs, run_id, payload),
                            HTTPStatus.ACCEPTED,
                        )
                except FileNotFoundError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                except (ValueError, OSError, json.JSONDecodeError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                except Exception as exc:
                    self.send_json(
                        {"error": str(exc).strip() or exc.__class__.__name__},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return
        super().do_POST()


class QualityHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        jobs: base_web.JobManager,
        approvals: base_web.ApprovalManager | None = None,
        web_dir: Path = WEB_DIR,
    ) -> None:
        super().__init__(server_address, QualityRequestHandler)
        self.jobs = jobs
        self.approvals = approvals or base_web.ApprovalManager(jobs)
        self.web_dir = web_dir

    def server_close(self) -> None:
        self.jobs.shutdown()
        super().server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open-browser",
        choices=("default", "chrome"),
        help="서버 시작 후 선택한 브라우저로 화면을 엽니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        print("안전을 위해 로컬 호스트에만 바인딩할 수 있습니다.", file=sys.stderr)
        return 1
    jobs = base_web.JobManager(runner=run_quality_request)
    server = QualityHTTPServer((args.host, args.port), jobs=jobs)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"
    print(f"PSOS 품질 화면: {url}")
    print("종료: Ctrl+C")
    if args.open_browser:
        threading.Timer(0.3, base_web.open_browser, args=(url, args.open_browser)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPSOS 품질 화면을 종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
