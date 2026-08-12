#!/usr/bin/env python3
"""Local screenshot upload support for the PSOS browser UI."""

from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT_ROOT = ROOT / "runs" / "web-attachments"
MAX_FILES = 4
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 12 * 1024 * 1024
MAX_BODY_BYTES = 18 * 1024 * 1024
ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class AttachmentError(ValueError):
    """Raised when a local upload is unsafe or malformed."""


def _safe_name(name: str, suffix: str, index: int) -> str:
    base = Path(str(name or "")).name
    stem = Path(base).stem
    stem = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", stem).strip(".-_")
    if not stem:
        stem = f"image-{index}"
    return f"{stem[:80]}{suffix}"


def _valid_magic(mime: str, data: bytes) -> bool:
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return False


def _decode_item(item: Any, index: int) -> tuple[str, str, bytes]:
    if not isinstance(item, Mapping):
        raise AttachmentError("첨부 파일 형식이 올바르지 않습니다.")
    name = item.get("name")
    mime = item.get("type")
    data_url = item.get("data_url")
    if not isinstance(name, str) or not isinstance(mime, str) or not isinstance(data_url, str):
        raise AttachmentError("첨부 파일 이름, 형식, 내용이 필요합니다.")
    if mime not in ALLOWED_MIME:
        raise AttachmentError("PNG, JPG, WEBP 이미지만 첨부할 수 있습니다.")
    prefix = f"data:{mime};base64,"
    if not data_url.startswith(prefix):
        raise AttachmentError("첨부 이미지 인코딩이 올바르지 않습니다.")
    try:
        data = base64.b64decode(data_url[len(prefix) :], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AttachmentError("첨부 이미지 데이터를 읽지 못했습니다.") from exc
    if not data:
        raise AttachmentError("빈 이미지는 첨부할 수 없습니다.")
    if len(data) > MAX_FILE_BYTES:
        raise AttachmentError("이미지 한 장은 5MB 이하여야 합니다.")
    if not _valid_magic(mime, data):
        raise AttachmentError("파일 확장자와 실제 이미지 형식이 맞지 않습니다.")
    return _safe_name(name, ALLOWED_MIME[mime], index), mime, data


def store_attachments(
    payload: Any,
    *,
    root: Path = ATTACHMENT_ROOT,
) -> list[dict[str, str]]:
    if not isinstance(payload, Mapping):
        raise AttachmentError("첨부 요청 형식이 올바르지 않습니다.")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise AttachmentError("첨부할 이미지를 선택해 주세요.")
    if len(files) > MAX_FILES:
        raise AttachmentError("이미지는 한 번에 최대 4장까지 첨부할 수 있습니다.")

    decoded = [_decode_item(item, index) for index, item in enumerate(files, 1)]
    if sum(len(data) for _name, _mime, data in decoded) > MAX_TOTAL_BYTES:
        raise AttachmentError("첨부 이미지 전체 크기는 12MB 이하여야 합니다.")

    bundle = root.expanduser().resolve() / f"upload-{uuid.uuid4().hex[:16]}"
    bundle.mkdir(parents=True, exist_ok=False)
    result: list[dict[str, str]] = []
    used: set[str] = set()
    try:
        for index, (name, mime, data) in enumerate(decoded, 1):
            candidate = name
            counter = 2
            while candidate.casefold() in used:
                path = Path(name)
                candidate = f"{path.stem}-{counter}{path.suffix}"
                counter += 1
            used.add(candidate.casefold())
            path = bundle / candidate
            path.write_bytes(data)
            result.append(
                {
                    "name": candidate,
                    "type": mime,
                    "path": str(path.resolve()),
                }
            )
        (bundle / "manifest.json").write_text(
            json.dumps({"attachments": result}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result
    except Exception:
        shutil.rmtree(bundle, ignore_errors=True)
        raise


def _read_upload_body(handler: Any) -> Any:
    raw_length = handler.headers.get("Content-Length")
    try:
        length = int(raw_length or "0")
    except ValueError as exc:
        raise AttachmentError("첨부 요청 크기를 확인할 수 없습니다.") from exc
    if length <= 0:
        raise AttachmentError("첨부 요청이 비어 있습니다.")
    if length > MAX_BODY_BYTES:
        raise AttachmentError("첨부 요청 전체 크기가 너무 큽니다.")
    content_type = handler.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        raise AttachmentError("첨부 요청은 JSON 형식이어야 합니다.")
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttachmentError("첨부 요청 JSON을 읽지 못했습니다.") from exc


def install(web_module: Any) -> None:
    """Install the upload endpoint on the next-loop request handler once."""

    handler_class = web_module.NextLoopQualityRequestHandler
    current = handler_class.do_POST
    if getattr(current, "_psos_attachments_installed", False):
        return

    def do_POST(self: Any) -> None:
        if urlparse(self.path).path != "/api/attachments":
            return current(self)
        try:
            attachments = store_attachments(_read_upload_body(self))
            self.send_json({"attachments": attachments}, HTTPStatus.CREATED)
        except AttachmentError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            self.send_json(
                {"error": f"첨부 이미지를 저장하지 못했습니다: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    do_POST._psos_attachments_installed = True  # type: ignore[attr-defined]
    handler_class.do_POST = do_POST
