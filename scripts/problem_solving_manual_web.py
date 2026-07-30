#!/usr/bin/env python3
"""Serve the local PSOS manual ChatGPT bridge UI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_manual as manual
import problem_solving_manual_deep as deep_manual
import problem_solving_os as problem_os

ROOT = SCRIPT_DIR.parent
WEB_DIR = ROOT / "web"
STATIC = {
    "/": ("manual.html", "text/html; charset=utf-8"),
    "/manual": ("manual.html", "text/html; charset=utf-8"),
    "/manual.html": ("manual.html", "text/html; charset=utf-8"),
    "/manual.js": ("manual.js", "text/javascript; charset=utf-8"),
    "/manual.css": ("manual.css", "text/css; charset=utf-8"),
}
MARKDOWN_REFERENCE = re.compile(
    r'^\s*\[[^\]\r\n]+\]:\s+\S+(?:\s+"[^"]*")?\s*$'
)


def strip_trailing_markdown_references(raw: str) -> str:
    """Keep one JSON object while tolerating ChatGPT link definitions after it."""

    text = raw.strip()
    start = text.find("{")
    if start < 0:
        return raw
    try:
        _value, end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return raw
    suffix = text[start + end :].strip()
    if suffix.startswith("```"):
        suffix = suffix[3:].strip()
    if not suffix:
        return text[start : start + end]
    lines = [line for line in suffix.splitlines() if line.strip()]
    if lines and all(MARKDOWN_REFERENCE.fullmatch(line) for line in lines):
        return text[start : start + end]
    return raw


def latest_session(bridge: manual.ManualBridge) -> dict[str, Any] | None:
    """Return the newest manual run, including completed runs."""

    with bridge.lock:
        candidates: list[tuple[str, Path, dict[str, Any]]] = []
        for run_dir in bridge.runs_dir.iterdir():
            if not manual.state_path(run_dir).is_file():
                continue
            try:
                state = manual.read_state(run_dir)
            except manual.ManualBridgeError:
                continue
            candidates.append((state["updated_at"], run_dir, state))
        if not candidates:
            return None
        _, run_dir, state = max(candidates, key=lambda item: item[0])
        return manual.public_state(state, run_dir)


class Handler(BaseHTTPRequestHandler):
    bridge: manual.ManualBridge

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )

    def allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        if origin.startswith("chrome-extension://"):
            return origin
        return (
            origin
            if urlparse(origin).hostname in {"127.0.0.1", "localhost"}
            else None
        )

    def reject_disallowed_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin and self.allowed_origin() is None:
            self.send_error(
                HTTPStatus.FORBIDDEN,
                "Cross-origin bridge request rejected",
            )
            return True
        return False

    def send_response_headers(self, status: int, kind: str, size: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        origin = self.allowed_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()

    def send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response_headers(
            status,
            "application/json; charset=utf-8",
            len(body),
        )
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise manual.ManualBridgeError(
                "Content-Length가 올바르지 않습니다."
            ) from exc
        if (
            length <= 0
            or length
            > manual.MAX_RESPONSE_CHARS + manual.MAX_REQUEST_CHARS + 10_000
        ):
            raise manual.ManualBridgeError("요청 본문 크기가 올바르지 않습니다.")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise manual.ManualBridgeError(
                "JSON 요청 본문을 읽을 수 없습니다."
            ) from exc
        if not isinstance(value, dict):
            raise manual.ManualBridgeError("요청 본문은 JSON 객체여야 합니다.")
        return value

    def do_OPTIONS(self) -> None:
        origin = self.allowed_origin()
        if not origin:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:
        if self.reject_disallowed_origin():
            return
        parsed = urlparse(self.path)
        if parsed.path in STATIC:
            filename, kind = STATIC[parsed.path]
            path = WEB_DIR / filename
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response_headers(HTTPStatus.OK, kind, len(body))
            self.wfile.write(body)
            return
        try:
            if parsed.path == "/api/manual/active":
                self.send_json(HTTPStatus.OK, {"session": self.bridge.active()})
                return
            if parsed.path == "/api/manual/latest":
                self.send_json(
                    HTTPStatus.OK,
                    {"session": latest_session(self.bridge)},
                )
                return
            if parsed.path == "/api/manual/status":
                run_id = parse_qs(parsed.query).get("run_id", [""])[0]
                self.send_json(
                    HTTPStatus.OK,
                    {"session": self.bridge.get(run_id)},
                )
                return
        except manual.ManualBridgeError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.reject_disallowed_origin():
            return
        try:
            value = self.read_json()
            if self.path == "/api/manual/start":
                session = self.bridge.start(
                    str(value.get("request", "")),
                    value.get("search_enabled", False),
                    value.get("research_mode"),
                )
                self.send_json(HTTPStatus.CREATED, {"session": session})
                return
            if self.path == "/api/manual/revise":
                session = self.bridge.revise(
                    str(value.get("parent_run_id", "")),
                    str(value.get("feedback", "")),
                    value.get("research_mode"),
                    value.get("revision_mode"),
                )
                self.send_json(HTTPStatus.CREATED, {"session": session})
                return
            if self.path == "/api/manual/submit":
                response = strip_trailing_markdown_references(
                    str(value.get("response", ""))
                )
                session = self.bridge.submit(
                    str(value.get("run_id", "")),
                    response,
                )
                self.send_json(HTTPStatus.OK, {"session": session})
                return
        except manual.ManualBridgeError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--runs-dir", type=Path, default=problem_os.RUNS_DIR)
    parser.add_argument(
        "--model-policy",
        type=Path,
        default=problem_os.DEFAULT_MODEL_POLICY_PATH,
    )
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            "ERROR: 수동 브리지는 loopback 주소에만 바인딩할 수 있습니다.",
            file=sys.stderr,
        )
        return 1
    bridge = deep_manual.ManualBridge(args.runs_dir, args.model_policy)
    configured = type("ConfiguredHandler", (Handler,), {"bridge": bridge})
    server = ThreadingHTTPServer((args.host, args.port), configured)
    print(f"PSOS manual ChatGPT bridge: http://{args.host}:{args.port}")
    print("종료: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
