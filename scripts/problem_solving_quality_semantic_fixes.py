#!/usr/bin/env python3
"""Tighten Result Contract, assessment, and evidence semantics for the quality runtime."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping


_IMAGE_MARKERS = (
    "image", "photo", "picture", "screenshot", "이미지", "사진", "스크린샷", "단면", "실착",
)


def _looks_visual(source: Any, finding: Any = "") -> bool:
    text = f"{source or ''} {finding or ''}".lower()
    clean = str(source or "").split("?", 1)[0].split("#", 1)[0].lower()
    return clean.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")) or any(
        marker in text for marker in _IMAGE_MARKERS
    )


def _patch_contract(contract_module: Any) -> None:
    if getattr(contract_module, "_empty_constraints_fix_applied", False):
        return
    original_unique = contract_module._unique_strings

    def unique_strings(values: Any, label: str, *, allow_empty: bool = True):
        if label in {"ledger.fixed_constraints", "must_preserve"}:
            allow_empty = True
        return original_unique(values, label, allow_empty=allow_empty)

    contract_module._unique_strings = unique_strings
    contract_module._empty_constraints_fix_applied = True


def _patch_enforcement(enforcement: Any) -> None:
    if getattr(enforcement, "_reference_integrity_fix_applied", False):
        return
    original_collect = enforcement.collect_observations
    original_prompt = enforcement.build_assessment_prompt
    original_validate = enforcement.validate_assessment

    def collect_observations(run_dir: Path, execution: Mapping[str, Any]) -> dict[str, Any]:
        observations = original_collect(run_dir, execution)
        refs = {
            "text": ["result_markdown"] if observations.get("result_markdown_length", 0) else [],
            "url": ["result_markdown"] if observations.get("url_count", 0) else [],
            "evidence": [],
            "artifact": [],
            "receipt": [f"receipt:{name}" for name in observations.get("verified_receipts", [])],
            "visual": ["result_markdown"] if observations.get("visual_reference_count", 0) else [],
        }
        evidence_items = execution.get("evidence", [])
        for index, item in enumerate(evidence_items if isinstance(evidence_items, list) else []):
            if not isinstance(item, Mapping):
                continue
            ref = f"evidence:{index}"
            refs["evidence"].append(ref)
            source = item.get("source")
            if isinstance(source, str) and source.startswith(("http://", "https://")):
                refs["url"].append(ref)
            if _looks_visual(source, item.get("finding")):
                refs["visual"].append(ref)
        artifact_items = execution.get("artifacts", [])
        for index, item in enumerate(artifact_items if isinstance(artifact_items, list) else []):
            if not isinstance(item, Mapping):
                continue
            ref = f"artifact:{index}"
            refs["artifact"].append(ref)
            if _looks_visual(item.get("path"), item.get("verification")):
                refs["visual"].append(ref)
        observations["reference_catalog"] = {
            key: list(dict.fromkeys(values)) for key, values in refs.items()
        }
        observations["valid_evidence_refs"] = list(
            dict.fromkeys(
                value
                for values in observations["reference_catalog"].values()
                for value in values
            )
        )
        return observations

    def build_assessment_prompt(
        contract: Mapping[str, Any],
        contract_sha256: str,
        execution: Mapping[str, Any],
        observations: Mapping[str, Any],
    ) -> str:
        base = original_prompt(contract, contract_sha256, execution, observations).rstrip()
        return base + "\n\n[사용 가능한 evidence_refs 목록]\n" + json.dumps(
            observations.get("reference_catalog", {}), ensure_ascii=False, indent=2
        ) + "\n목록에 없는 참조를 만들지 말고 verification 종류에 맞는 참조만 사용한다.\n"

    def validate_assessment(
        payload: Any,
        contract: Mapping[str, Any],
        contract_sha256: str,
        observations: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = original_validate(payload, contract, contract_sha256, observations)
        catalog = observations.get("reference_catalog", {})
        valid_refs = set(observations.get("valid_evidence_refs", []))
        verification_by_id = {
            item["id"]: item["verification"] for item in contract["required_outputs"]
        }
        missing_conditions = list(result["missing_conditions"])
        for item in result["requirements"]:
            unknown = set(item["evidence_refs"]) - valid_refs
            if unknown:
                raise enforcement.ContractEnforcementError(
                    "assessment referenced unknown evidence locations: "
                    + ", ".join(sorted(unknown))
                )
            verification = verification_by_id[item["id"]]
            allowed = set(catalog.get(verification, []))
            if item["status"] == "satisfied" and not (
                set(item["evidence_refs"]) & allowed
            ):
                item["status"] = "missing"
                item["finding"] = (
                    f"{verification} 검증에 맞는 실제 evidence_ref가 연결되지 않았습니다."
                )
                item["evidence_refs"] = []
                if item["finding"] not in missing_conditions:
                    missing_conditions.append(item["finding"])
        result["missing_requirement_ids"] = [
            item["id"]
            for item in result["requirements"]
            if item["status"] != "satisfied"
        ]
        result["missing_conditions"] = missing_conditions
        result["overall_status"] = (
            "satisfied"
            if not result["missing_requirement_ids"]
            and result["evidence_check"]["status"] == "satisfied"
            else "missing"
        )
        return result

    enforcement.collect_observations = collect_observations
    enforcement.build_assessment_prompt = build_assessment_prompt
    enforcement.validate_assessment = validate_assessment
    enforcement._reference_integrity_fix_applied = True


def _patch_contract_runtime(runtime: Any) -> None:
    if getattr(runtime, "_semantic_runtime_fix_applied", False):
        return
    os_module = runtime.OS

    def persist_runtime_state(run_dir: Path, payload: dict[str, Any], engine: Any) -> None:
        run_record = payload.get("run")
        if isinstance(run_record, dict):
            run_record["engine_trace"] = engine.trace()
            if "result_contract" in payload:
                run_record["result_contract"] = payload["result_contract"]
        route_record = {
            **payload["route"],
            "execution_status": payload["execution"]["status"],
            "capabilities_used": payload["execution"]["capabilities_used"],
            "needed_capability": payload["execution"]["needed_capability"],
            "handoff": payload["execution"]["handoff"],
            "artifacts": payload["execution"]["artifacts"],
            "evidence": payload["execution"]["evidence"],
            "limitations": payload["execution"]["limitations"],
            "run": payload["run"],
        }
        if "prompt_compiler" in payload:
            route_record["prompt_compiler"] = payload["prompt_compiler"]
        if "result_contract" in payload:
            route_record["result_contract"] = payload["result_contract"]
        os_module.write_json(run_dir / "goal_ledger.json", payload["goal_ledger"])
        os_module.write_json(run_dir / "route.json", route_record)
        (run_dir / "result.md").write_text(
            os_module.result_markdown(payload), encoding="utf-8"
        )

    def run_request(
        request: str,
        *,
        context_path: Path | None = None,
        output_root: Path | None = None,
        engine: Any,
        model_policy: dict[str, Any] | None = None,
        model_policy_path: Path | None = None,
        run_id: str | None = None,
    ):
        output_root = output_root or os_module.RUNS_DIR
        model_policy_path = model_policy_path or os_module.DEFAULT_MODEL_POLICY_PATH
        policy = model_policy or os_module.load_model_policy(model_policy_path)
        wrapped = runtime.ContractAwareEngine(
            engine,
            request=request,
            profiles=runtime.contract_profiles(policy),
        )
        run_dir, payload = os_module.run_request(
            request,
            context_path=context_path,
            output_root=output_root,
            engine=wrapped,
            model_policy=policy,
            model_policy_path=model_policy_path,
            run_id=run_id,
        )
        routed = copy.deepcopy(getattr(wrapped, "_router_payload", None))
        if (
            routed is not None
            and payload.get("route", {}).get("selected_route") is None
            and payload.get("execution", {}).get("status") == "blocked_by_capability"
        ):
            detail = "; ".join(payload["execution"].get("limitations", []))
            payload["goal_ledger"] = routed["goal_ledger"]
            payload["route"] = routed["route"]
            payload["execution"] = os_module.blocked_execution(
                "경로 선택은 완료했지만 선택된 경로의 실행 중 오류가 발생해 결과를 완성하지 못했습니다.",
                needed_capability=f"{routed['route']['selected_route']} 경로 실행 환경",
                handoff="실행 기록의 오류를 확인한 뒤 같은 요청을 다시 실행하세요.",
                limitation=detail or "라우팅 이후 실행 오류",
            )
            if isinstance(payload.get("run"), dict):
                payload["run"]["model_plan"] = os_module.selected_model_plan(
                    payload["route"], policy
                )
        contract = wrapped.contract_payload()
        record = wrapped.contract_record()
        if contract is not None and record is not None:
            payload["result_contract"] = record
            if isinstance(payload.get("run"), dict):
                payload["run"]["result_contract"] = record
            runtime.enforce_result_contract(
                request, run_dir, payload, engine, policy, contract, record
            )
            if isinstance(payload.get("run"), dict):
                payload["run"]["result_contract"] = record
        persist_runtime_state(run_dir, payload, engine)
        return run_dir, payload

    runtime._persist_runtime_state = persist_runtime_state
    runtime.run_request = run_request
    runtime._semantic_runtime_fix_applied = True


def _patch_evidence(evidence: Any) -> None:
    if getattr(evidence, "_semantic_bundle_fix_applied", False):
        return
    original_integrity = evidence._integrity_for_source
    original_build = evidence.build_evidence_bundle
    evidence._workspace_root = None

    def integrity_for_source(run_dir: Path, source: str) -> str | None:
        direct = original_integrity(run_dir, source)
        if direct:
            return direct
        if evidence._is_url(source):
            return None
        workspace = evidence._workspace_root
        if workspace is None:
            return None
        root = Path(workspace).expanduser().resolve()
        candidate = Path(source).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            candidate = candidate.resolve()
            candidate.relative_to(root)
        except (OSError, ValueError):
            return None
        if not candidate.is_file():
            return None
        try:
            return evidence.sha256_file(candidate)
        except OSError:
            return None

    def build_evidence_bundle(*args: Any, **kwargs: Any) -> dict[str, Any]:
        execution = args[5] if len(args) > 5 else kwargs.get("execution", {})
        bundle = original_build(*args, **kwargs)
        findings_by_source: dict[str, list[str]] = {}
        origins_by_source: dict[str, list[str]] = {}
        raw_evidence = execution.get("evidence", []) if isinstance(execution, Mapping) else []
        for index, raw in enumerate(raw_evidence if isinstance(raw_evidence, list) else []):
            if not isinstance(raw, Mapping):
                continue
            source = raw.get("source")
            finding = raw.get("finding")
            if not isinstance(source, str) or not source.strip():
                continue
            normalized = evidence._normalize_source(source)
            if isinstance(finding, str) and finding.strip():
                findings_by_source.setdefault(normalized, []).append(finding.strip())
            origins_by_source.setdefault(normalized, []).append(
                f"execution.evidence:{index}"
            )
        for item in bundle["items"]:
            findings = list(dict.fromkeys(findings_by_source.get(item["source"], [])))
            origins = list(dict.fromkeys(origins_by_source.get(item["source"], [])))
            if len(findings) > 1:
                item["finding"] = " / ".join(findings)
            if len(origins) > 1:
                item["origin"] = ", ".join(origins)
        for requirement in bundle["requirements"]:
            if requirement["status"] in {"missing", "unverifiable"}:
                requirement["evidence_item_ids"] = []
        return evidence.validate_evidence_bundle(bundle)

    evidence._integrity_for_source = integrity_for_source
    evidence.build_evidence_bundle = build_evidence_bundle
    evidence._semantic_bundle_fix_applied = True


def set_workspace_root(evidence: Any, engine: Any) -> None:
    workspace = getattr(engine, "workspace", None)
    evidence._workspace_root = (
        Path(workspace).resolve() if workspace is not None else None
    )


def apply(contract_runtime: Any, evidence: Any | None = None) -> None:
    _patch_contract(contract_runtime.CONTRACT)
    _patch_enforcement(contract_runtime.ENFORCEMENT)
    _patch_contract_runtime(contract_runtime)
    if evidence is not None:
        _patch_evidence(evidence)
