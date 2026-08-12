#!/usr/bin/env python3
"""Apply ChatGPT-produced full-file changes through an explicit local approval."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


MAX_BODY_BYTES = 2_500_000
MAX_FILES = 20
MAX_FILE_CHARS = 750_000
MAX_TOTAL_CHARS = 2_000_000
APPROVAL_MINUTES = 10
DISALLOWED_ROOTS = {".git", "runs"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _clean_relative_path(root: Path, value: Any) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("변경 파일 경로가 필요합니다.")
    text = value.strip().replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"허용할 수 없는 파일 경로입니다: {text}")
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts or parts[0].lower() in DISALLOWED_ROOTS:
        raise ValueError(f"보호된 경로는 변경할 수 없습니다: {text}")
    relative = Path(*parts).as_posix()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"작업 공간 밖의 파일은 변경할 수 없습니다: {text}") from exc
    return relative, resolved


def _normalize_scopes(root: Path, values: Any) -> list[str]:
    if isinstance(values, str):
        source = values.splitlines()
    elif isinstance(values, list):
        source = values
    else:
        raise ValueError("허용 경로 형식이 올바르지 않습니다.")
    scopes: list[str] = []
    for value in source:
        relative, _ = _clean_relative_path(root, value)
        if relative not in scopes:
            scopes.append(relative)
    if not scopes:
        raise ValueError("변경을 허용할 파일 또는 폴더를 한 개 이상 입력해 주세요.")
    return scopes


def _within_scope(path: str, scopes: list[str]) -> bool:
    return any(path == scope or path.startswith(f"{scope.rstrip('/')}/") for scope in scopes)


def _normalize_operations(root: Path, values: Any, scopes: list[str]) -> list[dict[str, Any]]:
    if not isinstance(values, list) or not values:
        raise ValueError("적용할 파일 변경안이 없습니다.")
    if len(values) > MAX_FILES:
        raise ValueError(f"한 번에 변경할 수 있는 파일은 {MAX_FILES}개 이하입니다.")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for item in values:
        if not isinstance(item, Mapping):
            raise ValueError("파일 변경안은 객체 배열이어야 합니다.")
        action = str(item.get("action") or "").strip().lower()
        if action not in {"create", "replace"}:
            raise ValueError("수동 파일 변경은 create와 replace만 지원합니다. 삭제는 지원하지 않습니다.")
        relative, target = _clean_relative_path(root, item.get("path"))
        if relative in seen:
            raise ValueError(f"같은 파일을 두 번 변경할 수 없습니다: {relative}")
        if not _within_scope(relative, scopes):
            raise ValueError(f"허용 경로 밖의 변경입니다: {relative}")
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError(f"파일 내용은 문자열이어야 합니다: {relative}")
        if len(content) > MAX_FILE_CHARS:
            raise ValueError(f"파일 하나의 크기가 너무 큽니다: {relative}")
        total += len(content)
        if total > MAX_TOTAL_CHARS:
            raise ValueError("전체 변경 내용이 허용 크기를 초과했습니다.")
        if action == "create" and target.exists():
            raise ValueError(f"이미 존재하는 파일은 create할 수 없습니다: {relative}")
        if action == "replace" and not target.is_file():
            raise ValueError(f"교체할 기존 파일을 찾을 수 없습니다: {relative}")
        seen.add(relative)
        output.append({"action": action, "path": relative, "content": content})
    return output


def _parse_command(command: Any) -> list[str]:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("검사 명령은 비어 있을 수 없습니다.")
    text = command.strip()
    if any(token in text for token in ("&&", "||", ">", "<", ";", "|")):
        raise ValueError(f"셸 연산자는 사용할 수 없습니다: {text}")
    argv = shlex.split(text, posix=os.name != "nt")
    if not argv:
        raise ValueError("검사 명령이 비어 있습니다.")
    executable = Path(argv[0]).name.lower()
    if executable in {"python", "python.exe", "py", "py.exe"}:
        if len(argv) < 3 or argv[1:3] not in (["-m", "py_compile"], ["-m", "unittest"]):
            raise ValueError("Python 검사는 'python -m py_compile' 또는 'python -m unittest'만 허용합니다.")
    elif executable in {"node", "node.exe"}:
        if len(argv) != 3 or argv[1] != "--check":
            raise ValueError("Node 검사는 'node --check <파일>'만 허용합니다.")
    else:
        raise ValueError("검사 명령은 Python 또는 Node 문법·테스트 명령만 허용합니다.")
    return argv


def _normalize_commands(values: Any, operations: list[dict[str, Any]]) -> list[list[str]]:
    if values in (None, "", []):
        values = []
    if isinstance(values, str):
        source = [line for line in values.splitlines() if line.strip()]
    elif isinstance(values, list):
        source = values
    else:
        raise ValueError("검사 명령 형식이 올바르지 않습니다.")
    commands = [_parse_command(value) for value in source]
    if commands:
        return commands
    for item in operations:
        path = item["path"]
        if path.endswith(".py"):
            commands.append([sys.executable, "-m", "py_compile", path])
        elif path.endswith((".js", ".mjs", ".cjs")):
            commands.append(["node", "--check", path])
    return commands


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "patch_id",
            "status",
            "request",
            "allowed_write_paths",
            "operations_preview",
            "test_commands",
            "created_at",
            "expires_at",
            "executed_at",
            "receipt",
            "rollback",
            "error",
        )
    }


class ManualPatchManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _expire(self, record: dict[str, Any]) -> None:
        if record["status"] == "pending" and dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(record["expires_at"]):
            record["status"] = "expired"

    def preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = str(payload.get("request") or "").strip()
        scopes = _normalize_scopes(self.root, payload.get("allowed_write_paths"))
        operations = _normalize_operations(self.root, payload.get("operations"), scopes)
        commands = _normalize_commands(payload.get("test_commands"), operations)
        snapshots: dict[str, dict[str, Any]] = {}
        preview: list[dict[str, Any]] = []
        for item in operations:
            target = self.root / item["path"]
            before = target.read_bytes() if target.is_file() else None
            snapshots[item["path"]] = {
                "exists": before is not None,
                "sha256": sha256_bytes(before) if before is not None else None,
            }
            preview.append({
                "action": item["action"],
                "path": item["path"],
                "before_sha256": snapshots[item["path"]]["sha256"],
                "after_sha256": sha256_bytes(item["content"].encode("utf-8")),
                "characters": len(item["content"]),
            })
        created = dt.datetime.now(dt.timezone.utc)
        record = {
            "patch_id": f"manual-patch-{uuid.uuid4().hex[:16]}",
            "status": "pending",
            "request": request,
            "allowed_write_paths": scopes,
            "operations": operations,
            "operations_preview": preview,
            "snapshots": snapshots,
            "test_argv": commands,
            "test_commands": [shlex.join(command) for command in commands],
            "created_at": created.isoformat(),
            "expires_at": (created + dt.timedelta(minutes=APPROVAL_MINUTES)).isoformat(),
            "executed_at": None,
            "receipt": None,
            "rollback": None,
            "error": None,
        }
        with self._lock:
            self._records[record["patch_id"]] = record
        return _public_record(record)

    def get(self, patch_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(patch_id)
            if record is None:
                return None
            self._expire(record)
            return _public_record(record)

    def cancel(self, patch_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(patch_id)
            if record is None:
                raise KeyError("파일 변경 검토를 찾을 수 없습니다.")
            self._expire(record)
            if record["status"] != "pending":
                raise ValueError(f"취소할 수 없는 상태입니다: {record['status']}")
            record["status"] = "cancelled"
            return _public_record(record)

    def _assert_unchanged(self, record: Mapping[str, Any]) -> None:
        for path, snapshot in record["snapshots"].items():
            target = self.root / path
            current = target.read_bytes() if target.is_file() else None
            current_hash = sha256_bytes(current) if current is not None else None
            if bool(current is not None) != bool(snapshot["exists"]) or current_hash != snapshot["sha256"]:
                raise ValueError(f"검토 이후 파일이 달라져 적용을 중단했습니다: {path}")

    def execute(self, patch_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(patch_id)
            if record is None:
                raise KeyError("파일 변경 검토를 찾을 수 없습니다.")
            self._expire(record)
            if record["status"] != "pending":
                raise ValueError(f"적용할 수 없는 상태입니다: {record['status']}")
            record["status"] = "applying"
        backups: dict[str, bytes | None] = {}
        changed: list[str] = []
        tests: list[dict[str, Any]] = []
        try:
            self._assert_unchanged(record)
            for item in record["operations"]:
                target = self.root / item["path"]
                backups[item["path"]] = target.read_bytes() if target.is_file() else None
                target.parent.mkdir(parents=True, exist_ok=True)
                encoded = item["content"].encode("utf-8")
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    handle.write(encoded)
                    temp_path = Path(handle.name)
                temp_path.replace(target)
                changed.append(item["path"])
            for argv in record["test_argv"]:
                completed = subprocess.run(
                    argv,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    shell=False,
                )
                result = {
                    "command": shlex.join(argv),
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-6000:],
                    "stderr": completed.stderr[-6000:],
                }
                tests.append(result)
                if completed.returncode != 0:
                    raise RuntimeError(f"검사 실패: {result['command']}")
            receipt = {
                "version": 1,
                "patch_id": patch_id,
                "verified": True,
                "actual_changes": {
                    "created": [item["path"] for item in record["operations"] if item["action"] == "create"],
                    "modified": [item["path"] for item in record["operations"] if item["action"] == "replace"],
                },
                "tests": tests,
                "completed_at": utc_now(),
            }
            with self._lock:
                record["status"] = "completed"
                record["executed_at"] = utc_now()
                record["receipt"] = receipt
            return _public_record(record)
        except Exception as exc:
            rollback_issues: list[str] = []
            for path in reversed(changed):
                target = self.root / path
                before = backups[path]
                try:
                    if before is None:
                        target.unlink(missing_ok=True)
                    else:
                        target.write_bytes(before)
                except OSError as rollback_exc:
                    rollback_issues.append(f"{path}: {rollback_exc}")
            rollback = {
                "version": 1,
                "patch_id": patch_id,
                "restored": not rollback_issues,
                "reverted_changes": {
                    "created": [path for path, before in backups.items() if before is None],
                    "modified": [path for path, before in backups.items() if before is not None],
                },
                "tests": tests,
                "issues": rollback_issues,
                "completed_at": utc_now(),
            }
            with self._lock:
                record["status"] = "rolled_back" if not rollback_issues else "rollback_failed"
                record["executed_at"] = utc_now()
                record["rollback"] = rollback
                record["error"] = str(exc).strip() or exc.__class__.__name__
            return _public_record(record)


def _read_json_body(handler: Any) -> dict[str, Any]:
    if handler.headers.get_content_type() != "application/json":
        raise ValueError("Content-Type은 application/json이어야 합니다.")
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ValueError("Content-Length가 올바르지 않습니다.") from exc
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("파일 변경 본문 크기가 허용 범위를 벗어났습니다.")
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("올바른 UTF-8 JSON이 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("요청 본문은 JSON 객체여야 합니다.")
    return payload


def install(web_module: Any) -> ManualPatchManager:
    """Install manual-patch endpoints on the next-loop HTTP handler."""

    manager = ManualPatchManager(web_module.ROOT)
    base_handler = web_module.NextLoopQualityRequestHandler

    class ManualPatchRequestHandler(base_handler):
        server_version = "PSOSManualPatchWeb/1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path.startswith("/api/manual-patches/"):
                patch_id = path.removeprefix("/api/manual-patches/")
                record = manager.get(patch_id)
                if record is None:
                    self.send_json({"error": "파일 변경 검토를 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
                else:
                    self.send_json(record)
                return
            super().do_GET()

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/manual-patches/preview":
                    self.send_json(manager.preview(_read_json_body(self)), HTTPStatus.CREATED)
                    return
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "manual-patches"]:
                    patch_id, action = parts[2], parts[3]
                    if action == "execute":
                        self.send_json(manager.execute(patch_id))
                        return
                    if action == "cancel":
                        self.send_json(manager.cancel(patch_id))
                        return
            except KeyError as exc:
                self.send_json({"error": str(exc.args[0])}, HTTPStatus.NOT_FOUND)
                return
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self.send_json({"error": str(exc).strip() or exc.__class__.__name__}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            super().do_POST()

    web_module.NextLoopQualityRequestHandler = ManualPatchRequestHandler
    return manager
