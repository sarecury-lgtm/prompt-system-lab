#!/usr/bin/env python3
"""Expose verified persisted PSOS Controller sessions to the manual ChatGPT adapter."""

from __future__ import annotations

import json
import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

import problem_solving_controller_session_verified as SESSION


MAX_BODY_BYTES = 2_500_000
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")


def _read_json_body(handler: Any) -> dict[str, Any]:
    if handler.headers.get_content_type() != "application/json":
        raise ValueError("Content-Type은 application/json이어야 합니다.")
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ValueError("Content-Length가 올바르지 않습니다.") from exc
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("요청 본문 크기가 허용 범위를 벗어났습니다.")
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("올바른 UTF-8 JSON이 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("요청 본문은 JSON 객체여야 합니다.")
    return payload


class ManualControllerManager:
    """Create and resume verified manual Controller sessions."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, session_id: str) -> Path:
        if SESSION_ID_PATTERN.fullmatch(session_id) is None:
            raise ValueError("session_id 형식이 올바르지 않습니다.")
        candidate = (self.root / session_id).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Controller session 경로가 허용 범위를 벗어났습니다.") from exc
        return candidate

    def create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = str(payload.get("request") or "").strip()
        context = str(payload.get("context") or "").strip()
        route_hint = str(payload.get("route_hint") or "").strip()
        session_dir, state = SESSION.create_session(
            request,
            context=context,
            route_hint=route_hint,
            output_root=self.root,
        )
        return SESSION.public_session(state, session_dir=session_dir)

    def get(self, session_id: str) -> dict[str, Any]:
        session_dir = self._dir(session_id)
        state = SESSION.load_session(session_dir)
        return SESSION.public_session(state, session_dir=session_dir)

    def submit_result(self, session_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        session_dir = self._dir(session_id)
        raw_answer = str(payload.get("answer") or "").strip()
        state = SESSION.submit_action_result(session_dir, raw_answer)
        return SESSION.public_session(state, session_dir=session_dir)

    def submit_user_input(self, session_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        session_dir = self._dir(session_id)
        answer = str(payload.get("answer") or "").strip()
        state = SESSION.submit_user_input(session_dir, answer)
        return SESSION.public_session(state, session_dir=session_dir)


def install(web_module: Any) -> ManualControllerManager:
    """Install manual Controller endpoints on the current next-loop handler."""

    manager = ManualControllerManager(
        web_module.ROOT / "runs" / "manual-controller-sessions"
    )
    base_handler = web_module.NextLoopQualityRequestHandler

    class ManualControllerRequestHandler(base_handler):
        server_version = "PSOSManualControllerWeb/2"

        def do_GET(self) -> None:
            parts = urlparse(self.path).path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "manual-controller", "sessions"]:
                try:
                    self.send_json(manager.get(unquote(parts[3])))
                except FileNotFoundError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                except (ValueError, OSError, json.JSONDecodeError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            super().do_GET()

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/manual-controller/sessions":
                    self.send_json(manager.create(_read_json_body(self)), HTTPStatus.CREATED)
                    return
                parts = path.strip("/").split("/")
                if (
                    len(parts) == 5
                    and parts[:3] == ["api", "manual-controller", "sessions"]
                ):
                    session_id = unquote(parts[3])
                    action = parts[4]
                    payload = _read_json_body(self)
                    if action == "result":
                        self.send_json(manager.submit_result(session_id, payload))
                        return
                    if action == "input":
                        self.send_json(manager.submit_user_input(session_id, payload))
                        return
            except FileNotFoundError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                return
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            super().do_POST()

    web_module.NextLoopQualityRequestHandler = ManualControllerRequestHandler
    return manager
