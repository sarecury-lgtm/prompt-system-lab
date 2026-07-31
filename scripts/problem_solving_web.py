#!/usr/bin/env python3
"""Serve a local web interface for the Personal Problem-Solving OS."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as problem_os
import problem_solving_prompt_renderer as prompt_renderer
import problem_solving_status as problem_status


ROOT = SCRIPT_DIR.parent
WEB_DIR = ROOT / "web"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
MAX_REQUEST_CHARS = 10_000
MAX_BODY_BYTES = 50_000
MAX_RENDER_ITEMS = 24
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/renderer.js": ("renderer.js", "text/javascript; charset=utf-8"),
    "/renderer.css": ("renderer.css", "text/css; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compact_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        key: job.get(key)
        for key in (
            "job_id",
            "state",
            "request",
            "search_enabled",
            "workspace_write",
            "allowed_write_paths",
            "approval_id",
            "submitted_at",
            "started_at",
            "finished_at",
            "run_id",
            "route",
            "execution_status",
            "result_markdown",
            "artifacts",
            "evidence",
            "limitations",
            "workspace_receipt",
            "workspace_rollback",
            "error",
        )
    }


def _required_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}을 입력해 주세요.")
    cleaned = value.strip()
    if len(cleaned) > MAX_REQUEST_CHARS:
        raise ValueError(f"{label}은 10,000자 이하여야 합니다.")
    return cleaned


def _string_list(
    payload: dict[str, Any],
    key: str,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_RENDER_ITEMS,
) -> list[str]:
    value = payload.get(key, [])
    if isinstance(value, str):
        values = value.splitlines()
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(f"{label} 형식이 올바르지 않습니다.")
    normalized: list[str] = []
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"{label}에는 문자열만 사용할 수 있습니다.")
        cleaned = item.strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    if len(normalized) < minimum:
        raise ValueError(f"{label}을 {minimum}개 이상 입력해 주세요.")
    if len(normalized) > maximum:
        raise ValueError(f"{label}은 {maximum}개 이하여야 합니다.")
    return normalized


def render_prompt_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Render a final prompt without invoking Codex or any model runtime."""

    goal = _required_text(payload, "goal", "목표")
    core_procedure = _string_list(
        payload,
        "core_procedure",
        "핵심 작업 절차",
        minimum=1,
        maximum=8,
    )
    fixed_constraints = _string_list(
        payload,
        "fixed_constraints",
        "고정 조건",
    )
    completion = _required_text(
        payload,
        "completion_condition",
        "완료 조건",
    )
    output_details = _string_list(
        payload,
        "output_details",
        "추가 출력 조건",
        maximum=7,
    )
    brief = {
        "version": 1,
        "goal": goal,
        "core_procedure": core_procedure,
        "supporting_inputs": _string_list(
            payload,
            "supporting_inputs",
            "보조 입력·도구",
            maximum=8,
        ),
        "fixed_constraints": fixed_constraints,
        "output_contract": [completion, *output_details],
        "defaults_and_exceptions": _string_list(
            payload,
            "defaults_and_exceptions",
            "기본값과 예외",
            maximum=6,
        ),
        "exclusions": _string_list(
            payload,
            "exclusions",
            "제외 범위",
            maximum=6,
        ),
        "upstream_context": _string_list(
            payload,
            "upstream_context",
            "검증된 상위 맥락",
            maximum=8,
        ),
    }
    ledger = {
        "fixed_constraints": fixed_constraints,
        "completion_condition": completion,
    }
    try:
        rendered = prompt_renderer.render_prompt(
            brief,
            ledger,
            prompt_renderer.load_policy(),
        )
    except (
        prompt_renderer.PromptRendererError,
        prompt_renderer.BRIEF.PromptBuildBriefError,
    ) as exc:
        raise ValueError(str(exc)) from exc
    return {
        "run_id": None,
        "route": "PROMPT · NO CODEX",
        "execution_status": "completed",
        "result_markdown": rendered,
        "artifacts": [
            {
                "path": "configs/psos-goal-aware-assistant-policy.md",
                "action": "read",
            },
            {
                "path": "scripts/problem_solving_prompt_renderer.py",
                "action": "used",
            },
        ],
        "evidence": [
            {
                "source": "deterministic_renderer",
                "finding": "Codex와 모델 호출 없이 입력된 구조를 검증해 최종 프롬프트를 렌더링했습니다.",
            }
        ],
        "limitations": [
            "목표·절차·조건을 AI가 추론하거나 보완하지 않고 사용자가 입력한 구조만 렌더링합니다."
        ],
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


def run_problem_solving_request(
    request: str,
    search_enabled: bool,
    run_id: str,
    workspace_write: bool,
    allowed_write_paths: list[str],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    engine = problem_os.CodexEngine(
        ROOT,
        allow_workspace_write=workspace_write,
        allowed_write_paths=(
            allowed_write_paths if workspace_write else None
        ),
        write_approval=approval,
        enable_search=search_enabled,
    )
    run_dir, payload = problem_os.run_request(
        request,
        output_root=problem_os.RUNS_DIR,
        engine=engine,
        run_id=run_id,
    )
    execution = payload["execution"]
    trace = engine.trace()

    def trace_record(name: str) -> dict[str, Any] | None:
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
        return read_json(path) if path.is_file() else None

    return {
        "run_id": run_dir.name,
        "route": payload["route"]["selected_route"],
        "execution_status": execution["status"],
        "result_markdown": (run_dir / "result.md").read_text(encoding="utf-8"),
        "artifacts": execution["artifacts"],
        "evidence": execution["evidence"],
        "limitations": execution["limitations"],
        "workspace_receipt": trace_record("workspace_receipt"),
        "workspace_rollback": trace_record("workspace_rollback"),
    }


class JobManager:
    """Keep a bounded in-memory view of background PSOS executions."""

    def __init__(
        self,
        *,
        runner: Callable[
            [str, bool, str, bool, list[str], dict[str, Any] | None],
            dict[str, Any],
        ] = run_problem_solving_request,
        max_workers: int = 1,
        max_history: int = 20,
    ) -> None:
        self._runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="psos-web",
        )
        self._jobs: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max_history = max_history

    def submit(
        self,
        request: str,
        search_enabled: bool,
        *,
        workspace_write: bool = False,
        allowed_write_paths: list[str] | None = None,
        approval: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = request.strip()
        if not cleaned:
            raise ValueError("요청을 입력해 주세요.")
        if len(cleaned) > MAX_REQUEST_CHARS:
            raise ValueError("요청은 10,000자 이하여야 합니다.")
        if not isinstance(search_enabled, bool):
            raise ValueError("웹 검색 설정이 올바르지 않습니다.")
        scopes = allowed_write_paths or []
        if workspace_write:
            try:
                scopes = problem_os.normalize_write_scopes(ROOT, scopes)
            except problem_os.ProblemSolvingError as exc:
                raise ValueError(str(exc)) from exc
            if not isinstance(approval, dict):
                raise ValueError("승인된 파일 변경 기록이 필요합니다.")
        elif scopes or approval is not None:
            raise ValueError("읽기 전용 작업에는 쓰기 승인 정보를 사용할 수 없습니다.")
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        run_id = problem_os.make_run_id()
        job = {
            "job_id": job_id,
            "state": "queued",
            "request": cleaned,
            "search_enabled": search_enabled,
            "workspace_write": workspace_write,
            "allowed_write_paths": scopes,
            "approval_id": (
                approval.get("approval_id")
                if isinstance(approval, dict)
                else None
            ),
            "_approval": (
                json.loads(json.dumps(approval))
                if isinstance(approval, dict)
                else None
            ),
            "submitted_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "run_id": run_id,
            "route": None,
            "execution_status": None,
            "result_markdown": None,
            "artifacts": [],
            "evidence": [],
            "limitations": [],
            "workspace_receipt": None,
            "workspace_rollback": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._order.append(job_id)
            self._trim_finished()
        self._executor.submit(self._run, job_id)
        return compact_job(job)

    def _trim_finished(self) -> None:
        while len(self._order) > self._max_history:
            removable = next(
                (
                    identifier
                    for identifier in self._order
                    if self._jobs[identifier]["state"] in {"completed", "failed"}
                ),
                None,
            )
            if removable is None:
                return
            self._order.remove(removable)
            self._jobs.pop(removable, None)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["state"] = "running"
            job["started_at"] = utc_now()
            request = job["request"]
            search_enabled = job["search_enabled"]
            workspace_write = job["workspace_write"]
            allowed_write_paths = job["allowed_write_paths"]
            approval = (
                job.get("_approval")
                if workspace_write
                else None
            )
        try:
            result = self._runner(
                request,
                search_enabled,
                job["run_id"],
                workspace_write,
                allowed_write_paths,
                approval,
            )
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job["state"] = "failed"
                job["error"] = str(exc).strip() or exc.__class__.__name__
                job["finished_at"] = utc_now()
            return
        with self._lock:
            job = self._jobs[job_id]
            job.update(result)
            job["state"] = "completed"
            job["finished_at"] = utc_now()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return compact_job(job) if job is not None else None

    def active_run_ids(self) -> set[str]:
        with self._lock:
            return {
                job["run_id"]
                for job in self._jobs.values()
                if job["state"] in {"queued", "running"}
            }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def compact_approval(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "approval_id",
            "status",
            "request",
            "request_sha256",
            "search_enabled",
            "workspace",
            "allowed_write_paths",
            "requested_at",
            "expires_at",
            "approved_at",
            "rejected_at",
            "job_id",
            "error",
        )
    }


class ApprovalManager:
    """Create one-time, expiring local write approvals."""

    def __init__(self, jobs: JobManager) -> None:
        self._jobs = jobs
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _expire(self, record: dict[str, Any]) -> None:
        if (
            record["status"] == "pending"
            and dt.datetime.now(dt.timezone.utc)
            >= dt.datetime.fromisoformat(record["expires_at"])
        ):
            record["status"] = "expired"

    def create(
        self,
        request: str,
        search_enabled: bool,
        allowed_write_paths: Any,
    ) -> dict[str, Any]:
        cleaned = request.strip()
        if not cleaned:
            raise ValueError("요청을 입력해 주세요.")
        if len(cleaned) > MAX_REQUEST_CHARS:
            raise ValueError("요청은 10,000자 이하여야 합니다.")
        if not isinstance(search_enabled, bool):
            raise ValueError("웹 검색 설정이 올바르지 않습니다.")
        try:
            scopes = problem_os.normalize_write_scopes(
                ROOT,
                allowed_write_paths,
            )
        except problem_os.ProblemSolvingError as exc:
            raise ValueError(str(exc)) from exc
        requested = dt.datetime.now(dt.timezone.utc)
        record = {
            "version": 1,
            "approval_id": f"approval-{uuid.uuid4().hex[:16]}",
            "status": "pending",
            "request": cleaned,
            "request_sha256": hashlib.sha256(
                cleaned.encode("utf-8")
            ).hexdigest(),
            "search_enabled": search_enabled,
            "workspace": str(ROOT.resolve()),
            "allowed_write_paths": scopes,
            "requested_at": requested.isoformat(),
            "expires_at": (requested + dt.timedelta(minutes=10)).isoformat(),
            "approved_at": None,
            "rejected_at": None,
            "job_id": None,
            "error": None,
        }
        with self._lock:
            self._records[record["approval_id"]] = record
        return compact_approval(record)

    def get(self, approval_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None:
                return None
            self._expire(record)
            return compact_approval(record)

    def approve(self, approval_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None:
                raise KeyError("승인 요청을 찾을 수 없습니다.")
            self._expire(record)
            if record["status"] != "pending":
                raise ValueError(
                    f"승인 요청을 실행할 수 없는 상태입니다: {record['status']}"
                )
            record["status"] = "approved"
            record["approved_at"] = utc_now()
            evidence = {
                key: record[key]
                for key in (
                    "version",
                    "approval_id",
                    "status",
                    "request_sha256",
                    "workspace",
                    "allowed_write_paths",
                    "requested_at",
                    "expires_at",
                    "approved_at",
                )
            }
            evidence["approval_method"] = "local_web_explicit_click"
            evidence["constraints"] = {
                "deletions_allowed": False,
                "outside_scope_action": "rollback",
                "unreported_change_action": "rollback",
            }
        try:
            job = self._jobs.submit(
                record["request"],
                record["search_enabled"],
                workspace_write=True,
                allowed_write_paths=record["allowed_write_paths"],
                approval=evidence,
            )
        except Exception as exc:
            with self._lock:
                record["status"] = "failed"
                record["error"] = str(exc).strip() or exc.__class__.__name__
            raise
        with self._lock:
            record["job_id"] = job["job_id"]
            return compact_approval(record), job

    def reject(self, approval_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None:
                raise KeyError("승인 요청을 찾을 수 없습니다.")
            self._expire(record)
            if record["status"] != "pending":
                raise ValueError(
                    f"승인 요청을 취소할 수 없는 상태입니다: {record['status']}"
                )
            record["status"] = "rejected"
            record["rejected_at"] = utc_now()
            return compact_approval(record)


def safe_run_dir(run_id: str, runs_root: Path = problem_os.RUNS_DIR) -> Path:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("실행 ID 형식이 올바르지 않습니다.")
    root = runs_root.expanduser().resolve()
    candidate = (root / run_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("실행 경로가 허용 범위를 벗어났습니다.") from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"실행 기록을 찾을 수 없습니다: {run_id}")
    return candidate


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return payload


def load_run(run_id: str, runs_root: Path = problem_os.RUNS_DIR) -> dict[str, Any]:
    run_dir = safe_run_dir(run_id, runs_root)
    ledger = read_json(run_dir / "goal_ledger.json")
    route = read_json(run_dir / "route.json")
    receipt_path = next(
        iter(sorted(run_dir.glob("*-workspace-receipt.json"))),
        None,
    )
    rollback_path = next(
        iter(sorted(run_dir.glob("*-workspace-rollback.json"))),
        None,
    )
    approval_path = run_dir / "web-write-approval.json"
    return {
        "run_id": run_id,
        "request": (run_dir / "request.txt").read_text(encoding="utf-8").strip(),
        "result_markdown": (run_dir / "result.md").read_text(encoding="utf-8"),
        "route": route.get("selected_route"),
        "execution_status": route.get("execution_status"),
        "route_reason": route.get("route_reason"),
        "artifacts": route.get("artifacts", []),
        "evidence": route.get("evidence", []),
        "limitations": route.get("limitations", []),
        "goal": ledger.get("parent_goal"),
        "current_step": ledger.get("current_step"),
        "workspace_receipt": (
            read_json(receipt_path) if receipt_path is not None else None
        ),
        "workspace_rollback": (
            read_json(rollback_path) if rollback_path is not None else None
        ),
        "write_approval": (
            read_json(approval_path) if approval_path.is_file() else None
        ),
    }


def find_chrome() -> Path | None:
    names = ("chrome.exe", "chrome") if os.name == "nt" else ("google-chrome", "chrome")
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def open_browser(url: str, browser_name: str) -> None:
    if browser_name == "chrome":
        chrome = find_chrome()
        if chrome is None:
            print(f"Chrome을 찾지 못했습니다. 직접 여세요: {url}", file=sys.stderr)
            return
        subprocess.Popen([str(chrome), url])
        return
    import webbrowser

    webbrowser.open(url)


class PsosRequestHandler(BaseHTTPRequestHandler):
    server_version = "PSOSWeb/2"

    @property
    def app(self) -> "PsosHTTPServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[psos-web] {self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def send_static(self, relative: str, content_type: str) -> None:
        path = (self.app.web_dir / relative).resolve()
        try:
            path.relative_to(self.app.web_dir.resolve())
            content = path.read_bytes()
        except (ValueError, OSError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'")
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type은 application/json이어야 합니다.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length가 올바르지 않습니다.") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("요청 본문 크기가 허용 범위를 벗어났습니다.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("올바른 UTF-8 JSON이 아닙니다.") from exc
        if not isinstance(payload, dict):
            raise ValueError("요청 본문은 JSON 객체여야 합니다.")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in STATIC_FILES:
            relative, content_type = STATIC_FILES[path]
            self.send_static(relative, content_type)
            return
        if path == "/api/status":
            try:
                self.send_json(
                    problem_status.build_status(
                        exclude_run_ids=self.app.jobs.active_run_ids(),
                    )
                )
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if path.startswith("/api/jobs/"):
            job = self.app.jobs.get(path.removeprefix("/api/jobs/"))
            if job is None:
                self.send_json({"error": "작업을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
            else:
                self.send_json(job)
            return
        if path.startswith("/api/approvals/"):
            approval = self.app.approvals.get(
                path.removeprefix("/api/approvals/")
            )
            if approval is None:
                self.send_json(
                    {"error": "승인 요청을 찾을 수 없습니다."},
                    HTTPStatus.NOT_FOUND,
                )
            else:
                self.send_json(approval)
            return
        if path.startswith("/api/runs/"):
            try:
                self.send_json(load_run(path.removeprefix("/api/runs/")))
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/render-prompt":
            try:
                self.send_json(render_prompt_request(self.read_json_body()))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if path == "/api/jobs":
            try:
                payload = self.read_json_body()
                job = self.app.jobs.submit(
                    payload.get("request", ""),
                    payload.get("search_enabled", False),
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(job, HTTPStatus.ACCEPTED)
            return
        if path == "/api/approvals":
            try:
                payload = self.read_json_body()
                approval = self.app.approvals.create(
                    payload.get("request", ""),
                    payload.get("search_enabled", False),
                    payload.get("allowed_write_paths"),
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json(approval, HTTPStatus.CREATED)
            return
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "approvals"]:
            approval_id, action = parts[2], parts[3]
            try:
                if action == "execute":
                    approval, job = self.app.approvals.approve(approval_id)
                    self.send_json(
                        {"approval": approval, "job": job},
                        HTTPStatus.ACCEPTED,
                    )
                    return
                if action == "reject":
                    self.send_json(self.app.approvals.reject(approval_id))
                    return
            except KeyError as exc:
                self.send_json(
                    {"error": str(exc.args[0])},
                    HTTPStatus.NOT_FOUND,
                )
                return
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
        self.send_error(HTTPStatus.NOT_FOUND)


class PsosHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        jobs: JobManager,
        approvals: ApprovalManager | None = None,
        web_dir: Path = WEB_DIR,
    ) -> None:
        super().__init__(server_address, PsosRequestHandler)
        self.jobs = jobs
        self.approvals = approvals or ApprovalManager(jobs)
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
    jobs = JobManager()
    server = PsosHTTPServer((args.host, args.port), jobs=jobs)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"
    print(f"PSOS 화면: {url}")
    print("종료: Ctrl+C")
    if args.open_browser:
        threading.Timer(0.3, open_browser, args=(url, args.open_browser)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPSOS 화면을 종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
