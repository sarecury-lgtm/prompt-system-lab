#!/usr/bin/env python3
"""Import explicitly selected web images into a PSOS Evidence Bundle."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent

import problem_solving_evidence_bundle as evidence_bundle
import problem_solving_evidence_review as evidence_review


SOURCE_KINDS = {"seller", "buyer_review", "editorial", "unknown"}
MAX_IMAGES = 24
MAX_SUBJECT_LABEL = 160
MAX_PAGE_TITLE = 300
MAX_ALT = 300
MAX_NEARBY_TEXT = 800
MAX_URL = 4000
ITEM_ID_PATTERN = re.compile(r"^ev-(\d+)$")


class VisualEvidenceError(ValueError):
    """Raised when a visual evidence import is stale or unsafe."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_bytes(path: Path, content: bytes) -> Path:
    path = path.expanduser().resolve()
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
        if temp_path.exists():
            temp_path.unlink()
    return path


def _atomic_json(path: Path, payload: Any) -> Path:
    return _atomic_bytes(path, _json_bytes(payload))


def _clean_text(
    value: Any,
    label: str,
    *,
    limit: int,
    required: bool = False,
) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise VisualEvidenceError(f"{label}는 문자열이어야 합니다.")
    cleaned = " ".join(value.split())
    if required and not cleaned:
        raise VisualEvidenceError(f"{label}를 입력해 주세요.")
    if len(cleaned) > limit:
        raise VisualEvidenceError(f"{label}는 {limit}자 이하여야 합니다.")
    return cleaned


def _http_url(value: Any, label: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    text = _clean_text(value, label, limit=MAX_URL, required=required)
    if not text and not required:
        return None
    parsed = urlsplit(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise VisualEvidenceError(f"{label}는 http 또는 https URL이어야 합니다.")
    if parsed.username is not None or parsed.password is not None:
        raise VisualEvidenceError(f"{label}에는 인증 정보를 넣을 수 없습니다.")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path,
            parsed.query,
            "",
        )
    )


def _timestamp(value: Any) -> str:
    text = _clean_text(value, "captured_at", limit=80, required=True)
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VisualEvidenceError("captured_at은 ISO 8601 시각이어야 합니다.") from exc
    if parsed.tzinfo is None:
        raise VisualEvidenceError("captured_at에는 시간대가 포함돼야 합니다.")
    return parsed.isoformat()


def _dimension(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VisualEvidenceError(f"{label}는 정수여야 합니다.")
    if value <= 0 or value > 20_000:
        raise VisualEvidenceError(f"{label}가 허용 범위를 벗어났습니다.")
    return value


def validate_import_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "version",
        "bundle_sha256",
        "subject_label",
        "source_kind",
        "page_url",
        "page_title",
        "captured_at",
        "images",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise VisualEvidenceError("시각 근거 가져오기 필드가 올바르지 않습니다.")
    if payload.get("version") != 1:
        raise VisualEvidenceError("지원하지 않는 시각 근거 가져오기 버전입니다.")
    bundle_sha = payload.get("bundle_sha256")
    if not isinstance(bundle_sha, str) or re.fullmatch(r"[a-f0-9]{64}", bundle_sha) is None:
        raise VisualEvidenceError("bundle_sha256이 올바르지 않습니다.")
    subject_label = _clean_text(
        payload.get("subject_label"),
        "후보명",
        limit=MAX_SUBJECT_LABEL,
        required=True,
    )
    source_kind = payload.get("source_kind")
    if source_kind not in SOURCE_KINDS:
        raise VisualEvidenceError("지원하지 않는 사진 출처 유형입니다.")
    page_url = _http_url(payload.get("page_url"), "페이지 URL")
    page_title = _clean_text(
        payload.get("page_title"),
        "페이지 제목",
        limit=MAX_PAGE_TITLE,
    )
    captured_at = _timestamp(payload.get("captured_at"))
    raw_images = payload.get("images")
    if not isinstance(raw_images, list) or not 1 <= len(raw_images) <= MAX_IMAGES:
        raise VisualEvidenceError(f"사진은 한 번에 1개부터 {MAX_IMAGES}개까지 가져올 수 있습니다.")

    images: list[dict[str, Any]] = []
    seen: set[str] = set()
    image_fields = {"src", "alt", "width", "height", "nearby_text", "link_url"}
    for raw in raw_images:
        if not isinstance(raw, Mapping) or set(raw) != image_fields:
            raise VisualEvidenceError("사진 항목 필드가 올바르지 않습니다.")
        src = _http_url(raw.get("src"), "사진 URL")
        assert src is not None
        if src in seen:
            continue
        seen.add(src)
        images.append(
            {
                "src": src,
                "alt": _clean_text(raw.get("alt"), "사진 대체 텍스트", limit=MAX_ALT),
                "width": _dimension(raw.get("width"), "사진 너비"),
                "height": _dimension(raw.get("height"), "사진 높이"),
                "nearby_text": _clean_text(
                    raw.get("nearby_text"),
                    "사진 주변 문맥",
                    limit=MAX_NEARBY_TEXT,
                ),
                "link_url": _http_url(raw.get("link_url"), "사진 연결 URL", required=False),
            }
        )
    if not images:
        raise VisualEvidenceError("중복을 제외하고 가져올 사진이 없습니다.")
    return {
        "version": 1,
        "bundle_sha256": bundle_sha,
        "subject_label": subject_label,
        "source_kind": source_kind,
        "page_url": page_url,
        "page_title": page_title,
        "captured_at": captured_at,
        "images": images,
    }


def _subject_id(label: str) -> str:
    digest = hashlib.sha256(label.casefold().encode("utf-8")).hexdigest()[:12]
    return f"candidate-{digest}"


def _next_item_number(items: list[Mapping[str, Any]]) -> int:
    maximum = 0
    for item in items:
        match = ITEM_ID_PATTERN.fullmatch(str(item.get("id") or ""))
        if match:
            maximum = max(maximum, int(match.group(1)))
    return maximum + 1


def _source_kind_label(value: str) -> str:
    return {
        "seller": "판매자 제공 사진",
        "buyer_review": "구매자 후기 사진",
        "editorial": "편집·기사 사진",
        "unknown": "출처 유형 미확인 사진",
    }[value]


def _validate_extended_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise VisualEvidenceError("Evidence Bundle이 JSON 객체가 아닙니다.")
    expected = {
        "version",
        "contract_sha256",
        "result_status",
        "subject_mapping",
        "review_required",
        "subjects",
        "requirements",
        "items",
        "review",
    }
    if set(bundle) != expected or bundle.get("version") != 2:
        raise VisualEvidenceError("확장 Evidence Bundle 구조가 올바르지 않습니다.")
    if bundle.get("subject_mapping") != "explicit":
        raise VisualEvidenceError("후보별 Evidence Bundle은 explicit 연결이어야 합니다.")
    subjects = bundle.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        raise VisualEvidenceError("Evidence Bundle subjects가 올바르지 않습니다.")
    subject_ids: set[str] = set()
    result_count = 0
    for subject in subjects:
        if not isinstance(subject, Mapping) or set(subject) != {"id", "label", "kind"}:
            raise VisualEvidenceError("Evidence Bundle subject 필드가 올바르지 않습니다.")
        subject_id = subject.get("id")
        if not isinstance(subject_id, str) or not subject_id or subject_id in subject_ids:
            raise VisualEvidenceError("Evidence Bundle subject ID가 올바르지 않습니다.")
        subject_ids.add(subject_id)
        _clean_text(subject.get("label"), "subject label", limit=MAX_SUBJECT_LABEL, required=True)
        if subject.get("kind") not in {"result", "candidate"}:
            raise VisualEvidenceError("지원하지 않는 Evidence Bundle subject 종류입니다.")
        result_count += int(subject.get("kind") == "result")
    if result_count != 1:
        raise VisualEvidenceError("Evidence Bundle에는 result subject가 정확히 하나 있어야 합니다.")

    item_ids: set[str] = set()
    for item in bundle.get("items", []):
        if not isinstance(item, Mapping):
            raise VisualEvidenceError("Evidence Bundle item이 객체가 아닙니다.")
        required = {
            "id",
            "subject_id",
            "kind",
            "source",
            "finding",
            "role",
            "origin",
            "reviewable",
            "preview",
            "integrity",
            "review",
        }
        allowed = {*required, "capture"}
        if not required.issubset(item) or not set(item).issubset(allowed):
            raise VisualEvidenceError("Evidence Bundle item 필드가 올바르지 않습니다.")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise VisualEvidenceError("Evidence Bundle item ID가 올바르지 않습니다.")
        item_ids.add(item_id)
        if item.get("subject_id") not in subject_ids:
            raise VisualEvidenceError("Evidence item이 알 수 없는 subject를 가리킵니다.")
        capture = item.get("capture")
        if capture is not None:
            capture_fields = {
                "source_kind",
                "page_url",
                "page_title",
                "captured_at",
                "alt",
                "nearby_text",
                "link_url",
                "width",
                "height",
            }
            if not isinstance(capture, Mapping) or set(capture) != capture_fields:
                raise VisualEvidenceError("시각 근거 capture 필드가 올바르지 않습니다.")
            if capture.get("source_kind") not in SOURCE_KINDS:
                raise VisualEvidenceError("시각 근거 source_kind가 올바르지 않습니다.")
    for requirement in bundle.get("requirements", []):
        if any(item_id not in item_ids for item_id in requirement.get("evidence_item_ids", [])):
            raise VisualEvidenceError("완료 조건이 알 수 없는 evidence item을 가리킵니다.")
    return json.loads(json.dumps(bundle, ensure_ascii=False))


def _render_extended_review_markdown(bundle: Mapping[str, Any]) -> str:
    subject_by_id = {
        subject["id"]: subject
        for subject in bundle.get("subjects", [])
        if isinstance(subject, Mapping)
    }
    lines = [
        "# Evidence Review",
        "",
        f"결과 상태: `{bundle['result_status']}`",
        f"검토 상태: `{bundle['review']['status']}`",
        "",
        "AI 결론만 보지 않고 원본 사진·링크와 후보 연결을 직접 확인합니다.",
        "",
        "## 후보별 시각 근거",
        "",
    ]
    for subject in bundle.get("subjects", []):
        if subject.get("kind") != "candidate":
            continue
        lines.extend([f"### {subject['label']}", ""])
        subject_items = [
            item
            for item in bundle.get("items", [])
            if item.get("subject_id") == subject.get("id")
        ]
        for item in subject_items:
            source = item["source"]
            capture = item.get("capture") or {}
            lines.append(f"#### {item['id']} · {_source_kind_label(capture.get('source_kind', 'unknown'))}")
            lines.append("")
            lines.append(f"원본 이미지: [{source}]({source})")
            lines.append(f"원본 페이지: [{capture.get('page_url')}]({capture.get('page_url')})")
            lines.append(f"관찰/문맥: {item['finding']}")
            lines.append(f"후보 연결: `{subject_by_id[item['subject_id']]['label']}`")
            lines.extend(["", "판정: [ ] 유지  [ ] 의심  [ ] 제외", ""])
    lines.extend(["## 전체 근거 항목", ""])
    for item in bundle.get("items", []):
        subject = subject_by_id.get(item.get("subject_id"), {"label": "결과 전체"})
        lines.append(
            f"- `{item['id']}` · `{item['kind']}` · {subject['label']} · {item['finding']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _bundle_record(bundle: Mapping[str, Any], bundle_sha: str) -> dict[str, Any]:
    return {
        "version": 2,
        "path": "evidence_bundle.json",
        "sha256": bundle_sha,
        "review_template": "evidence_review.json",
        "review_markdown": "evidence_review.md",
        "item_count": len(bundle.get("items", [])),
        "reviewable_count": sum(
            1 for item in bundle.get("items", []) if item.get("reviewable") is True
        ),
        "image_count": sum(1 for item in bundle.get("items", []) if item.get("kind") == "image"),
        "subject_count": len(bundle.get("subjects", [])),
        "review_status": bundle.get("review", {}).get("status"),
    }


def import_visual_evidence(run_dir: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Append explicitly selected images and preserve decisions for unchanged evidence IDs."""

    run_dir = run_dir.expanduser().resolve()
    cleaned = validate_import_payload(payload)
    bundle, current_sha = evidence_review.load_bundle(run_dir)
    if cleaned["bundle_sha256"] != current_sha:
        raise VisualEvidenceError(
            "Evidence Bundle이 바뀌었습니다. PSOS 결과 화면을 새로고침한 뒤 다시 수집해 주세요."
        )
    old_review = evidence_review.load_review(run_dir)

    if bundle.get("version") == 1:
        evidence_bundle.validate_evidence_bundle(bundle)
    elif bundle.get("version") != 2:
        raise VisualEvidenceError("지원하지 않는 Evidence Bundle 버전입니다.")

    updated = json.loads(json.dumps(bundle, ensure_ascii=False))
    updated["version"] = 2
    updated["subject_mapping"] = "explicit"
    subjects = updated.setdefault("subjects", [])
    result_subject = next(
        (subject for subject in subjects if subject.get("kind") == "result"),
        None,
    )
    if result_subject is None:
        raise VisualEvidenceError("기존 Evidence Bundle의 result subject를 찾을 수 없습니다.")

    subject = next(
        (
            candidate
            for candidate in subjects
            if candidate.get("kind") == "candidate"
            and str(candidate.get("label", "")).casefold() == cleaned["subject_label"].casefold()
        ),
        None,
    )
    if subject is None:
        subject = {
            "id": _subject_id(cleaned["subject_label"]),
            "label": cleaned["subject_label"],
            "kind": "candidate",
        }
        existing_ids = {candidate.get("id") for candidate in subjects}
        if subject["id"] in existing_ids:
            raise VisualEvidenceError("후보 ID 충돌이 발생했습니다.")
        subjects.append(subject)

    items = updated.setdefault("items", [])
    next_number = _next_item_number(items)
    existing = {
        (str(item.get("subject_id")), str(item.get("source")))
        for item in items
        if isinstance(item, Mapping)
    }
    added_ids: list[str] = []
    duplicate_sources: list[str] = []
    source_label = _source_kind_label(cleaned["source_kind"])
    for image in cleaned["images"]:
        key = (subject["id"], image["src"])
        if key in existing:
            duplicate_sources.append(image["src"])
            continue
        existing.add(key)
        context = image["alt"] or image["nearby_text"] or "선택한 이미지"
        finding = f"[{subject['label']}] {source_label} · {context}"
        item_id = f"ev-{next_number:03d}"
        next_number += 1
        items.append(
            {
                "id": item_id,
                "subject_id": subject["id"],
                "kind": "image",
                "source": image["src"],
                "finding": finding,
                "role": "visual_observation",
                "origin": "browser_visual_collector",
                "reviewable": True,
                "preview": {"type": "image", "source": image["src"]},
                "integrity": {"sha256": None},
                "review": {"decision": "unreviewed", "note": ""},
                "capture": {
                    "source_kind": cleaned["source_kind"],
                    "page_url": cleaned["page_url"],
                    "page_title": cleaned["page_title"],
                    "captured_at": cleaned["captured_at"],
                    "alt": image["alt"],
                    "nearby_text": image["nearby_text"],
                    "link_url": image["link_url"],
                    "width": image["width"],
                    "height": image["height"],
                },
            }
        )
        added_ids.append(item_id)
    if not added_ids:
        raise VisualEvidenceError("선택한 사진이 모두 이 후보에 이미 추가돼 있습니다.")

    updated["review_required"] = True
    updated["review"]["status"] = "pending"
    validated = _validate_extended_bundle(updated)
    bundle_bytes = _json_bytes(validated)
    new_bundle_sha = hashlib.sha256(bundle_bytes).hexdigest()

    old_decisions = {
        decision["evidence_id"]: decision
        for decision in old_review.get("decisions", [])
        if isinstance(decision, Mapping)
    }
    decisions = [
        dict(
            old_decisions.get(
                item["id"],
                {"evidence_id": item["id"], "decision": "unreviewed", "note": ""},
            )
        )
        for item in validated["items"]
        if item.get("reviewable") is True
    ]
    migrated_review = {
        "version": 1,
        "bundle_sha256": new_bundle_sha,
        "allowed_decisions": evidence_review.ALLOWED_DECISIONS,
        "review_status": evidence_review.review_status(decisions),
        "reviewer_note": old_review.get("reviewer_note", ""),
        "updated_at": utc_now(),
        "decisions": decisions,
    }

    history_path = run_dir / "visual_evidence_imports.json"
    if history_path.is_file():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VisualEvidenceError(f"기존 시각 근거 기록을 읽을 수 없습니다: {exc}") from exc
        if not isinstance(history, dict) or history.get("version") != 1 or not isinstance(history.get("imports"), list):
            raise VisualEvidenceError("기존 시각 근거 기록 구조가 올바르지 않습니다.")
    else:
        history = {"version": 1, "imports": []}
    import_seed = (
        f"{current_sha}:{new_bundle_sha}:{subject['id']}:{cleaned['captured_at']}:{','.join(added_ids)}"
    )
    import_record = {
        "version": 1,
        "import_id": "visual-" + hashlib.sha256(import_seed.encode("utf-8")).hexdigest()[:16],
        "previous_bundle_sha256": current_sha,
        "bundle_sha256": new_bundle_sha,
        "subject_id": subject["id"],
        "subject_label": subject["label"],
        "source_kind": cleaned["source_kind"],
        "page_url": cleaned["page_url"],
        "page_title": cleaned["page_title"],
        "captured_at": cleaned["captured_at"],
        "imported_at": utc_now(),
        "added_item_ids": added_ids,
        "duplicate_sources": duplicate_sources,
    }
    history["imports"].append(import_record)

    originals: dict[Path, bytes | None] = {}
    targets = {
        run_dir / "evidence_bundle.json": bundle_bytes,
        run_dir / "evidence_review.json": _json_bytes(migrated_review),
        run_dir / "evidence_review.md": _render_extended_review_markdown(validated).encode("utf-8"),
        history_path: _json_bytes(history),
    }
    for path in targets:
        originals[path] = path.read_bytes() if path.is_file() else None
    try:
        for path, content in targets.items():
            _atomic_bytes(path, content)
    except Exception:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_bytes(path, original)
        raise

    return {
        "bundle": validated,
        "bundle_record": _bundle_record(validated, new_bundle_sha),
        "review": migrated_review,
        "import": import_record,
    }


def enrich_revision_context(run_dir: Path, context_record: Mapping[str, Any]) -> dict[str, Any]:
    """Append candidate and capture metadata to an existing immutable revision context."""

    run_dir = run_dir.expanduser().resolve()
    bundle, _bundle_sha = evidence_review.load_bundle(run_dir)
    if bundle.get("version") != 2:
        return dict(context_record)
    context_path = run_dir / str(context_record.get("path") or "")
    if not context_path.is_file():
        raise VisualEvidenceError("수정 문맥 파일을 찾을 수 없습니다.")
    subject_by_id = {
        subject["id"]: subject["label"]
        for subject in bundle.get("subjects", [])
        if isinstance(subject, Mapping)
    }
    visual_items = [
        {
            "evidence_id": item.get("id"),
            "subject_id": item.get("subject_id"),
            "subject_label": subject_by_id.get(item.get("subject_id"), "결과 전체"),
            "source": item.get("source"),
            "finding": item.get("finding"),
            "capture": item.get("capture"),
        }
        for item in bundle.get("items", [])
        if isinstance(item, Mapping) and item.get("capture") is not None
    ]
    if not visual_items:
        return dict(context_record)
    addition = (
        "\n\n## 후보별 시각 근거 연결\n\n"
        "아래 연결은 사용자가 브라우저에서 직접 후보명을 지정해 수집한 것이다. "
        "다른 후보로 임의 재분류하지 않는다.\n\n```json\n"
        + json.dumps(visual_items, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    _atomic_bytes(context_path, context_path.read_bytes() + addition.encode("utf-8"))
    enriched = dict(context_record)
    enriched["sha256"] = evidence_review.sha256_file(context_path)
    enriched["visual_subject_count"] = len(
        {item["subject_id"] for item in visual_items if item.get("subject_id")}
    )
    enriched["visual_item_count"] = len(visual_items)
    return enriched
