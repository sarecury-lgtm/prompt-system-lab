#!/usr/bin/env python3
"""Extract dynamic research into durable candidate updates and merge them safely."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent

import problem_solving_candidate_working_set as WORKING
import problem_solving_dynamic_loop_experiment as DYNAMIC
import problem_solving_next_loop_experiment as LEGACY
import problem_solving_os as OS


ROOT = SCRIPT_DIR.parent
SCHEMA_PATH = ROOT / "schemas" / "problem-solving-candidate-update.schema.json"
UPDATE_ACTIONS = {"PARTIAL_RESEARCH", "VERIFY_CANDIDATE", "VERIFY_COMPLETION"}
SCOUT_RISK = "정찰 단계 단서이므로 세부 속성과 현재 상태를 아직 검증하지 않음"
VERIFICATION_RANK = {
    "unverified": 0,
    "partially_verified": 1,
    "verified": 2,
    "blocked": -1,
}


class CandidateUpdateError(ValueError):
    """Raised when research cannot be converted into a safe candidate update."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateUpdateError(f"{label}이 비어 있습니다.")
    return value.strip()


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise CandidateUpdateError(f"{label}은 배열이어야 합니다.")
    result: list[str] = []
    for item in value:
        text = _text(item, label)
        if text not in result:
            result.append(text)
    return result


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise CandidateUpdateError(f"{label} 필드가 올바르지 않습니다.")
    return value


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip()
    lowered = cleaned.lower()
    if lowered in {"true", "yes", "예", "포함"}:
        return True
    if lowered in {"false", "no", "아니오", "제외"}:
        return False
    compact = cleaned.replace(",", "")
    if re.fullmatch(r"-?\d+", compact):
        return int(compact)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", compact):
        return float(compact)
    return cleaned


def validate_candidate_update(
    payload: Any,
    *,
    working_set: Mapping[str, Any],
) -> dict[str, Any]:
    current = WORKING.validate_working_set(dict(working_set))
    root = _exact_object(payload, {"candidate_update"}, "candidate_update 최상위")
    value = _exact_object(
        root["candidate_update"],
        {
            "updates",
            "resolved_requirements",
            "unresolved_requirements",
            "completion_recommendation",
            "reason",
        },
        "candidate_update",
    )
    if not isinstance(value["updates"], list) or len(value["updates"]) > 30:
        raise CandidateUpdateError("candidate updates는 최대 30개여야 합니다.")
    known_ids = {item["id"] for item in current["candidates"]}
    update_fields = {
        "candidate_id",
        "name",
        "source_family",
        "source_url",
        "why_actionable",
        "attributes",
        "evidence",
        "strengths",
        "risks",
        "status",
        "verification_status",
    }
    updates: list[dict[str, Any]] = []
    for index, raw in enumerate(value["updates"], 1):
        item = _exact_object(raw, update_fields, f"updates[{index}]")
        candidate_id = item["candidate_id"]
        if not isinstance(candidate_id, str):
            raise CandidateUpdateError("candidate_id는 문자열이어야 합니다.")
        candidate_id = candidate_id.strip()
        if candidate_id and candidate_id not in known_ids:
            raise CandidateUpdateError("존재하지 않는 candidate_id를 업데이트할 수 없습니다.")
        if item["source_family"] not in WORKING.SOURCE_FAMILIES:
            raise CandidateUpdateError("source_family가 올바르지 않습니다.")
        if item["status"] not in {"kept", "needs_check"}:
            raise CandidateUpdateError("candidate update status가 올바르지 않습니다.")
        if item["verification_status"] not in VERIFICATION_RANK:
            raise CandidateUpdateError("verification_status가 올바르지 않습니다.")
        attributes = item["attributes"]
        if not isinstance(attributes, list) or len(attributes) > 40:
            raise CandidateUpdateError("attributes는 최대 40개 배열이어야 합니다.")
        normalized_attributes: list[dict[str, str]] = []
        seen_attribute_keys: set[str] = set()
        for attr in attributes:
            attr = _exact_object(attr, {"key", "value", "source"}, "attribute")
            key = _text(attr["key"], "attribute.key")
            if key in seen_attribute_keys:
                raise CandidateUpdateError("attribute key가 중복되었습니다.")
            seen_attribute_keys.add(key)
            normalized_attributes.append(
                {
                    "key": key,
                    "value": _text(attr["value"], "attribute.value"),
                    "source": _text(attr["source"], "attribute.source"),
                }
            )
        evidence = item["evidence"]
        if not isinstance(evidence, list) or len(evidence) > 30:
            raise CandidateUpdateError("evidence는 최대 30개 배열이어야 합니다.")
        normalized_evidence: list[dict[str, str]] = []
        for evidence_item in evidence:
            evidence_item = _exact_object(
                evidence_item,
                {"source", "finding", "kind"},
                "evidence",
            )
            normalized_evidence.append(
                {
                    "source": _text(evidence_item["source"], "evidence.source"),
                    "finding": _text(evidence_item["finding"], "evidence.finding"),
                    "kind": _text(evidence_item["kind"], "evidence.kind"),
                }
            )
        updates.append(
            {
                "candidate_id": candidate_id,
                "name": _text(item["name"], "candidate.name"),
                "source_family": item["source_family"],
                "source_url": _text(item["source_url"], "candidate.source_url"),
                "why_actionable": _text(item["why_actionable"], "candidate.why_actionable"),
                "attributes": normalized_attributes,
                "evidence": normalized_evidence,
                "strengths": _strings(item["strengths"], "candidate.strengths"),
                "risks": _strings(item["risks"], "candidate.risks"),
                "status": item["status"],
                "verification_status": item["verification_status"],
            }
        )
    recommendation = value["completion_recommendation"]
    if recommendation not in {"awaiting_correction", "completed", "partial"}:
        raise CandidateUpdateError("completion_recommendation이 올바르지 않습니다.")
    return {
        "updates": updates,
        "resolved_requirements": _strings(
            value["resolved_requirements"], "resolved_requirements"
        ),
        "unresolved_requirements": _strings(
            value["unresolved_requirements"], "unresolved_requirements"
        ),
        "completion_recommendation": recommendation,
        "reason": _text(value["reason"], "candidate_update.reason"),
    }


def _normalized_name(value: str) -> str:
    return re.sub(r"\W+", "", value).casefold()


def _normalized_url(value: str) -> str:
    cleaned = value.strip()
    try:
        parts = urlsplit(cleaned)
    except ValueError:
        return cleaned.rstrip("/")
    if not parts.scheme or not parts.netloc:
        return cleaned.rstrip("/")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            parts.query,
            "",
        )
    )


def _next_candidate_id(candidates: list[Mapping[str, Any]]) -> str:
    maximum = 0
    for candidate in candidates:
        match = re.fullmatch(r"candidate-(\d+)", str(candidate.get("id", "")))
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"candidate-{maximum + 1:03d}"


def _merge_evidence(
    existing: list[Mapping[str, Any]],
    additions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result = [copy.deepcopy(dict(item)) for item in existing]
    seen = {
        (str(item.get("source", "")), str(item.get("finding", "")), str(item.get("kind", "")))
        for item in result
    }
    for item in additions:
        normalized = copy.deepcopy(dict(item))
        fingerprint = (
            str(normalized.get("source", "")),
            str(normalized.get("finding", "")),
            str(normalized.get("kind", "")),
        )
        if fingerprint not in seen:
            seen.add(fingerprint)
            result.append(normalized)
    return result


def _merge_strings(existing: list[str], additions: list[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *additions]))


def merge_candidate_update(
    working_set: Mapping[str, Any],
    candidate_update: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    current = WORKING.validate_working_set(dict(working_set))
    update = validate_candidate_update(
        {"candidate_update": dict(candidate_update)},
        working_set=current,
    )
    stats = {"added": 0, "updated": 0, "preserved_excluded": 0}
    candidates = current["candidates"]

    for item in update["updates"]:
        target = None
        if item["candidate_id"]:
            target = next(
                (candidate for candidate in candidates if candidate["id"] == item["candidate_id"]),
                None,
            )
        if target is None:
            target = next(
                (
                    candidate
                    for candidate in candidates
                    if _normalized_url(candidate["source_url"]) == _normalized_url(item["source_url"])
                ),
                None,
            )
        if target is None:
            normalized_name = _normalized_name(item["name"])
            target = next(
                (
                    candidate
                    for candidate in candidates
                    if _normalized_name(candidate["name"]) == normalized_name
                ),
                None,
            )

        attribute_evidence = [
            {
                "source": attr["source"],
                "finding": f"{attr['key']}: {attr['value']}",
                "kind": "candidate-attribute",
            }
            for attr in item["attributes"]
        ]
        parsed_attributes = {
            attr["key"]: _parse_scalar(attr["value"])
            for attr in item["attributes"]
        }

        if target is None:
            candidates.append(
                {
                    "id": _next_candidate_id(candidates),
                    "name": item["name"],
                    "source_family": item["source_family"],
                    "source_url": item["source_url"],
                    "why_actionable": item["why_actionable"],
                    "attributes": parsed_attributes,
                    "evidence": _merge_evidence([], [*item["evidence"], *attribute_evidence]),
                    "strengths": item["strengths"],
                    "risks": item["risks"],
                    "status": item["status"],
                    "verification_status": item["verification_status"],
                    "exclusion_reason": None,
                }
            )
            stats["added"] += 1
            continue

        was_excluded = target["status"] == "excluded"
        target["name"] = item["name"]
        target["source_family"] = item["source_family"]
        target["source_url"] = item["source_url"]
        target["why_actionable"] = item["why_actionable"]
        target["attributes"].update(parsed_attributes)
        target["evidence"] = _merge_evidence(
            target["evidence"],
            [*item["evidence"], *attribute_evidence],
        )
        target["strengths"] = _merge_strings(target["strengths"], item["strengths"])
        target["risks"] = _merge_strings(target["risks"], item["risks"])
        current_verification = target["verification_status"]
        incoming_verification = item["verification_status"]
        if incoming_verification == "blocked":
            if current_verification in {"unverified", "blocked"}:
                target["verification_status"] = "blocked"
            target["risks"] = _merge_strings(
                target["risks"],
                ["현재 출처 접근이 막혀 추가 검증이 필요함"],
            )
        elif (
            current_verification == "blocked"
            or VERIFICATION_RANK[incoming_verification]
            >= VERIFICATION_RANK[current_verification]
        ):
            target["verification_status"] = incoming_verification
        if target["verification_status"] not in {"unverified", "blocked"}:
            target["risks"] = [risk for risk in target["risks"] if risk != SCOUT_RISK]
        if was_excluded:
            stats["preserved_excluded"] += 1
        else:
            target["status"] = item["status"]
            target["exclusion_reason"] = None
        stats["updated"] += 1

    resolved = set(update["resolved_requirements"])
    unresolved = [
        item for item in current["unresolved_requirements"] if item not in resolved
    ]
    for item in update["unresolved_requirements"]:
        if item not in unresolved:
            unresolved.append(item)
    current["unresolved_requirements"] = unresolved
    return WORKING.validate_working_set(current), stats


def candidate_update_prompt(state: Mapping[str, Any]) -> str:
    dynamic = state.get("dynamic_state") if isinstance(state.get("dynamic_state"), Mapping) else {}
    execution = dynamic.get("final_execution") if isinstance(dynamic, Mapping) else None
    assessment = dynamic.get("final_assessment") if isinstance(dynamic, Mapping) else None
    return f"""동적 조사 결과에서 후보 작업대에 실제로 반영할 변화만 구조화하세요.

[사용자 요청]
{state['request']}

[현재 후보 작업대]
{json.dumps(state['candidate_working_set'], ensure_ascii=False, indent=2)}

[이번 사용자 교정]
{json.dumps(state.get('latest_correction'), ensure_ascii=False, indent=2)}

[실제 실행 결과]
{json.dumps(execution, ensure_ascii=False, indent=2)}

[완료 평가]
{json.dumps(assessment, ensure_ascii=False, indent=2)}

규칙:
- 실행 결과나 evidence가 직접 뒷받침하는 후보와 속성만 반환합니다.
- 기존 후보는 candidate_id를 반드시 사용합니다.
- 새 후보만 candidate_id를 빈 문자열로 둡니다.
- 같은 URL이나 같은 후보를 새 후보로 중복 생성하지 않습니다.
- 사용자가 제외한 후보를 다시 유지 후보로 되살리지 않습니다.
- 가격, 중량, 판매 상태, 공식 요건처럼 관찰된 값만 attributes에 둡니다.
- 속성의 source에는 그 값을 확인한 직접 출처를 적습니다.
- 아직 확인되지 않은 조건은 unresolved_requirements에 남깁니다.
- 실제로 해결된 기존 미확인 조건만 resolved_requirements에 둡니다.
- 후보 업데이트가 없으면 updates=[]로 반환하고 이유를 설명합니다.
- 완료 추천은 후보 작업대 기준입니다. 사용자가 다시 후보를 쳐낼 가치가 있으면 awaiting_correction, 최종 결론 조건까지 충족하면 completed, 조사 자체가 부족하면 partial입니다.
"""


def _dedupe_trace(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        normalized = copy.deepcopy(dict(record))
        fingerprint = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint not in seen:
            seen.add(fingerprint)
            result.append(normalized)
    return result


def _persist_state(
    run_dir: Path,
    state: dict[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    note: str | None = None,
) -> None:
    state["engine_trace"] = _dedupe_trace(
        [*state.get("engine_trace", []), *engine.trace()]
    )
    OS.write_json(run_dir / LEGACY.STATE_FILENAME, state)
    if state["state"] == "awaiting_correction":
        text = LEGACY._working_markdown(state["candidate_working_set"])
        if note:
            text += f"\n## 최근 조사 반영\n\n{note.strip()}\n"
        (run_dir / "result.md").write_text(text, encoding="utf-8")
    elif state["state"] == "partial" and note:
        result_path = run_dir / "result.md"
        prior = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
        if note not in prior:
            prior = prior.rstrip() + f"\n\n## 후보 업데이트 한계\n\n{note.strip()}\n"
            result_path.write_text(prior.lstrip(), encoding="utf-8")


def apply_update_to_state(
    run_dir: Path,
    state: Mapping[str, Any],
    candidate_update: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    working, stats = merge_candidate_update(
        result["candidate_working_set"],
        candidate_update,
    )
    action = (result.get("latest_correction") or {}).get("planned_action")
    recommendation = candidate_update["completion_recommendation"]
    dynamic = result.get("dynamic_state")
    dynamic_status = dynamic.get("state") if isinstance(dynamic, Mapping) else None
    kept = WORKING.kept_candidates(working)
    has_updates = bool(candidate_update["updates"])

    if action in {"PARTIAL_RESEARCH", "VERIFY_CANDIDATE"}:
        next_state = "awaiting_correction" if has_updates and kept else "partial"
    elif action == "VERIFY_COMPLETION":
        can_complete = (
            recommendation == "completed"
            and dynamic_status == "completed"
            and bool(kept)
            and not working["unresolved_requirements"]
        )
        if can_complete:
            next_state = "completed"
        elif recommendation == "partial" or not kept:
            next_state = "partial"
        else:
            next_state = "awaiting_correction"
    elif recommendation == "completed" and dynamic_status == "completed" and kept:
        next_state = "completed"
    elif recommendation == "partial" or not has_updates:
        next_state = "partial"
    else:
        next_state = "awaiting_correction"

    working["state"] = next_state
    working["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(working)
    result["state"] = next_state
    history = result.get("candidate_update_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "revision": working["revision"],
            "action": action,
            "stats": stats,
            "recommendation": recommendation,
            "reason": candidate_update["reason"],
        }
    )
    result["candidate_update_history"] = history
    _persist_state(
        run_dir,
        result,
        engine=engine,
        note=candidate_update["reason"],
    )
    return run_dir, result


def _downgrade_update_failure(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    error: Exception,
) -> tuple[Path, dict[str, Any]]:
    result = copy.deepcopy(dict(state))
    message = "동적 조사 결과를 후보 작업대에 안전하게 구조화하지 못함: " + (
        str(error).strip() or error.__class__.__name__
    )
    working = result["candidate_working_set"]
    working["state"] = "partial"
    working["next_action"] = None
    result["candidate_working_set"] = WORKING.validate_working_set(working)
    result["state"] = "partial"
    dynamic = result.get("dynamic_state")
    if isinstance(dynamic, dict) and isinstance(dynamic.get("final_execution"), dict):
        limitations = dynamic["final_execution"].setdefault("limitations", [])
        if message not in limitations:
            limitations.append(message)
        dynamic["final_execution"]["status"] = "partial"
    _persist_state(run_dir, result, engine=engine, note=message)
    return run_dir, result


def enrich_dynamic_candidate_state(
    run_dir: Path,
    state: Mapping[str, Any],
    *,
    engine: OS.ProblemSolvingEngine,
    policy: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    if state.get("state") not in {"completed", "partial"}:
        return run_dir, copy.deepcopy(dict(state))
    latest = state.get("latest_correction")
    action = latest.get("planned_action") if isinstance(latest, Mapping) else None
    if action not in UPDATE_ACTIONS:
        return run_dir, copy.deepcopy(dict(state))
    dynamic = state.get("dynamic_state")
    if not isinstance(dynamic, Mapping) or not isinstance(dynamic.get("final_execution"), Mapping):
        return _downgrade_update_failure(
            run_dir,
            state,
            engine=engine,
            error=CandidateUpdateError("실제 동적 실행 결과가 없습니다."),
        )
    try:
        model_policy = policy or OS.load_model_policy()
        raw = DYNAMIC._invoke(
            engine,
            run_dir,
            name=f"next-candidate-update-{state['candidate_working_set']['revision']}",
            phase="next-candidate-update",
            route=None,
            profile=model_policy["router_fallback"],
            schema=SCHEMA_PATH,
            prompt=candidate_update_prompt(state),
        )
        update = validate_candidate_update(
            raw,
            working_set=state["candidate_working_set"],
        )
        if not update["updates"] and action in {"PARTIAL_RESEARCH", "VERIFY_CANDIDATE"}:
            raise CandidateUpdateError("부분 조사에서 후보 변화가 확인되지 않았습니다.")
        return apply_update_to_state(
            run_dir,
            state,
            update,
            engine=engine,
        )
    except (
        CandidateUpdateError,
        WORKING.CandidateWorkingSetError,
        OS.ProblemSolvingError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        return _downgrade_update_failure(
            run_dir,
            state,
            engine=engine,
            error=exc,
        )
