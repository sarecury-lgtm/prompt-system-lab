#!/usr/bin/env python3
"""Persist product-verification work exchanged with the user's Chrome session."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import problem_solving_live_browser as live_browser


RECEIPT_NAME = "connected-browser-verification.json"
RESULT_START = "<!-- PSOS_CONNECTED_BROWSER_START -->"
RESULT_END = "<!-- PSOS_CONNECTED_BROWSER_END -->"
TERMINAL_STATUSES = {"available", "sold_out", "unknown", "error"}
ALLOWED_STATUSES = TERMINAL_STATUSES | {"needs_user"}
MAX_TARGETS = 20
MAX_TEXT = 4_000
_LOCK = threading.RLock()


class ConnectedBrowserError(ValueError):
    """Raised when a browser queue or receipt is invalid."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConnectedBrowserError(f"검증 파일을 읽을 수 없습니다: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ConnectedBrowserError(f"검증 파일 형식이 올바르지 않습니다: {path.name}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _clean_text(value: Any, *, limit: int = MAX_TEXT) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _valid_url(value: Any) -> str:
    cleaned = _clean_text(value, limit=4_000)
    try:
        parsed = urlparse(cleaned)
    except ValueError as exc:
        raise ConnectedBrowserError("상품 URL 형식이 올바르지 않습니다.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConnectedBrowserError("상품 URL은 http 또는 https 주소여야 합니다.")
    return cleaned


def _target_id(url: str) -> str:
    return "page-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _queue_path(run_dir: Path) -> Path:
    return run_dir / RECEIPT_NAME


def load_queue(run_dir: Path) -> dict[str, Any]:
    path = _queue_path(run_dir)
    if not path.is_file():
        raise FileNotFoundError("연결된 Chrome 검증 작업이 아직 없습니다.")
    return _read_json(path)


def _verification_urls(run_dir: Path) -> list[str]:
    route = _read_json(run_dir / "route.json")
    result_path = run_dir / "result.md"
    result_markdown = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
    execution = {
        "result_markdown": result_markdown,
        "evidence": route.get("evidence", []),
    }
    return live_browser.verification_targets(execution, maximum=MAX_TARGETS)


def create_queue(run_dir: Path, *, reset: bool = False) -> dict[str, Any]:
    """Create or return the persistent queue for one PSOS run."""

    with _LOCK:
        path = _queue_path(run_dir)
        if path.is_file() and not reset:
            return load_queue(run_dir)
        urls = _verification_urls(run_dir)
        if not urls:
            raise ConnectedBrowserError("결과에서 검증할 상품 URL을 찾지 못했습니다.")
        now = utc_now()
        queue = {
            "version": 1,
            "kind": "connected_chrome_product_verification",
            "run_id": run_dir.name,
            "created_at": now,
            "updated_at": now,
            "state": "pending",
            "targets": [
                {
                    "id": _target_id(url),
                    "url": url,
                    "status": "pending",
                    "attempts": 0,
                    "receipt": None,
                }
                for url in urls
            ],
            "counts": {"total": len(urls), "completed": 0, "needs_user": 0},
            "revision": None,
        }
        _write_json(path, queue)
        return queue


def _normalized_receipt(target: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    status = _clean_text(payload.get("status"), limit=40)
    if status not in ALLOWED_STATUSES:
        raise ConnectedBrowserError("브라우저 검증 상태가 올바르지 않습니다.")
    payload_url = _valid_url(payload.get("url"))
    if payload_url != target["url"]:
        raise ConnectedBrowserError("대기열에 등록되지 않은 상품 URL입니다.")
    fields = payload.get("fields") if isinstance(payload.get("fields"), Mapping) else {}

    def string_items(key: str, maximum: int, limit: int) -> list[str]:
        raw = fields.get(key, [])
        if not isinstance(raw, list):
            return []
        return [_clean_text(item, limit=limit) for item in raw[:maximum] if _clean_text(item, limit=limit)]

    return {
        "url": payload_url,
        "final_url": _valid_url(payload.get("final_url") or payload_url),
        "status": status,
        "checked_at": _clean_text(payload.get("checked_at"), limit=80) or utc_now(),
        "signal": _clean_text(payload.get("signal"), limit=500),
        "excerpt": _clean_text(payload.get("excerpt")),
        "text_sha256": _clean_text(payload.get("text_sha256"), limit=128) or None,
        "fields": {
            "title": _clean_text(fields.get("title"), limit=500),
            "prices": string_items("prices", 20, 200),
            "shipping": string_items("shipping", 12, 500),
            "weights": string_items("weights", 20, 200),
            "selected_options": string_items("selected_options", 20, 500),
            "purchase_controls": string_items("purchase_controls", 12, 200),
        },
    }


def _refresh_state(queue: dict[str, Any]) -> None:
    statuses = [target["status"] for target in queue["targets"]]
    terminal = sum(status in TERMINAL_STATUSES for status in statuses)
    needs_user = sum(status == "needs_user" for status in statuses)
    if terminal == len(statuses):
        state = "completed"
    elif needs_user:
        state = "needs_user"
    else:
        state = "pending"
    queue["state"] = state
    queue["counts"] = {
        "total": len(statuses),
        "completed": terminal,
        "needs_user": needs_user,
        "available": sum(status == "available" for status in statuses),
        "sold_out": sum(status == "sold_out" for status in statuses),
        "unknown": sum(status in {"unknown", "error"} for status in statuses),
    }
    queue["updated_at"] = utc_now()


def submit_receipt(
    run_dir: Path,
    target_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Store one Chrome observation and finalize the run when all targets are terminal."""

    with _LOCK:
        queue = load_queue(run_dir)
        target = next((item for item in queue["targets"] if item.get("id") == target_id), None)
        if target is None:
            raise ConnectedBrowserError("대기열에 없는 검증 항목입니다.")
        receipt = _normalized_receipt(target, payload)
        target["status"] = receipt["status"]
        target["attempts"] = int(target.get("attempts", 0)) + 1
        target["receipt"] = receipt
        _refresh_state(queue)
        _write_json(_queue_path(run_dir), queue)
        if queue["state"] == "completed":
            apply_completed_queue(run_dir, queue)
        return queue


def _strip_previous_section(markdown: str) -> str:
    pattern = re.compile(
        re.escape(RESULT_START) + r".*?" + re.escape(RESULT_END) + r"\s*",
        re.DOTALL,
    )
    return pattern.sub("", markdown).strip()


def _receipt_rows(queue: Mapping[str, Any]) -> list[str]:
    rows = [
        RESULT_START,
        "## 사용자 Chrome 실시간 검증",
        "",
        "이 표는 검색 결과나 AI의 설명보다 우선합니다.",
        "",
        "| 상태 | 상품 | 현재 화면에서 확인한 정보 | 확인 시각 |",
        "|---|---|---|---|",
    ]
    for target in queue["targets"]:
        receipt = target.get("receipt") or {}
        fields = receipt.get("fields") or {}
        details = "; ".join(
            item
            for item in [
                fields.get("title"),
                ", ".join(fields.get("prices") or [])[:300],
                ", ".join(fields.get("shipping") or [])[:300],
                receipt.get("signal"),
            ]
            if item
        )
        rows.append(
            f"| {target['status']} | [{target['url']}]({target['url']}) | "
            f"{details.replace('|', ' / ')} | {receipt.get('checked_at', '')} |"
        )
    rows.append(RESULT_END)
    return rows


def apply_completed_queue(run_dir: Path, queue: Mapping[str, Any]) -> None:
    """Anchor connected-browser receipts in the parent run and make them authoritative."""

    route_path = run_dir / "route.json"
    route = _read_json(route_path)
    result_path = run_dir / "result.md"
    existing = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
    clean = _strip_previous_section(existing)
    result_path.write_text("\n".join(_receipt_rows(queue)) + "\n\n" + clean + "\n", encoding="utf-8")

    evidence = [
        item
        for item in route.get("evidence", [])
        if not (
            isinstance(item, Mapping)
            and item.get("source") == RECEIPT_NAME
            and str(item.get("finding", "")).startswith("[CONNECTED_BROWSER]")
        )
    ]
    for target in queue["targets"]:
        receipt = target.get("receipt") or {}
        evidence.append(
            {
                "source": RECEIPT_NAME,
                "finding": (
                    f"[CONNECTED_BROWSER] url={target['url']} status={target['status']} "
                    f"checked_at={receipt.get('checked_at', '')} signal={receipt.get('signal', '')}"
                ),
                "kind": "receipt",
            }
        )
    route["evidence"] = evidence
    invalid = [target for target in queue["targets"] if target["status"] != "available"]
    limitations = list(route.get("limitations", []))
    prefix = "사용자 Chrome 검증 미통과:"
    limitations = [item for item in limitations if not str(item).startswith(prefix)]
    if invalid:
        limitations.append(
            prefix + " " + "; ".join(f"{item['url']}={item['status']}" for item in invalid)
        )
        route["execution_status"] = "partial"
    route["limitations"] = limitations
    digest = hashlib.sha256(_queue_path(run_dir).read_bytes()).hexdigest()
    record = {
        "path": RECEIPT_NAME,
        "sha256": digest,
        "status": queue["state"],
        "updated_at": queue["updated_at"],
        "counts": dict(queue["counts"]),
    }
    route["connected_browser_verification"] = record
    if isinstance(route.get("run"), dict):
        route["run"]["connected_browser_verification"] = record
    _write_json(route_path, route)


def build_revision_request(run_dir: Path, queue: Mapping[str, Any]) -> str:
    relative = f"runs/{run_dir.name}/{RECEIPT_NAME}"
    available = queue.get("counts", {}).get("available", 0)
    return f"""원본 실행 {run_dir.name}의 상품 추천을 사용자 Chrome 실시간 검증 결과로 다시 완성하세요.

신뢰할 검증 영수증: {relative}

- 영수증의 available만 현재 구매 가능한 후보로 인정합니다.
- sold_out, unknown, error는 최종 추천 후보에서 제외합니다.
- 각 후보의 표시 가격, 선택 옵션, 중량, 배송비를 다시 계산하고 확인되지 않은 값은 추정하지 않습니다.
- 현재 유효 후보는 {available}개입니다. 요청의 후보 수나 완료 조건에 부족하면 웹에서 다른 판매처를 넓게 찾아 보충합니다.
- 검색 문구를 길게 설명하는 대신 검증 가능한 후보를 수집하고, 비교 후보와 최종 선택을 분명히 제시합니다.
- 원본 실행의 잘못된 판매 상태나 가격 주장을 그대로 복사하지 않습니다.
"""


def record_revision(run_dir: Path, job: Mapping[str, Any]) -> dict[str, Any]:
    with _LOCK:
        queue = load_queue(run_dir)
        record = {
            "job_id": job.get("job_id"),
            "child_run_id": job.get("run_id"),
            "state": job.get("state"),
            "submitted_at": utc_now(),
        }
        queue["revision"] = record
        queue["updated_at"] = utc_now()
        _write_json(_queue_path(run_dir), queue)
        route = _read_json(run_dir / "route.json")
        verification = route.get("connected_browser_verification")
        if isinstance(verification, dict):
            verification["sha256"] = hashlib.sha256(_queue_path(run_dir).read_bytes()).hexdigest()
            verification["updated_at"] = queue["updated_at"]
        route["connected_browser_revision"] = record
        if isinstance(route.get("run"), dict):
            route["run"]["connected_browser_revision"] = record
        _write_json(run_dir / "route.json", route)
        return queue
