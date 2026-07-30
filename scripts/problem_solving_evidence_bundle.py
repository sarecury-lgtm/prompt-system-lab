#!/usr/bin/env python3
"""Build reviewable evidence bundles from a completed PSOS run."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping


URL_PATTERN = re.compile(r"https?://[^\s<>()\]\[\"']+")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)]+)\)")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ITEM_KINDS = {
    "result_text",
    "web",
    "local",
    "command_output",
    "provided_context",
    "image",
    "artifact",
    "receipt",
}
REQUIREMENT_STATUSES = {"satisfied", "missing", "unverifiable", "not_assessed"}
RESULT_STATUSES = {"completed", "partial", "blocked_by_capability", "handoff"}
DECISIONS = ["keep", "question", "exclude"]


class EvidenceBundleError(ValueError):
    """Raised when an evidence bundle cannot be built or validated."""


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceBundleError(f"{label} must be a non-empty string")
    return value.strip()


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_source(value: Any) -> str:
    source = _nonempty(value, "evidence source")
    return source.rstrip(".,;:")


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _looks_like_image(source: str, finding: str = "") -> bool:
    clean = source.split("?", 1)[0].split("#", 1)[0]
    if Path(clean).suffix.lower() in IMAGE_SUFFIXES:
        return True
    combined = f"{source} {finding}".lower()
    return any(
        marker in combined
        for marker in (
            "image",
            "photo",
            "picture",
            "screenshot",
            "이미지",
            "사진",
            "스크린샷",
            "단면",
            "실착",
        )
    )


def _integrity_for_source(run_dir: Path, source: str) -> str | None:
    if _is_url(source):
        return None
    candidate = Path(source).expanduser()
    if not candidate.is_absolute():
        candidate = run_dir / candidate
    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    try:
        return sha256_file(candidate)
    except OSError:
        return None


def _preview(kind: str, source: str, reviewable: bool) -> dict[str, Any]:
    if not reviewable:
        return {"type": "none", "source": None}
    if kind == "image":
        return {"type": "image", "source": source}
    return {"type": "link", "source": source}


def _assessment_requirements(assessment: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(assessment, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in assessment.get("requirements", []):
        if isinstance(item, Mapping) and isinstance(item.get("id"), str):
            result[item["id"]] = dict(item)
    return result


def _load_assessment(run_dir: Path, contract_record: Mapping[str, Any]) -> dict[str, Any] | None:
    validation = contract_record.get("validation")
    if not isinstance(validation, Mapping):
        return None
    final_record = validation.get("final_assessment")
    if not isinstance(final_record, Mapping):
        return None
    path = final_record.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    candidate = run_dir / path
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def build_evidence_bundle(
    run_dir: Path,
    request: str,
    ledger: Mapping[str, Any],
    contract: Mapping[str, Any],
    contract_sha256: str,
    execution: Mapping[str, Any],
    assessment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a conservative, deterministic bundle without inventing subjects or roles."""

    run_dir = run_dir.expanduser().resolve()
    contract_sha256 = _nonempty(contract_sha256, "contract_sha256")
    if not re.fullmatch(r"[a-f0-9]{64}", contract_sha256):
        raise EvidenceBundleError("contract_sha256 must be a lowercase SHA-256")
    result_status = execution.get("status")
    if result_status not in RESULT_STATUSES:
        raise EvidenceBundleError("unsupported execution status")

    result_label = str(
        ledger.get("current_goal_hypothesis")
        or ledger.get("parent_goal")
        or request
        or "최종 결과"
    ).strip()
    items: list[dict[str, Any]] = []
    source_index: dict[str, int] = {}
    ref_map: dict[str, str] = {}
    next_number = 1

    def add_item(
        *,
        kind: str,
        source: str,
        finding: str,
        role: str,
        origin: str,
        reviewable: bool,
        fixed_id: str | None = None,
    ) -> str:
        nonlocal next_number
        if kind not in ITEM_KINDS:
            kind = "provided_context"
        source = _normalize_source(source)
        finding = _nonempty(finding, "evidence finding")
        existing_index = source_index.get(source)
        if existing_index is not None:
            existing = items[existing_index]
            if kind == "image" and existing["kind"] != "image":
                existing["kind"] = "image"
                existing["role"] = "visual_observation"
                existing["preview"] = _preview("image", source, True)
            existing["reviewable"] = bool(existing["reviewable"] or reviewable)
            if existing["preview"]["type"] == "none" and existing["reviewable"]:
                existing["preview"] = _preview(existing["kind"], source, True)
            return existing["id"]

        item_id = fixed_id or f"ev-{next_number:03d}"
        if fixed_id is None:
            next_number += 1
        item = {
            "id": item_id,
            "subject_id": "result",
            "kind": kind,
            "source": source,
            "finding": finding,
            "role": role,
            "origin": origin,
            "reviewable": reviewable,
            "preview": _preview(kind, source, reviewable),
            "integrity": {"sha256": _integrity_for_source(run_dir, source)},
            "review": {"decision": "unreviewed", "note": ""},
        }
        source_index[source] = len(items)
        items.append(item)
        return item_id

    markdown = str(execution.get("result_markdown", "")).strip()
    if markdown:
        ref_map["result_markdown"] = add_item(
            kind="result_text",
            source="result.md",
            finding="최종 결과 본문",
            role="output",
            origin="execution.result_markdown",
            reviewable=True,
            fixed_id="result-text",
        )

    evidence_items = execution.get("evidence", [])
    for index, raw in enumerate(evidence_items if isinstance(evidence_items, list) else []):
        if not isinstance(raw, Mapping):
            continue
        source = raw.get("source")
        finding = raw.get("finding")
        if not isinstance(source, str) or not source.strip():
            continue
        if not isinstance(finding, str) or not finding.strip():
            finding = "실행 결과에 연결된 근거"
        raw_kind = raw.get("kind")
        kind = raw_kind if raw_kind in {"web", "local", "command_output", "provided_context"} else "provided_context"
        if _looks_like_image(source, finding):
            kind = "image"
        reviewable = _is_url(source) or kind in {"local", "command_output", "image"}
        item_id = add_item(
            kind=kind,
            source=source,
            finding=finding,
            role="visual_observation" if kind == "image" else "unclassified",
            origin=f"execution.evidence:{index}",
            reviewable=reviewable,
        )
        ref_map[f"evidence:{index}"] = item_id

    for alt, source in MARKDOWN_IMAGE_PATTERN.findall(markdown):
        add_item(
            kind="image",
            source=source,
            finding=alt.strip() or "최종 결과에 포함된 이미지",
            role="visual_observation",
            origin="result_markdown.image",
            reviewable=True,
        )

    for label, source in MARKDOWN_LINK_PATTERN.findall(markdown):
        add_item(
            kind="image" if _looks_like_image(source, label) else "web",
            source=source,
            finding=label.strip() or "최종 결과에 포함된 링크",
            role="visual_observation" if _looks_like_image(source, label) else "reference",
            origin="result_markdown.link",
            reviewable=True,
        )

    for source in URL_PATTERN.findall(markdown):
        add_item(
            kind="image" if _looks_like_image(source) else "web",
            source=source,
            finding="최종 결과 본문에 제시된 원본 위치",
            role="visual_observation" if _looks_like_image(source) else "reference",
            origin="result_markdown.url",
            reviewable=True,
        )

    artifact_items = execution.get("artifacts", [])
    for index, raw in enumerate(artifact_items if isinstance(artifact_items, list) else []):
        if not isinstance(raw, Mapping):
            continue
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        action = str(raw.get("action") or "artifact")
        verification = str(raw.get("verification") or "실행 결과에 기록된 산출물")
        item_id = add_item(
            kind="image" if _looks_like_image(path, verification) else "artifact",
            source=path,
            finding=f"{action}: {verification}",
            role="visual_observation" if _looks_like_image(path, verification) else "artifact",
            origin=f"execution.artifact:{index}",
            reviewable=True,
        )
        ref_map[f"artifact:{index}"] = item_id

    for receipt_path in sorted(run_dir.glob("*receipt.json")):
        verified = False
        try:
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            verified = isinstance(receipt_payload, Mapping) and receipt_payload.get("verified") is True
        except (OSError, json.JSONDecodeError):
            pass
        item_id = add_item(
            kind="receipt",
            source=receipt_path.name,
            finding="검증된 실행 receipt" if verified else "검증 상태를 확인해야 하는 receipt",
            role="receipt",
            origin="run.receipt",
            reviewable=True,
        )
        ref_map[f"receipt:{receipt_path.name}"] = item_id

    assessed = _assessment_requirements(assessment)
    requirements: list[dict[str, Any]] = []
    all_ids = {item["id"] for item in items}
    for requirement in contract.get("required_outputs", []):
        if not isinstance(requirement, Mapping):
            continue
        requirement_id = _nonempty(requirement.get("id"), "requirement id")
        description = _nonempty(requirement.get("description"), "requirement description")
        verification = requirement.get("verification")
        assessment_item = assessed.get(requirement_id)
        status = "not_assessed"
        refs: list[str] = []
        if assessment_item:
            candidate_status = assessment_item.get("status")
            if candidate_status in REQUIREMENT_STATUSES - {"not_assessed"}:
                status = candidate_status
            for ref in assessment_item.get("evidence_refs", []):
                mapped = ref_map.get(ref)
                if mapped and mapped not in refs:
                    refs.append(mapped)
        if not refs:
            fallback_kinds = {
                "text": {"result_text"},
                "url": {"web", "image"},
                "evidence": {"web", "local", "command_output", "provided_context", "image"},
                "artifact": {"artifact", "image"},
                "receipt": {"receipt"},
                "visual": {"image"},
            }.get(verification, set())
            refs = [item["id"] for item in items if item["kind"] in fallback_kinds]
        requirements.append(
            {
                "id": requirement_id,
                "description": description,
                "status": status,
                "evidence_item_ids": [item_id for item_id in refs if item_id in all_ids],
            }
        )

    review_types = contract.get("user_review", {}).get("evidence_types", [])
    review_required = bool(contract.get("user_review", {}).get("needed")) or any(
        item["kind"] == "image" for item in items
    )
    reviewable_count = sum(1 for item in items if item["reviewable"])
    review_status = (
        "pending"
        if review_required and reviewable_count
        else "unavailable" if review_required else "not_required"
    )
    bundle = {
        "version": 1,
        "contract_sha256": contract_sha256,
        "result_status": result_status,
        "subject_mapping": "result_only",
        "review_required": review_required,
        "subjects": [{"id": "result", "label": result_label, "kind": "result"}],
        "requirements": requirements,
        "items": items,
        "review": {
            "status": review_status,
            "allowed_decisions": DECISIONS,
            "decision_file": "evidence_review.json",
            "review_markdown": "evidence_review.md",
        },
    }
    if review_types and review_required:
        # The types remain in the contract; the bundle deliberately does not pretend
        # every source was semantically classified into one of them.
        pass
    return validate_evidence_bundle(bundle)


def validate_evidence_bundle(payload: Mapping[str, Any]) -> dict[str, Any]:
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
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise EvidenceBundleError("evidence bundle fields do not match schema")
    if payload["version"] != 1:
        raise EvidenceBundleError("unsupported evidence bundle version")
    if not re.fullmatch(r"[a-f0-9]{64}", str(payload["contract_sha256"])):
        raise EvidenceBundleError("invalid contract hash")
    if payload["result_status"] not in RESULT_STATUSES:
        raise EvidenceBundleError("invalid result status")
    if payload["subject_mapping"] != "result_only":
        raise EvidenceBundleError("unsupported subject mapping")
    if not isinstance(payload["review_required"], bool):
        raise EvidenceBundleError("review_required must be boolean")
    subjects = payload["subjects"]
    if subjects != [{"id": "result", "label": subjects[0]["label"], "kind": "result"}] if isinstance(subjects, list) and subjects else True:
        raise EvidenceBundleError("Phase C foundation supports exactly one result subject")
    _nonempty(subjects[0]["label"], "subject label")

    item_ids: set[str] = set()
    for item in payload["items"]:
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
        if not isinstance(item, Mapping) or set(item) != required:
            raise EvidenceBundleError("evidence item fields do not match schema")
        item_id = _nonempty(item["id"], "evidence item id")
        if item_id in item_ids:
            raise EvidenceBundleError("evidence item ids must be unique")
        item_ids.add(item_id)
        if item["kind"] not in ITEM_KINDS or item["subject_id"] != "result":
            raise EvidenceBundleError("invalid evidence item kind or subject")
        _nonempty(item["source"], "evidence item source")
        _nonempty(item["finding"], "evidence item finding")
        if item["review"] != {"decision": "unreviewed", "note": ""}:
            raise EvidenceBundleError("new evidence items must be unreviewed")
        preview = item["preview"]
        if not isinstance(preview, Mapping) or set(preview) != {"type", "source"}:
            raise EvidenceBundleError("invalid preview")
        integrity = item["integrity"]
        if not isinstance(integrity, Mapping) or set(integrity) != {"sha256"}:
            raise EvidenceBundleError("invalid integrity record")

    for requirement in payload["requirements"]:
        if not isinstance(requirement, Mapping) or set(requirement) != {
            "id",
            "description",
            "status",
            "evidence_item_ids",
        }:
            raise EvidenceBundleError("invalid requirement mapping")
        if requirement["status"] not in REQUIREMENT_STATUSES:
            raise EvidenceBundleError("invalid requirement status")
        if any(item_id not in item_ids for item_id in requirement["evidence_item_ids"]):
            raise EvidenceBundleError("requirement references unknown evidence item")

    review = payload["review"]
    if not isinstance(review, Mapping) or review.get("allowed_decisions") != DECISIONS:
        raise EvidenceBundleError("invalid review configuration")
    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_review_markdown(bundle: Mapping[str, Any]) -> str:
    lines = [
        "# Evidence Review",
        "",
        f"결과 상태: `{bundle['result_status']}`",
        f"검토 상태: `{bundle['review']['status']}`",
        "",
        "이 문서는 AI 결론만 보는 대신 원본 근거를 직접 확인하기 위한 검토판입니다.",
        "각 항목을 본 뒤 `evidence_review.json`에 keep / question / exclude를 기록합니다.",
        "",
        "## 완료 조건과 연결된 근거",
        "",
    ]
    for requirement in bundle["requirements"]:
        connected = ", ".join(requirement["evidence_item_ids"]) or "연결된 근거 없음"
        lines.append(
            f"- **{requirement['id']}** · `{requirement['status']}` · "
            f"{requirement['description']} · {connected}"
        )
    lines.extend(["", "## 근거 항목", ""])
    for item in bundle["items"]:
        lines.append(f"### {item['id']} · {item['kind']}")
        lines.append("")
        source = item["source"]
        if item["preview"]["type"] in {"link", "image"} and _is_url(source):
            lines.append(f"원본: [{source}]({source})")
        else:
            lines.append(f"원본: `{source}`")
        lines.append(f"관찰/설명: {item['finding']}")
        lines.append(f"분류: `{item['role']}` · 출처 위치: `{item['origin']}`")
        if item["integrity"]["sha256"]:
            lines.append(f"SHA-256: `{item['integrity']['sha256']}`")
        if item["preview"]["type"] == "image":
            lines.extend(["", f"![{item['id']} 미리보기]({source})"])
        lines.extend(["", "판정: [ ] 유지  [ ] 의심  [ ] 제외", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_evidence_bundle(run_dir: Path, bundle: Mapping[str, Any]) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    validated = validate_evidence_bundle(bundle)
    bundle_path = _atomic_json(run_dir / "evidence_bundle.json", validated)
    bundle_sha = sha256_file(bundle_path)
    review_payload = {
        "version": 1,
        "bundle_sha256": bundle_sha,
        "allowed_decisions": DECISIONS,
        "decisions": [
            {"evidence_id": item["id"], "decision": "unreviewed", "note": ""}
            for item in validated["items"]
            if item["reviewable"]
        ],
    }
    review_path = _atomic_json(run_dir / "evidence_review.json", review_payload)
    markdown_path = run_dir / "evidence_review.md"
    markdown_path.write_text(render_review_markdown(validated), encoding="utf-8")
    return {
        "version": 1,
        "path": bundle_path.name,
        "sha256": bundle_sha,
        "review_template": review_path.name,
        "review_markdown": markdown_path.name,
        "item_count": len(validated["items"]),
        "reviewable_count": sum(1 for item in validated["items"] if item["reviewable"]),
        "image_count": sum(1 for item in validated["items"] if item["kind"] == "image"),
        "review_status": validated["review"]["status"],
    }


def attach_evidence_bundle(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    contract_record = payload.get("result_contract")
    if not isinstance(contract_record, Mapping):
        return None
    contract_path = contract_record.get("path")
    contract_sha = contract_record.get("sha256")
    if not isinstance(contract_path, str) or not isinstance(contract_sha, str):
        return None
    try:
        contract = json.loads((run_dir / contract_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    assessment = _load_assessment(run_dir, contract_record)
    bundle = build_evidence_bundle(
        run_dir,
        payload.get("goal_ledger", {}).get("parent_goal", ""),
        payload.get("goal_ledger", {}),
        contract,
        contract_sha,
        payload.get("execution", {}),
        assessment,
    )
    record = write_evidence_bundle(run_dir, bundle)
    payload["evidence_bundle"] = record
    run_record = payload.get("run")
    if isinstance(run_record, dict):
        run_record["evidence_bundle"] = record
    return record
