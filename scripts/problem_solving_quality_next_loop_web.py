#!/usr/bin/env python3
"""Serve the quality UI with an optional source-scout and correction loop."""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_next_loop_experiment as next_loop
import problem_solving_os as OS
import problem_solving_quality_web as quality_web
import problem_solving_web as base_web


ROOT = SCRIPT_DIR.parent
WEB_DIR = ROOT / "web"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
STATIC_ADDONS = {
    "app.js": ["quality-review.js", "next-loop.js"],
    "styles.css": ["quality-review.css", "next-loop.css"],
}
Runner = Callable[
    [str, bool, str, bool, list[str], dict[str, Any] | None],
    dict[str, Any],
]


def safe_next_loop_run_dir(run_id: str) -> Path:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("실행 ID 형식이 올바르지 않습니다.")
    root = next_loop.DEFAULT_OUTPUT_ROOT.expanduser().resolve()
    candidate = (root / run_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("실행 경로가 허용 범위를 벗어났습니다.") from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"next-loop 실행 기록을 찾을 수 없습니다: {run_id}")
    return candidate


def _source_evidence(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    working = state.get("candidate_working_set")
    if not isinstance(working, Mapping):
        return evidence
    for candidate in working.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        source = candidate.get("source_url")
        finding = candidate.get("why_actionable")
        if isinstance(source, str) and source and isinstance(finding, str) and finding:
            evidence.append({"source": source, "finding": finding, "kind": "source-scout-lead"})
    return evidence


def public_next_loop_payload(run_dir: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    dynamic = state.get("dynamic_state")
    execution = dynamic.get("final_execution") if isinstance(dynamic, Mapping) else None
    execution = execution if isinstance(execution, Mapping) else {}
    interaction_state = str(state.get("state") or "partial")
    limitations = list(execution.get("limitations", []))
    if interaction_state == "awaiting_correction":
        limitations.append("후보 작업대에서 사용자의 짧은 교정을 기다리고 있습니다.")
    elif interaction_state == "awaiting_information":
        limitations.append("결과를 바꾸는 사용자 답변을 기다리고 있습니다.")
    return {
        "run_id": run_dir.name,
        "route": "NEXT_LOOP · 후보 교정",
        "execution_status": interaction_state,
        "result_markdown": (run_dir / "result.md").read_text(encoding="utf-8"),
        "artifacts": [
            {"path": str(run_dir / next_loop.STATE_FILENAME), "action": "state"},
        ],
        "evidence": list(execution.get("evidence", [])) or _source_evidence(state),
        "limitations": limitations,
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


def load_public_next_loop_state(run_id: str) -> dict[str, Any]:
    run_dir = safe_next_loop_run_dir(run_id)
    state_path = run_dir / next_loop.STATE_FILENAME
    if not state_path.is_file():
        raise FileNotFoundError("next-loop 상태 파일이 없습니다.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    payload = public_next_loop_payload(run_dir, state)
    payload.update(
        {
            "interaction_state": state.get("state"),
            "candidate_working_set": state.get("candidate_working_set"),
            "pending_questions": state.get("pending_questions", []),
            "latest_correction": state.get("latest_correction"),
        }
    )
    return payload


def run_next_loop_request(
    request: str,
    _search_enabled: bool,
    run_id: str,
    workspace_write: bool,
    _allowed_write_paths: list[str],
    _approval: dict[str, Any] | None,
) -> dict[str, Any]:
    if workspace_write:
        raise ValueError("후보 교정 루프는 읽기 전용으로만 실행할 수 있습니다.")
    engine = OS.CodexEngine(ROOT, enable_search=True)
    run_dir, state = next_loop.run_next_loop(
        request,
        engine=engine,
        output_root=next_loop.DEFAULT_OUTPUT_ROOT,
        run_id=run_id,
        pause_for_correction=True,
    )
    return public_next_loop_payload(run_dir, state)


def run_next_loop_resume_request(
    envelope: str,
    _search_enabled: bool,
    _job_run_id: str,
    workspace_write: bool,
    _allowed_write_paths: list[str],
    _approval: dict[str, Any] | None,
) -> dict[str, Any]:
    if workspace_write:
        raise ValueError("후보 교정 루프는 읽기 전용으로만 실행할 수 있습니다.")
    payload = json.loads(envelope)
    if not isinstance(payload, dict):
        raise ValueError("재개 요청 형식이 올바르지 않습니다.")
    run_id = payload.get("run_id")
    body = payload.get("body")
    if not isinstance(run_id, str) or not isinstance(body, dict):
        raise ValueError("재개할 실행과 입력이 필요합니다.")
    run_dir = safe_next_loop_run_dir(run_id)
    correction_text = body.get("correction_text")
    answers = body.get("answers")
    if correction_text is not None and not isinstance(correction_text, str):
        raise ValueError("교정 문장은 문자열이어야 합니다.")
    if answers is not None and not isinstance(answers, dict):
        raise ValueError("답변은 객체여야 합니다.")
    engine = OS.CodexEngine(ROOT, enable_search=True)
    run_dir, state = next_loop.resume_next_loop(
        run_dir,
        engine=engine,
        correction_text=correction_text,
        answers=answers,
    )
    return public_next_loop_payload(run_dir, state)


class CombinedJobManager:
    """Expose quality, next-loop start, and next-loop resume jobs through one API."""

    def __init__(
        self,
        *,
        quality_runner: Runner = quality_web.run_quality_request,
        next_runner: Runner = run_next_loop_request,
        resume_runner: Runner = run_next_loop_resume_request,
    ) -> None:
        self._quality = base_web.JobManager(runner=quality_runner)
        self._next = base_web.JobManager(runner=next_runner)
        self._resume = base_web.JobManager(runner=resume_runner)
        self._owners: dict[str, base_web.JobManager] = {}
        self._lock = threading.Lock()

    def _remember(self, job: dict[str, Any], manager: base_web.JobManager) -> dict[str, Any]:
        with self._lock:
            self._owners[str(job["job_id"])] = manager
        return job

    def submit(
        self,
        request: str,
        search_enabled: bool,
        *,
        workspace_write: bool = False,
        allowed_write_paths: list[str] | None = None,
        approval: dict[str, Any] | None = None,
        execution_mode: str = "quality",
    ) -> dict[str, Any]:
        if execution_mode == "next_loop":
            if workspace_write:
                raise ValueError("후보 교정 루프에서는 파일 변경을 사용할 수 없습니다.")
            return self._remember(self._next.submit(request, True), self._next)
        if execution_mode != "quality":
            raise ValueError("지원하지 않는 실행 방식입니다.")
        return self._remember(
            self._quality.submit(
                request,
                search_enabled,
                workspace_write=workspace_write,
                allowed_write_paths=allowed_write_paths,
                approval=approval,
            ),
            self._quality,
        )

    def submit_resume(self, run_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        safe_next_loop_run_dir(run_id)
        envelope = json.dumps(
            {"run_id": run_id, "body": dict(body)},
            ensure_ascii=False,
        )
        return self._remember(self._resume.submit(envelope, True), self._resume)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            owner = self._owners.get(job_id)
        return owner.get(job_id) if owner is not None else None

    def active_run_ids(self) -> set[str]:
        return self._quality.active_run_ids()

    def shutdown(self) -> None:
        self._quality.shutdown()
        self._next.shutdown()
        self._resume.shutdown()


class NextLoopQualityRequestHandler(quality_web.QualityRequestHandler):
    server_version = "PSOSQualityNextLoopWeb/1"

    @property
    def app(self) -> "NextLoopQualityHTTPServer":
        return self.server  # type: ignore[return-value]

    def send_static(self, relative: str, content_type: str) -> None:
        path = (self.app.web_dir / relative).resolve()
        try:
            path.relative_to(self.app.web_dir.resolve())
            chunks = [path.read_bytes()]
            for addon_name in STATIC_ADDONS.get(relative, []):
                addon = (self.app.web_dir / addon_name).resolve()
                addon.relative_to(self.app.web_dir.resolve())
                chunks.append(addon.read_bytes())
            content = b"\n\n".join(chunks)
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

    def do_GET(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["api", "next-loop", "runs"]:
            try:
                self.send_json(load_public_next_loop_state(unquote(parts[3])))
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/jobs":
            try:
                payload = self.read_json_body()
                mode = payload.get("execution_mode", "quality")
                job = self.app.jobs.submit(
                    payload.get("request", ""),
                    payload.get("search_enabled", False),
                    execution_mode=mode,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(job, HTTPStatus.ACCEPTED)
            return
        parts = path.strip("/").split("/")
        if (
            len(parts) == 5
            and parts[:3] == ["api", "next-loop", "runs"]
            and parts[4] == "resume"
        ):
            try:
                job = self.app.jobs.submit_resume(
                    unquote(parts[3]),
                    self.read_json_body(),
                )
                self.send_json({"job": job}, HTTPStatus.ACCEPTED)
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_POST()


class NextLoopQualityHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        jobs: CombinedJobManager,
        approvals: base_web.ApprovalManager | None = None,
        web_dir: Path = WEB_DIR,
    ) -> None:
        super().__init__(server_address, NextLoopQualityRequestHandler)
        self.jobs = jobs
        self.approvals = approvals or base_web.ApprovalManager(jobs)  # type: ignore[arg-type]
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
    jobs = CombinedJobManager()
    server = NextLoopQualityHTTPServer((args.host, args.port), jobs=jobs)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"
    print(f"PSOS next-loop 품질 화면: {url}")
    print("종료: Ctrl+C")
    if args.open_browser:
        threading.Timer(0.3, base_web.open_browser, args=(url, args.open_browser)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPSOS next-loop 품질 화면을 종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
