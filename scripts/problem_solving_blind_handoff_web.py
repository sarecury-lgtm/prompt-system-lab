#!/usr/bin/env python3
"""Create a one-shot PSOS workbench -> PSOS Blind handoff ZIP."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import zipfile
from http import HTTPStatus
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import problem_solving_web_attachments as ATTACHMENTS


MAX_REQUEST_CHARS = 10_000
MAX_RESULT_CHARS = 30_000
MAX_MANUAL_TEXT_CHARS = 20_000
MAX_ATTACHMENT_FILES = 4
MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024


class BlindHandoffError(ValueError):
    """Raised when a Blind handoff cannot be created safely."""


def _text(value: Any, *, maximum: int, required: bool = False, label: str = "값") -> str:
    if value is None:
        cleaned = ""
    elif isinstance(value, str):
        cleaned = value.strip()
    else:
        raise BlindHandoffError(f"{label} 형식이 올바르지 않습니다.")
    if required and not cleaned:
        raise BlindHandoffError(f"{label}을 입력해 주세요.")
    if len(cleaned) > maximum:
        raise BlindHandoffError(f"{label}이 너무 깁니다.")
    return cleaned


def _manual_state(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise BlindHandoffError("수동 실행 상태 형식이 올바르지 않습니다.")
    result: dict[str, Any] = {}
    for key in ("request", "latest_answer", "latest_correction"):
        if key in value:
            result[key] = _text(
                value.get(key),
                maximum=MAX_MANUAL_TEXT_CHARS,
                label=f"수동 상태 {key}",
            )
    imported = value.get("imported")
    if imported is not None:
        if not isinstance(imported, Mapping):
            raise BlindHandoffError("수동 결과 상태 형식이 올바르지 않습니다.")
        envelope = imported.get("envelope")
        warnings = imported.get("warnings")
        result["imported"] = {
            "envelope": dict(envelope) if isinstance(envelope, Mapping) else None,
            "warnings": [
                str(item).strip()
                for item in warnings
                if str(item).strip()
            ][:12]
            if isinstance(warnings, list)
            else [],
        }
    return result


def _safe_attachment_paths(
    values: Any,
    *,
    attachment_root: Path,
) -> list[Path]:
    if values in (None, ""):
        return []
    if not isinstance(values, list):
        raise BlindHandoffError("첨부 경로 형식이 올바르지 않습니다.")
    if len(values) > MAX_ATTACHMENT_FILES:
        raise BlindHandoffError("handoff에는 첨부 이미지를 최대 4장까지 넣을 수 있습니다.")

    root = attachment_root.expanduser().resolve()
    paths: list[Path] = []
    total = 0
    for raw in values:
        if not isinstance(raw, str) or not raw.strip():
            raise BlindHandoffError("첨부 경로가 비어 있습니다.")
        path = Path(raw.strip()).expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BlindHandoffError("PSOS 첨부 폴더 밖의 파일은 handoff에 넣을 수 없습니다.") from exc
        if not path.is_file():
            raise BlindHandoffError(f"첨부 파일을 찾을 수 없습니다: {path.name}")
        size = path.stat().st_size
        total += size
        if total > MAX_ATTACHMENT_BYTES:
            raise BlindHandoffError("handoff 첨부 파일 전체 크기는 12MB 이하여야 합니다.")
        paths.append(path)
    return paths


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", value).strip(".-_")
    return cleaned[:80] or "attachment"


def _conversation_markdown(
    request: str,
    current_result: str,
    manual: Mapping[str, Any],
) -> str:
    sections = ["# PSOS handoff conversation", "", "## 원래 사용자 요청", "", request]
    latest_correction = str(manual.get("latest_correction") or "").strip()
    latest_answer = str(manual.get("latest_answer") or "").strip()
    if current_result:
        sections.extend(["", "## 작업실의 현재 결과", "", current_result])
    elif latest_answer:
        sections.extend(["", "## 마지막 ChatGPT 결과", "", latest_answer])
    if latest_correction:
        sections.extend(["", "## 사용자의 최신 교정", "", latest_correction])
    sections.extend(
        [
            "",
            "## 이어갈 때",
            "",
            "이 파일은 새 문제를 만드는 자료가 아니라 같은 작업을 이어가기 위한 스냅샷입니다. "
            "현재 ChatGPT 대화에서 사용자가 새로 말한 내용이 있으면 그 말을 가장 우선하세요.",
            "",
        ]
    )
    return "\n".join(sections)


def _state_markdown(
    *,
    request: str,
    route: str,
    run_id: str,
    current_result: str,
    manual: Mapping[str, Any],
    attachment_names: list[str],
    exported_at: str,
) -> str:
    lines = [
        "# Current Handoff State",
        "",
        "## 목적",
        "",
        request,
        "",
        "## 현재 위치",
        "",
        f"- exported_at: `{exported_at}`",
        f"- route: `{route or 'unknown'}`",
        f"- run_id: `{run_id or 'none'}`",
        f"- 작업실 결과 있음: {'yes' if current_result else 'no'}",
        f"- 사용자 최신 교정 있음: {'yes' if str(manual.get('latest_correction') or '').strip() else 'no'}",
    ]
    if attachment_names:
        lines.extend(["", "## 첨부", "", *[f"- `attachments/{name}`" for name in attachment_names]])
    lines.extend(
        [
            "",
            "## PSOS Blind가 지켜야 할 것",
            "",
            "- 이 상태를 새 작업으로 초기화하지 말고 같은 목적을 이어간다.",
            "- 현재 대화에서 사용자가 새로 정정한 내용이 ZIP보다 우선한다.",
            "- 부족한 정보가 실제 결론을 바꿀 때만 자연스럽게 질문한다.",
            "- 사용자에게 내부 packet, controller, receipt 구조를 설명하지 않는다.",
            "- 이 ZIP은 한 번의 인계용이다. 이후 같은 PSOS Blind 채팅에서는 다시 업로드할 필요가 없다.",
            "",
        ]
    )
    return "\n".join(lines)


def build_handoff_zip(
    payload: Mapping[str, Any],
    *,
    attachment_root: Path = ATTACHMENTS.ATTACHMENT_ROOT,
    now: dt.datetime | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    """Return ZIP bytes, a download filename, and the stored manifest."""

    if not isinstance(payload, Mapping):
        raise BlindHandoffError("handoff 요청 형식이 올바르지 않습니다.")
    request = _text(
        payload.get("request"),
        maximum=MAX_REQUEST_CHARS,
        required=True,
        label="사용자 요청",
    )
    current_result = _text(
        payload.get("current_result"),
        maximum=MAX_RESULT_CHARS,
        label="현재 결과",
    )
    route = _text(payload.get("route"), maximum=200, label="route")
    run_id = _text(payload.get("run_id"), maximum=200, label="run_id")
    manual = _manual_state(payload.get("manual_state"))
    attachment_paths = _safe_attachment_paths(
        payload.get("attachment_paths", []),
        attachment_root=attachment_root,
    )

    stamp = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    exported_at = stamp.isoformat()
    archive_names: list[str] = []
    used: set[str] = set()
    for index, path in enumerate(attachment_paths, 1):
        candidate = _slug(path.name)
        if not Path(candidate).suffix:
            candidate += path.suffix
        counter = 2
        base = Path(candidate)
        while candidate.casefold() in used:
            candidate = f"{base.stem}-{counter}{base.suffix}"
            counter += 1
        used.add(candidate.casefold())
        archive_names.append(candidate)

    manifest = {
        "version": 1,
        "kind": "psos_blind_handoff",
        "exported_at": exported_at,
        "source": "PSOS workbench",
        "current_request": request,
        "route": route or None,
        "run_id": run_id or None,
        "has_current_result": bool(current_result),
        "manual_state": manual,
        "attachments": [f"attachments/{name}" for name in archive_names],
        "continuation": {
            "mode": "same_task",
            "do_not_reset": True,
            "reupload_each_turn": False,
        },
    }

    start_here = """# 00 START HERE\n\n이 ZIP은 **PSOS 작업실에서 PSOS Blind로 같은 작업을 한 번 넘기기 위한 handoff**입니다.\n\n1. `STATE.md`, `conversation.md`, `manifest.json`을 읽으세요.\n2. ZIP 안의 원래 요청을 새 문제로 바꾸지 말고 현재 작업을 그대로 이어가세요.\n3. 이 채팅에서 사용자가 새로 말한 내용이나 정정이 있으면 ZIP보다 우선하세요.\n4. 답을 크게 바꾸는 정보가 부족할 때만 자연스럽게 질문하세요.\n5. 사용자는 이 ZIP을 매 턴 다시 올릴 필요가 없습니다. 이 대화에서 계속 이어가세요.\n6. 내부 PSOS 구조를 설명하거나 큰 schema를 출력하지 말고 실제 사용자 결과를 먼저 주세요.\n\nZIP만 올라오고 별도 사용자 요청이 없다면 `작업을 이어받았습니다. 지금 상태에서 계속할 내용을 말해주세요.` 정도로 짧게 응답하세요.\n"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        root = "psos-handoff"
        archive.writestr(f"{root}/00_START_HERE.md", start_here)
        archive.writestr(
            f"{root}/STATE.md",
            _state_markdown(
                request=request,
                route=route,
                run_id=run_id,
                current_result=current_result,
                manual=manual,
                attachment_names=archive_names,
                exported_at=exported_at,
            ),
        )
        archive.writestr(
            f"{root}/conversation.md",
            _conversation_markdown(request, current_result, manual),
        )
        archive.writestr(
            f"{root}/manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for path, archive_name in zip(attachment_paths, archive_names):
            archive.write(path, f"{root}/attachments/{archive_name}")

    filename = f"psos-blind-handoff-{stamp.strftime('%Y%m%d-%H%M%S')}.zip"
    return buffer.getvalue(), filename, manifest


def install(web_module: Any) -> None:
    """Install POST /api/blind-handoff on the current workbench handler."""

    handler_class = web_module.NextLoopQualityRequestHandler
    current = handler_class.do_POST
    if getattr(current, "_psos_blind_handoff_installed", False):
        return

    def do_POST(self: Any) -> None:
        if urlparse(self.path).path != "/api/blind-handoff":
            return current(self)
        try:
            payload = self.read_json_body()
            content, filename, _manifest = build_handoff_zip(payload)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
        except BlindHandoffError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            self.send_json(
                {"error": f"handoff ZIP을 만들지 못했습니다: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    do_POST._psos_blind_handoff_installed = True  # type: ignore[attr-defined]
    handler_class.do_POST = do_POST
