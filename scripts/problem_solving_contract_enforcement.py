#!/usr/bin/env python3
"""Validate PSOS executions against a request-specific Result Contract."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

ASSESSMENT_STATUSES = {"satisfied", "missing", "unverifiable"}
OVERALL_STATUSES = {"satisfied", "missing"}
URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")


class ContractEnforcementError(ValueError):
    """Raised when a contract assessment is malformed or not bound to its contract."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractEnforcementError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ContractEnforcementError(f"{label} must be an array of non-empty strings")
    result: list[str] = []
    for item in value:
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def collect_observations(run_dir: Path, execution: Mapping[str, Any]) -> dict[str, Any]:
    """Collect mechanical facts that the semantic assessor is not allowed to invent."""

    markdown = str(execution.get("result_markdown", ""))
    evidence = execution.get("evidence", [])
    artifacts = execution.get("artifacts", [])

    urls: list[str] = []
    for match in URL_PATTERN.findall(markdown):
        cleaned = match.rstrip(".,;:")
        if cleaned not in urls:
            urls.append(cleaned)
    evidence_sources: list[str] = []
    evidence_kinds: dict[str, int] = {}
    visual_references = list(MARKDOWN_IMAGE_PATTERN.findall(markdown))
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, Mapping):
            continue
        source = item.get("source")
        kind = item.get("kind")
        finding = item.get("finding")
        if isinstance(source, str) and source.strip():
            normalized = source.strip()
            if normalized not in evidence_sources:
                evidence_sources.append(normalized)
            if normalized.startswith(("http://", "https://")) and normalized not in urls:
                urls.append(normalized)
        if isinstance(kind, str):
            evidence_kinds[kind] = evidence_kinds.get(kind, 0) + 1
        combined = f"{source or ''} {finding or ''}".lower()
        if (
            isinstance(source, str)
            and source.startswith(("http://", "https://"))
            and any(
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
            and source not in visual_references
        ):
            visual_references.append(source)

    artifact_actions: dict[str, int] = {}
    artifact_paths: list[str] = []
    for item in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(item, Mapping):
            continue
        action = item.get("action")
        path = item.get("path")
        if isinstance(action, str):
            artifact_actions[action] = artifact_actions.get(action, 0) + 1
        if isinstance(path, str) and path.strip() and path.strip() not in artifact_paths:
            artifact_paths.append(path.strip())

    verified_receipts: list[str] = []
    failed_receipts: list[str] = []
    for receipt_path in sorted(run_dir.glob("*receipt.json")):
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failed_receipts.append(receipt_path.name)
            continue
        if isinstance(payload, Mapping) and payload.get("verified") is True:
            verified_receipts.append(receipt_path.name)
        else:
            failed_receipts.append(receipt_path.name)

    return {
        "result_markdown_length": len(markdown.strip()),
        "urls": urls,
        "url_count": len(urls),
        "evidence_sources": evidence_sources,
        "evidence_source_count": len(evidence_sources),
        "evidence_kinds": evidence_kinds,
        "artifact_paths": artifact_paths,
        "artifact_actions": artifact_actions,
        "verified_receipts": verified_receipts,
        "failed_receipts": failed_receipts,
        "visual_references": visual_references,
        "visual_reference_count": len(visual_references),
    }


def build_assessment_prompt(
    contract: Mapping[str, Any],
    contract_sha256: str,
    execution: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> str:
    return f"""당신은 Personal Problem-Solving OS의 Result Contract 검증기다.

새 조사나 새 답변을 만들지 말고, 주어진 실행 결과가 계약을 실제로 충족하는지만 판정한다.
문장에 그럴듯한 표현이 있다는 이유로 충족 처리하지 않는다. 현재 상태, 직접 URL, 실제
artifact, receipt, 시각 근거처럼 계약이 요구하는 대상은 제공된 결과와 기계 관찰에 실제로
존재해야 한다. 제공되지 않은 사실을 추론하거나 보충하지 않는다.

[판정 규칙]
1. contract의 required_outputs를 정확히 한 번씩 판정한다.
2. status는 satisfied, missing, unverifiable 중 하나다.
3. finding은 결과에서 확인한 근거 또는 부족한 이유를 짧게 적는다.
4. evidence_refs에는 result_markdown, evidence:N, artifact:N, receipt:파일명처럼
   제공된 결과 안의 위치만 적는다.
5. evidence_requirements의 최소 출처 수와 결론-출처 연결 여부도 별도로 판정한다.
6. 하나라도 missing 또는 unverifiable이면 overall_status는 missing이다.
7. contract_sha256은 제공된 값을 정확히 복사한다.
8. 내부 추론은 쓰지 않는다.

[Result Contract SHA-256]
{contract_sha256}

[Result Contract]
{json.dumps(contract, ensure_ascii=False, indent=2)}

[실행 결과]
{json.dumps(execution, ensure_ascii=False, indent=2)}

[기계 관찰]
{json.dumps(observations, ensure_ascii=False, indent=2)}
"""


def _hard_requirement_status(
    verification: str,
    observations: Mapping[str, Any],
) -> tuple[bool, str]:
    if verification == "url":
        return observations.get("url_count", 0) > 0, "직접 URL이 감지되지 않았습니다."
    if verification == "artifact":
        return bool(observations.get("artifact_paths")), "artifact가 기록되지 않았습니다."
    if verification == "receipt":
        return bool(observations.get("verified_receipts")), "검증된 receipt가 없습니다."
    if verification == "visual":
        return (
            observations.get("visual_reference_count", 0) > 0,
            "사용자가 열어볼 수 있는 시각 근거가 없습니다.",
        )
    if verification == "evidence":
        return (
            observations.get("evidence_source_count", 0) > 0,
            "연결된 evidence source가 없습니다.",
        )
    return True, ""


def validate_assessment(
    payload: Any,
    contract: Mapping[str, Any],
    contract_sha256: str,
    observations: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "version",
        "contract_sha256",
        "overall_status",
        "requirements",
        "evidence_check",
        "missing_requirement_ids",
        "missing_conditions",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ContractEnforcementError("assessment fields do not match the schema")
    if payload["version"] != 1:
        raise ContractEnforcementError("unsupported assessment version")
    if payload["contract_sha256"] != contract_sha256:
        raise ContractEnforcementError("assessment contract hash does not match")
    if payload["overall_status"] not in OVERALL_STATUSES:
        raise ContractEnforcementError("unsupported overall assessment status")

    required_outputs = contract.get("required_outputs")
    if not isinstance(required_outputs, list) or not required_outputs:
        raise ContractEnforcementError("contract required_outputs are invalid")
    expected_ids = [item["id"] for item in required_outputs]
    requirements = payload["requirements"]
    if not isinstance(requirements, list) or len(requirements) != len(expected_ids):
        raise ContractEnforcementError("assessment must cover every contract requirement")

    normalized_requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    verification_by_id = {item["id"]: item["verification"] for item in required_outputs}
    for item in requirements:
        if not isinstance(item, Mapping) or set(item) != {
            "id",
            "status",
            "finding",
            "evidence_refs",
        }:
            raise ContractEnforcementError("assessment requirement fields are invalid")
        requirement_id = _nonempty_string(item["id"], "requirements.id")
        if requirement_id not in expected_ids or requirement_id in seen:
            raise ContractEnforcementError("assessment requirement ids do not match contract")
        seen.add(requirement_id)
        status = item["status"]
        if status not in ASSESSMENT_STATUSES:
            raise ContractEnforcementError("unsupported requirement status")
        finding = _nonempty_string(item["finding"], "requirements.finding")
        refs = _string_list(item["evidence_refs"], "requirements.evidence_refs")

        hard_ok, hard_message = _hard_requirement_status(
            verification_by_id[requirement_id],
            observations,
        )
        if not hard_ok:
            status = "missing"
            finding = hard_message
            refs = []
        normalized_requirements.append(
            {
                "id": requirement_id,
                "status": status,
                "finding": finding,
                "evidence_refs": refs,
            }
        )
    if seen != set(expected_ids):
        raise ContractEnforcementError("assessment omitted contract requirements")
    normalized_requirements.sort(key=lambda item: expected_ids.index(item["id"]))

    evidence_check = payload["evidence_check"]
    if not isinstance(evidence_check, Mapping) or set(evidence_check) != {
        "status",
        "finding",
    }:
        raise ContractEnforcementError("evidence_check fields are invalid")
    evidence_status = evidence_check["status"]
    if evidence_status not in ASSESSMENT_STATUSES:
        raise ContractEnforcementError("unsupported evidence_check status")
    evidence_finding = _nonempty_string(evidence_check["finding"], "evidence_check.finding")

    minimum_sources = int(contract["evidence_requirements"]["minimum_sources"])
    actual_sources = int(observations.get("evidence_source_count", 0))
    if actual_sources < minimum_sources:
        evidence_status = "missing"
        evidence_finding = (
            f"계약은 서로 구분되는 출처 {minimum_sources}개를 요구하지만 "
            f"{actual_sources}개만 확인됐습니다."
        )
    if (
        contract["evidence_requirements"].get("claim_source_mapping")
        and actual_sources > 0
        and not any(
            item["evidence_refs"]
            for item in normalized_requirements
            if item["status"] == "satisfied"
        )
    ):
        evidence_status = "unverifiable"
        evidence_finding = "충족 판정과 출처 위치의 연결이 확인되지 않았습니다."

    missing_ids = [
        item["id"] for item in normalized_requirements if item["status"] != "satisfied"
    ]
    missing_conditions = _string_list(
        payload["missing_conditions"], "missing_conditions"
    )
    if evidence_status != "satisfied":
        evidence_condition = evidence_finding
        if evidence_condition not in missing_conditions:
            missing_conditions.append(evidence_condition)
    for item in normalized_requirements:
        if item["status"] != "satisfied" and item["finding"] not in missing_conditions:
            missing_conditions.append(item["finding"])

    overall_status = (
        "satisfied"
        if not missing_ids and evidence_status == "satisfied"
        else "missing"
    )
    supplied_missing_ids = _string_list(
        payload["missing_requirement_ids"], "missing_requirement_ids"
    )
    if set(supplied_missing_ids) - set(expected_ids):
        raise ContractEnforcementError("assessment references unknown missing ids")

    return {
        "version": 1,
        "contract_sha256": contract_sha256,
        "overall_status": overall_status,
        "requirements": normalized_requirements,
        "evidence_check": {
            "status": evidence_status,
            "finding": evidence_finding,
        },
        "missing_requirement_ids": missing_ids,
        "missing_conditions": missing_conditions,
    }


def deterministic_fallback_assessment(
    contract: Mapping[str, Any],
    contract_sha256: str,
    observations: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    for item in contract["required_outputs"]:
        hard_ok, hard_message = _hard_requirement_status(
            item["verification"], observations
        )
        if item["verification"] == "text" and observations.get(
            "result_markdown_length", 0
        ) > 0:
            status = "unverifiable"
            finding = "텍스트는 존재하지만 의미상 계약 충족 여부를 검증하지 못했습니다."
        elif hard_ok:
            status = "unverifiable"
            finding = "검증 모델 실패로 의미상 충족 여부를 확인하지 못했습니다."
        else:
            status = "missing"
            finding = hard_message
        requirements.append(
            {
                "id": item["id"],
                "status": status,
                "finding": finding,
                "evidence_refs": [],
            }
        )
    minimum = contract["evidence_requirements"]["minimum_sources"]
    actual = observations.get("evidence_source_count", 0)
    evidence_status = "satisfied" if actual >= minimum else "missing"
    evidence_finding = (
        f"출처 {actual}개가 확인되어 최소 요구 {minimum}개를 충족합니다."
        if evidence_status == "satisfied"
        else f"출처 {actual}개만 확인되어 최소 요구 {minimum}개를 충족하지 못합니다."
    )
    missing_ids = [item["id"] for item in requirements]
    conditions = [reason, *[item["finding"] for item in requirements]]
    if evidence_status != "satisfied":
        conditions.append(evidence_finding)
    return {
        "version": 1,
        "contract_sha256": contract_sha256,
        "overall_status": "missing",
        "requirements": requirements,
        "evidence_check": {
            "status": evidence_status,
            "finding": evidence_finding,
        },
        "missing_requirement_ids": missing_ids,
        "missing_conditions": list(dict.fromkeys(condition for condition in conditions if condition)),
    }


def build_repair_prompt(
    request: str,
    ledger: Mapping[str, Any],
    contract: Mapping[str, Any],
    assessment: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> str:
    return f"""당신은 Personal Problem-Solving OS의 focused repair 실행기다.

기존 결과 전체를 버리고 처음부터 다시 쓰지 않는다. Result Contract 검증에서 빠진 항목만
보충하되, 최종 반환값은 사용자가 바로 쓸 수 있는 완전한 execution JSON이어야 한다.

[규칙]
1. 이미 충족한 내용과 사용자의 고정 조건을 보존한다.
2. assessment의 missing_requirement_ids와 missing_conditions만 집중해서 보충한다.
3. 현재 route에서 허용된 도구만 사용한다.
4. 확인하지 못한 URL, 가격, 현재 상태, 파일, receipt, 이미지, 후기를 만들지 않는다.
5. 충족할 수 없는 항목이 남으면 completed로 꾸미지 말고 상태와 limitations에 반영한다.
6. 분석 보고서가 아니라 수정된 전체 결과를 result_markdown에 넣는다.
7. 내부 추론은 노출하지 않는다.

[사용자 요청]
{request.strip()}

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[Result Contract]
{json.dumps(contract, ensure_ascii=False, indent=2)}

[계약 검증 결과]
{json.dumps(assessment, ensure_ascii=False, indent=2)}

[기존 execution]
{json.dumps(execution, ensure_ascii=False, indent=2)}
"""


def missing_descriptions(
    contract: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> list[str]:
    by_id = {item["id"]: item["description"] for item in contract["required_outputs"]}
    descriptions = [
        by_id[requirement_id]
        for requirement_id in assessment.get("missing_requirement_ids", [])
        if requirement_id in by_id
    ]
    descriptions.extend(
        condition
        for condition in assessment.get("missing_conditions", [])
        if isinstance(condition, str) and condition.strip()
    )
    return list(dict.fromkeys(descriptions))


def apply_failure_policy(
    execution: Mapping[str, Any],
    contract: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a conservative execution that cannot masquerade as completed."""

    result = copy.deepcopy(dict(execution))
    missing = missing_descriptions(contract, assessment)
    bullets = "\n".join(f"- {item}" for item in missing) or "- 계약 충족 여부 미확인"
    limitation = "Result Contract 미충족: " + "; ".join(missing)
    limitations = [
        item
        for item in result.get("limitations", [])
        if isinstance(item, str) and item.strip()
    ]
    if limitation not in limitations:
        limitations.append(limitation)
    result["limitations"] = limitations

    policy = contract["failure_policy"]
    if policy == "no_winner":
        result["status"] = "partial"
        result["summary"] = "조건을 충족하는 결과를 확정하지 못함"
        result["result_markdown"] = (
            "현재 확보된 근거로는 사용자의 조건을 충족하는 결과를 확정할 수 없습니다.\n\n"
            "미충족 조건:\n" + bullets
        )
        result["needed_capability"] = None
        result["handoff"] = None
    elif policy == "blocked":
        result["status"] = "blocked_by_capability"
        result["summary"] = "필수 실행 근거나 capability가 없어 완료하지 못함"
        result["result_markdown"] = (
            "초안 또는 일부 작업은 생성됐지만 필수 조건을 실제로 확인하지 못해 "
            "완료 결과로 인정하지 않았습니다.\n\n미충족 조건:\n" + bullets
        )
        result["needed_capability"] = "Result Contract의 필수 근거 또는 실행 capability"
        result["handoff"] = "미충족 조건을 확보하거나 실행 권한을 제공한 뒤 같은 요청을 다시 실행하세요."
    else:
        result["status"] = "partial"
        result["summary"] = "일부 결과는 생성됐지만 필수 조건이 남음"
        original = str(result.get("result_markdown", "")).rstrip()
        result["result_markdown"] = (
            original
            + "\n\n### 아직 충족되지 않은 조건\n"
            + bullets
        )
        result["needed_capability"] = None
        result["handoff"] = None
    return result


def write_json_atomic(path: Path, payload: Any) -> Path:
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
