#!/usr/bin/env python3
"""Validate evidence decisions and prepare immutable-source PSOS revisions."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping


ALLOWED_DECISIONS = ["keep", "question", "exclude"]
DECISION_VALUES = {"unreviewed", *ALLOWED_DECISIONS}
MAX_ITEM_NOTE = 500
MAX_REVIEWER_NOTE = 2000


class EvidenceReviewError(ValueError):
    """Raised when an evidence review is stale, incomplete, or malformed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Any) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return path


def _atomic_text(path: Path, content: str) -> Path:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
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
        if temp_path.exists():
            temp_path.unlink()
    return path


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceReviewError(f"{label}을 찾을 수 없습니다.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceReviewError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceReviewError(f"{label}은 JSON 객체여야 합니다.")
    return payload


def load_bundle(run_dir: Path) -> tuple[dict[str, Any], str]:
    run_dir = run_dir.expanduser().resolve()
    path = run_dir / "evidence_bundle.json"
    bundle = _read_object(path, "Evidence Bundle")
    items = bundle.get("items")
    if not isinstance(items, list):
        raise EvidenceReviewError("Evidence Bundle items가 올바르지 않습니다.")
    item_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise EvidenceReviewError("Evidence Bundle item이 객체가 아닙니다.")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip() or item_id in item_ids:
            raise EvidenceReviewError("Evidence Bundle item ID가 올바르지 않습니다.")
        item_ids.add(item_id)
    return bundle, sha256_file(path)


def _reviewable_items(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in bundle.get("items", [])
        if isinstance(item, Mapping) and item.get("reviewable") is True
    ]


def _clean_note(value: Any, *, limit: int, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise EvidenceReviewError(f"{label}는 문자열이어야 합니다.")
    cleaned = value.strip()
    if len(cleaned) > limit:
        raise EvidenceReviewError(f"{label}는 {limit}자 이하여야 합니다.")
    return cleaned


def _normalize_decisions(
    bundle: Mapping[str, Any],
    decisions: Any,
    *,
    require_complete_set: bool,
) -> list[dict[str, str]]:
    if not isinstance(decisions, list):
        raise EvidenceReviewError("decisions는 배열이어야 합니다.")
    reviewable = _reviewable_items(bundle)
    expected_ids = [item["id"] for item in reviewable]
    expected_set = set(expected_ids)
    normalized_by_id: dict[str, dict[str, str]] = {}
    for raw in decisions:
        if not isinstance(raw, Mapping) or set(raw) != {
            "evidence_id",
            "decision",
            "note",
        }:
            raise EvidenceReviewError("evidence decision 필드가 올바르지 않습니다.")
        evidence_id = raw.get("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id not in expected_set:
            raise EvidenceReviewError("검토할 수 없는 evidence ID가 포함됐습니다.")
        if evidence_id in normalized_by_id:
            raise EvidenceReviewError("같은 evidence ID의 판정이 중복됐습니다.")
        decision = raw.get("decision")
        if decision not in DECISION_VALUES:
            raise EvidenceReviewError("지원하지 않는 evidence 판정입니다.")
        normalized_by_id[evidence_id] = {
            "evidence_id": evidence_id,
            "decision": str(decision),
            "note": _clean_note(
                raw.get("note"),
                limit=MAX_ITEM_NOTE,
                label="evidence note",
            ),
        }
    if require_complete_set and set(normalized_by_id) != expected_set:
        raise EvidenceReviewError("모든 검토 가능 evidence의 판정을 함께 보내야 합니다.")
    return [
        normalized_by_id.get(
            evidence_id,
            {"evidence_id": evidence_id, "decision": "unreviewed", "note": ""},
        )
        for evidence_id in expected_ids
    ]


def review_status(decisions: list[Mapping[str, Any]]) -> str:
    reviewed = sum(1 for item in decisions if item.get("decision") != "unreviewed")
    if reviewed == 0:
        return "pending"
    if reviewed == len(decisions):
        return "completed"
    return "partial"


def empty_review(bundle: Mapping[str, Any], bundle_sha256: str) -> dict[str, Any]:
    decisions = [
        {"evidence_id": item["id"], "decision": "unreviewed", "note": ""}
        for item in _reviewable_items(bundle)
    ]
    return {
        "version": 1,
        "bundle_sha256": bundle_sha256,
        "allowed_decisions": ALLOWED_DECISIONS,
        "review_status": "pending",
        "reviewer_note": "",
        "updated_at": None,
        "decisions": decisions,
    }


def load_review(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    bundle, bundle_sha = load_bundle(run_dir)
    path = run_dir / "evidence_review.json"
    if not path.is_file():
        return empty_review(bundle, bundle_sha)
    payload = _read_object(path, "Evidence Review")
    if payload.get("bundle_sha256") != bundle_sha:
        raise EvidenceReviewError(
            "Evidence Review가 현재 bundle과 일치하지 않습니다. 새로 검토해 주세요."
        )
    decisions = _normalize_decisions(
        bundle,
        payload.get("decisions", []),
        require_complete_set=False,
    )
    return {
        "version": 1,
        "bundle_sha256": bundle_sha,
        "allowed_decisions": ALLOWED_DECISIONS,
        "review_status": review_status(decisions),
        "reviewer_note": _clean_note(
            payload.get("reviewer_note", ""),
            limit=MAX_REVIEWER_NOTE,
            label="reviewer_note",
        ),
        "updated_at": payload.get("updated_at")
        if isinstance(payload.get("updated_at"), str)
        else None,
        "decisions": decisions,
    }


def save_review(run_dir: Path, payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    run_dir = run_dir.expanduser().resolve()
    bundle, bundle_sha = load_bundle(run_dir)
    if payload.get("bundle_sha256") != bundle_sha:
        raise EvidenceReviewError(
            "화면의 Evidence Bundle이 바뀌었습니다. 새로고침한 뒤 다시 판정해 주세요."
        )
    decisions = _normalize_decisions(
        bundle,
        payload.get("decisions"),
        require_complete_set=True,
    )
    review = {
        "version": 1,
        "bundle_sha256": bundle_sha,
        "allowed_decisions": ALLOWED_DECISIONS,
        "review_status": review_status(decisions),
        "reviewer_note": _clean_note(
            payload.get("reviewer_note", ""),
            limit=MAX_REVIEWER_NOTE,
            label="reviewer_note",
        ),
        "updated_at": utc_now(),
        "decisions": decisions,
    }
    path = _atomic_json(run_dir / "evidence_review.json", review)
    return review, sha256_file(path)


def _json_block(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_revision_context(run_dir: Path) -> dict[str, Any]:
    """Write a context file while leaving the original result and bundle untouched."""

    run_dir = run_dir.expanduser().resolve()
    bundle, bundle_sha = load_bundle(run_dir)
    review = load_review(run_dir)
    review_path = run_dir / "evidence_review.json"
    if not review_path.is_file():
        raise EvidenceReviewError("먼저 evidence 판정을 저장해 주세요.")
    actionable = [
        item
        for item in review["decisions"]
        if item["decision"] in {"question", "exclude"}
    ]
    if not actionable:
        raise EvidenceReviewError(
            "수정에 반영할 '의심' 또는 '제외' 판정이 없습니다."
        )

    request = (run_dir / "request.txt").read_text(encoding="utf-8").strip()
    result = (run_dir / "result.md").read_text(encoding="utf-8").rstrip()
    ledger = _read_object(run_dir / "goal_ledger.json", "Goal Ledger")
    route = _read_object(run_dir / "route.json", "Route record")
    contract_path = run_dir / "result_contract.json"
    contract = _read_object(contract_path, "Result Contract")

    item_by_id = {
        item["id"]: item
        for item in bundle.get("items", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    requirement_links: dict[str, list[str]] = {}
    for requirement in bundle.get("requirements", []):
        if not isinstance(requirement, Mapping):
            continue
        requirement_id = requirement.get("id")
        for evidence_id in requirement.get("evidence_item_ids", []):
            if isinstance(requirement_id, str) and isinstance(evidence_id, str):
                requirement_links.setdefault(evidence_id, []).append(requirement_id)

    reviewed_items: list[dict[str, Any]] = []
    for decision in review["decisions"]:
        item = item_by_id.get(decision["evidence_id"])
        if item is None:
            continue
        reviewed_items.append(
            {
                "evidence_id": decision["evidence_id"],
                "decision": decision["decision"],
                "note": decision["note"],
                "kind": item.get("kind"),
                "source": item.get("source"),
                "finding": item.get("finding"),
                "role": item.get("role"),
                "linked_requirement_ids": requirement_links.get(
                    decision["evidence_id"], []
                ),
            }
        )

    review_sha = sha256_file(review_path)
    content = f"""# PSOS Evidence Review Revision Context

원본 실행 ID: `{run_dir.name}`
Evidence Bundle SHA-256: `{bundle_sha}`
Evidence Review SHA-256: `{review_sha}`

## 수정 규칙

1. 원본 실행의 `result.md`, Evidence Bundle, Evidence Review는 수정하거나 덮어쓰지 않는다.
2. `keep` 근거는 사용자가 유지하기로 한 근거다. 해당 근거에 의존하는 확인된 내용을 보존한다.
3. `question` 근거는 다시 확인한다. 현재 capability로 확인할 수 없으면 단정을 약화하거나 미확인으로 표시한다.
4. `exclude` 근거는 최종 결론의 근거로 사용하지 않는다. 그 근거에만 의존한 주장·추천·순위를 제거하거나 다시 검증한다.
5. 대체 URL, 후기, 가격, 사진, 파일, 실행 결과를 만들어내지 않는다.
6. 수정 내역 설명만 반환하지 말고 사용자가 바로 쓸 수 있는 수정된 전체 결과를 반환한다.
7. 사용자의 원래 목표와 고정 조건을 유지한다.

## 사용자 전체 메모

{review['reviewer_note'] or '없음'}

## 근거별 사용자 판정

```json
{_json_block(reviewed_items)}
```

## 원래 사용자 요청

{request}

## 원래 Goal Ledger

```json
{_json_block(ledger)}
```

## 원래 route

```json
{_json_block(route.get('selected_route'))}
```

## Result Contract

```json
{_json_block(contract)}
```

## 원래 결과

{result}
"""
    context_path = _atomic_text(run_dir / "evidence_revision_context.md", content)
    return {
        "version": 1,
        "parent_run_id": run_dir.name,
        "path": context_path.name,
        "sha256": sha256_file(context_path),
        "bundle_sha256": bundle_sha,
        "review_sha256": review_sha,
        "actionable_decision_count": len(actionable),
    }


def build_revision_request(context_path: str, parent_run_id: str) -> str:
    return f"""`{context_path}` 파일을 읽고 원본 실행 `{parent_run_id}`의 결과를 수정해 주세요.

파일 안의 Evidence Review 판정을 그대로 적용하십시오. keep은 보존하고, question은 다시 확인하거나 단정을 낮추며, exclude는 근거와 그 근거에만 의존한 주장에서 제거하십시오. 확인하지 못한 대체 근거를 만들지 마십시오.

원본 실행 파일은 변경하지 말고, 이번 실행의 result_markdown에 수정된 전체 결과를 완성하십시오."""


def record_revision_submission(
    run_dir: Path,
    *,
    context_record: Mapping[str, Any],
    child_job: Mapping[str, Any],
    search_enabled: bool,
    request: str,
) -> dict[str, Any]:
    record = {
        "version": 1,
        "parent_run_id": run_dir.name,
        "child_job_id": child_job.get("job_id"),
        "child_run_id": child_job.get("run_id"),
        "context_path": context_record.get("path"),
        "context_sha256": context_record.get("sha256"),
        "bundle_sha256": context_record.get("bundle_sha256"),
        "review_sha256": context_record.get("review_sha256"),
        "search_enabled": search_enabled,
        "submitted_at": utc_now(),
        "request": request,
    }
    path = _atomic_json(run_dir / "evidence_revision_request.json", record)
    record["sha256"] = sha256_file(path)
    return record
