#!/usr/bin/env python3
"""Safely archive selected external images inside a PSOS run directory."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_REDIRECTS = 4
DOWNLOAD_TIMEOUT = 12
ALLOWED_MEDIA_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}


class VisualArchiveError(ValueError):
    """Raised when an external image cannot be archived safely."""


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        redirect_count = int(getattr(req, "_psos_redirect_count", 0)) + 1
        if redirect_count > MAX_REDIRECTS:
            raise VisualArchiveError("이미지 리다이렉트 횟수가 허용 범위를 넘었습니다.")
        target = urljoin(req.full_url, newurl)
        validate_public_http_url(target)
        redirected = super().redirect_request(req, fp, code, msg, headers, target)
        if redirected is not None:
            setattr(redirected, "_psos_redirect_count", redirect_count)
        return redirected


def _clean_error(exc: BaseException) -> str:
    text = " ".join(str(exc).split()).strip() or exc.__class__.__name__
    return text[:300]


def _resolved_addresses(hostname: str, port: int) -> set[str]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise VisualArchiveError("이미지 호스트 주소를 확인할 수 없습니다.") from exc
    addresses = {str(record[4][0]).split("%", 1)[0] for record in records}
    if not addresses:
        raise VisualArchiveError("이미지 호스트 주소가 비어 있습니다.")
    return addresses


def validate_public_http_url(url: str) -> str:
    """Reject credentials and hosts that resolve to non-public address space."""

    if not isinstance(url, str) or not url.strip():
        raise VisualArchiveError("이미지 URL이 비어 있습니다.")
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise VisualArchiveError("이미지는 http 또는 https URL이어야 합니다.")
    if parsed.username is not None or parsed.password is not None:
        raise VisualArchiveError("이미지 URL에는 인증 정보를 넣을 수 없습니다.")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise VisualArchiveError("로컬 호스트의 이미지는 외부 보존 대상으로 사용할 수 없습니다.")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = {str(literal)}
    except ValueError:
        addresses = _resolved_addresses(hostname, port)
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise VisualArchiveError("이미지 호스트 주소 형식이 올바르지 않습니다.") from exc
        if not ip.is_global:
            raise VisualArchiveError("사설·로컬·예약 주소의 이미지는 내려받지 않습니다.")
    return parsed.geturl()


def _detect_media_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if len(content) >= 16 and content[4:8] == b"ftyp":
        brands = content[8:40]
        if b"avif" in brands or b"avis" in brands:
            return "image/avif"
    return None


def _read_limited(response: Any, limit: int) -> bytes:
    length = response.headers.get("Content-Length")
    if length:
        try:
            if int(length) > limit:
                raise VisualArchiveError("이미지 크기가 허용 한도를 초과합니다.")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise VisualArchiveError("이미지 크기가 허용 한도를 초과합니다.")
        chunks.append(chunk)
    if not chunks:
        raise VisualArchiveError("이미지 응답이 비어 있습니다.")
    return b"".join(chunks)


def download_image(url: str, max_bytes: int) -> dict[str, Any]:
    """Download one public image without cookies or authentication headers."""

    safe_url = validate_public_http_url(url)
    opener = build_opener(_SafeRedirectHandler())
    request = Request(
        safe_url,
        headers={
            "User-Agent": "PSOS-Visual-Evidence/1.0",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9,*/*;q=0.1",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=DOWNLOAD_TIMEOUT) as response:
            final_url = validate_public_http_url(response.geturl())
            header_media = str(response.headers.get_content_type()).lower()
            content = _read_limited(response, min(MAX_IMAGE_BYTES, max_bytes))
    except VisualArchiveError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise VisualArchiveError(f"이미지를 내려받지 못했습니다: {_clean_error(exc)}") from exc

    detected_media = _detect_media_type(content)
    if detected_media is None:
        raise VisualArchiveError("응답 내용이 지원하는 이미지 형식이 아닙니다.")
    if header_media not in ALLOWED_MEDIA_TYPES:
        raise VisualArchiveError("응답 MIME이 허용된 이미지 형식이 아닙니다.")
    if header_media != detected_media:
        raise VisualArchiveError("응답 MIME과 실제 이미지 형식이 일치하지 않습니다.")
    return {
        "content": content,
        "media_type": detected_media,
        "final_url": final_url,
    }


def _atomic_write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
    try:
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def archive_selected_images(
    run_dir: Path,
    images: list[Mapping[str, Any]],
    *,
    downloader: Callable[[str, int], Mapping[str, Any]] = download_image,
) -> dict[str, dict[str, Any]]:
    """Best-effort archive keyed by original URL; failures remain explicit."""

    run_dir = run_dir.expanduser().resolve()
    archive_dir = run_dir / "evidence" / "images"
    remaining = MAX_TOTAL_BYTES
    results: dict[str, dict[str, Any]] = {}
    for image in images:
        source = str(image.get("src") or "")
        if source in results:
            continue
        if remaining <= 0:
            results[source] = {
                "status": "unavailable",
                "path": None,
                "sha256": None,
                "media_type": None,
                "byte_count": None,
                "final_url": None,
                "error": "이번 가져오기의 전체 이미지 용량 한도를 초과했습니다.",
            }
            continue
        try:
            downloaded = downloader(source, remaining)
            content = downloaded.get("content")
            media_type = downloaded.get("media_type")
            final_url = downloaded.get("final_url")
            if not isinstance(content, bytes) or not content:
                raise VisualArchiveError("다운로더가 이미지 바이트를 반환하지 않았습니다.")
            if media_type not in ALLOWED_MEDIA_TYPES:
                raise VisualArchiveError("다운로더가 지원하지 않는 이미지 MIME을 반환했습니다.")
            if len(content) > min(MAX_IMAGE_BYTES, remaining):
                raise VisualArchiveError("이미지 크기가 허용 한도를 초과합니다.")
            digest = hashlib.sha256(content).hexdigest()
            extension = ALLOWED_MEDIA_TYPES[str(media_type)]
            relative_path = Path("evidence") / "images" / f"{digest}{extension}"
            target = run_dir / relative_path
            if target.is_symlink():
                raise VisualArchiveError("이미지 보존 경로가 심볼릭 링크입니다.")
            if not target.is_file():
                _atomic_write(target, content)
            remaining -= len(content)
            results[source] = {
                "status": "archived",
                "path": relative_path.as_posix(),
                "sha256": digest,
                "media_type": media_type,
                "byte_count": len(content),
                "final_url": str(final_url or source),
                "error": None,
            }
        except (VisualArchiveError, OSError) as exc:
            results[source] = {
                "status": "unavailable",
                "path": None,
                "sha256": None,
                "media_type": None,
                "byte_count": None,
                "final_url": None,
                "error": _clean_error(exc),
            }
    return results
