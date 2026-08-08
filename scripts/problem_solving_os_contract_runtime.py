#!/usr/bin/env python3
"""Run canonical PSOS with an AI-compiled and enforced Result Contract."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Protocol, Sequence

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os.py"
CONTRACT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_contract.py"
ENFORCEMENT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_contract_enforcement.py"
LIVE_BROWSER_PATH = ROOT / "scripts" / "problem_solving_live_browser.py"
CONTRACT_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-result-contract.schema.json"
ASSESSMENT_SCHEMA_PATH = (
    ROOT / "schemas" / "problem-solving-os-result-contract-assessment.schema.json"
)


def _load_local_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = _load_local_module("psos_canonical_runtime", CANONICAL_RUNTIME_PATH)
CONTRACT = _load_local_module("psos_result_contract_runtime", CONTRACT_RUNTIME_PATH)
ENFORCEMENT = _load_local_module(
    "psos_result_contract_enforcement_runtime",
    ENFORCEMENT_RUNTIME_PATH,
)
LIVE_BROWSER = _load_local_module("psos_live_browser_runtime", LIVE_BROWSER_PATH)


class CompatibleEngine(Protocol):
    def capabilities(self) -> Any: ...

    def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]: ...

    def trace(self) -> list[dict[str, Any]]: ...


def _deduplicated_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in values if isinstance(values, (list, tuple)) else []:
        if isinstance(value, str) and value.strip() and value.strip() not in result:
            result.append(value.strip())
    return result


def build_contract_prompt(
    request: str,
    router_payload: dict[str, Any],
) -> str:
    """Build a domain-neutral prompt for a bounded Result Contract compiler."""

    route = router_payload["route"]
    ledger = router_payload["goal_ledger"]
    return f"""당신은 Personal Problem-Solving OS의 Result Contract 컴파일러다.

사용자 답변이나 조사 결과를 만들지 않는다. 승인된 Goal Ledger와 route를 바탕으로,
이번 결과가 실제 사용자 결과로 인정되기 위한 관찰 가능한 완료 조건만 JSON으로 만든다.

[핵심 원칙]
1. must_preserve에는 Goal Ledger의 fixed_constraints를 같은 순서와 문구로 정확히 복사한다.
   새 취향, 새 목표, 새 제약을 추가하지 않는다.
2. required_outputs의 첫 항목은 반드시 다음과 같다.
   - id: goal-completion
   - description: Goal Ledger의 completion_condition을 정확히 복사
   - verification: 선택된 결과를 실제로 확인할 가장 직접적인 방식
3. 사용자가 명시적으로 요구했거나 목표 달성에 필수인 산출물만 추가한다.
   보기 좋은 표, 임의 점수, 과도한 후보 수처럼 없어도 되는 형식은 요구하지 않는다.
4. verification은 text, evidence, url, artifact, receipt, visual 중 하나만 사용한다.
5. RESEARCH에서는 결론과 출처가 연결돼야 한다. 현재 구매·예약·신청 가능한 구체적
   대상을 고르는 요청이라면 대상 식별, 직접 대상 URL, 확인 시점의 상태, 비용·조건,
   사용자 판단 기준별 근거처럼 거래 가능한 수준의 항목을 요구한다.
   웹 검색 결과나 캐시된 페이지는 실시간 판매 상태를 증명하지 못한다. 실제 브라우저에서
   현재 구매·재고·주문 UI를 확인하지 못한 경우에는 완료 조건을 충족한 것으로 간주하지 않는다.
6. 기존 산출물을 수정하는 요청이라면 피드백 설명이 아니라 실제 수정된 전체본과
   변경 요구의 반영을 요구한다.
7. 파일·코드 작업은 실제 artifact와 receipt로 확인할 항목을 요구한다.
8. 외관, 상태, 단면, 손상, 실착처럼 시각 정보가 판단을 바꾸면 visual 검증과
   user_review.evidence_types의 image를 사용한다. 단지 이미지가 있으면 좋다는 이유로
   시각 검토를 강제하지 않는다.
9. minimum_sources는 요청에 필요한 최소치만 0~8 범위에서 정한다. 임의의 고정 숫자를
   모든 조사에 반복하지 않는다.
10. 조건을 충족하지 못해도 억지 우승자를 내면 안 되는 선택 요청은 no_winner,
    capability나 실제 artifact가 없으면 완료할 수 없는 요청은 blocked,
    나머지는 partial을 사용한다.
11. required_outputs는 goal-completion을 포함해 최대 12개다.
12. route와 result_type은 승인된 route에 정확히 맞춘다.

[승인된 route]
{json.dumps(route, ensure_ascii=False, indent=2)}

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[사용자 요청]
{request.strip()}
"""


def validate_compiled_contract(
    payload: dict[str, Any],
    router_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate structure and bind an AI-generated contract to the accepted ledger."""

    validated = CONTRACT.validate_result_contract(payload)
    route = router_payload["route"]["selected_route"]
    ledger = router_payload["goal_ledger"]
    if validated["route"] != route:
        raise CONTRACT.ResultContractError("compiled contract route does not match router")
    expected_constraints = _deduplicated_strings(ledger.get("fixed_constraints"))
    if validated["must_preserve"] != expected_constraints:
        raise CONTRACT.ResultContractError(
            "compiled contract must_preserve does not exactly match fixed_constraints"
        )
    completion = ledger.get("completion_condition")
    goal_outputs = [
        item for item in validated["required_outputs"] if item["id"] == "goal-completion"
    ]
    if len(goal_outputs) != 1 or goal_outputs[0]["description"] != completion:
        raise CONTRACT.ResultContractError(
            "compiled contract must preserve the exact goal completion condition"
        )
    if len(validated["required_outputs"]) > 12:
        raise CONTRACT.ResultContractError("compiled contract has too many required outputs")
    evidence = validated["evidence_requirements"]
    if evidence["minimum_sources"] > 8:
        raise CONTRACT.ResultContractError("compiled contract requires too many sources")
    if len(evidence["source_roles"]) > 8:
        raise CONTRACT.ResultContractError("compiled contract has too many source roles")
    completion_text = " ".join(
        [
            str(ledger.get("completion_condition", "")),
            *expected_constraints,
        ]
    )
    explicit_collection = bool(
        re.search(r"(?:최소\s*)?\d+\s*개|\d+\s*개\s*이상", completion_text)
        or re.search(
            r"\bat\s+least\s+\d+\b|\b\d+\s+(?:items|products|options|results)\b",
            completion_text,
            re.IGNORECASE,
        )
    )
    if explicit_collection and validated["failure_policy"] == "no_winner":
        validated["failure_policy"] = "partial"
    return validated


def _read_only_profile(profile: Any) -> Any:
    return OS.ModelProfile(
        model=profile.model,
        reasoning_effort=profile.reasoning_effort,
        web_search=False,
        sandbox="read-only",
    )


def contract_profiles(policy: dict[str, Any]) -> tuple[Any, ...]:
    """Return bounded primary/fallback profiles without duplicate model settings."""

    candidates = [
        _read_only_profile(policy["router"]),
        _read_only_profile(policy["router_fallback"]),
    ]
    unique: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for profile in candidates:
        key = (profile.model, profile.reasoning_effort)
        if key not in seen:
            seen.add(key)
            unique.append(profile)
    return tuple(unique)


class ContractAwareEngine:
    """Compile and inject a validated router-derived contract before execution."""

    def __init__(
        self,
        delegate: CompatibleEngine,
        *,
        request: str,
        profiles: Sequence[Any],
    ) -> None:
        self.delegate = delegate
        self.request = request.strip()
        self.profiles = tuple(profiles)
        self._router_payload: dict[str, Any] | None = None
        self._contract_payload: dict[str, Any] | None = None
        self._contract_path: Path | None = None
        self._contract_sha256: str | None = None
        self._contract_attempted = False
        self._contract_generation = "not_attempted"
        self._contract_trace: list[dict[str, Any]] = []

    def capabilities(self) -> Any:
        return self.delegate.capabilities()

    def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]:
        if invocation.phase == "router":
            result = self.delegate.execute(prompt, run_dir, invocation)
            try:
                self._router_payload = OS.validate_route_output(copy.deepcopy(result))
            except OS.ProblemSolvingError:
                self._router_payload = None
            return result

        self._ensure_contract(run_dir)
        if self._contract_payload is not None:
            prompt = (
                prompt.rstrip()
                + "\n\n[Result Contract]\n"
                + "아래 계약은 이번 실행이 사용자 결과로 인정되기 위한 필수 조건이다. "
                + "결과와 근거를 만들 때 각 항목을 빠뜨리지 말고, 충족할 수 없는 항목은 "
                + "완료로 꾸미지 말고 limitation과 상태에 반영한다.\n"
                + json.dumps(self._contract_payload, ensure_ascii=False, indent=2)
                + "\n"
            )
        result = self.delegate.execute(prompt, run_dir, invocation)
        if (
            invocation.phase in {"executor", "repair"}
            and self._contract_payload is not None
            and contract_requires_live_transaction(self._contract_payload)
            and getattr(self.capabilities(), "live_browser", False)
        ):
            result = LIVE_BROWSER.verify_execution(
                result,
                run_dir,
                invocation.name,
                chrome_path=LIVE_BROWSER.find_chrome(),
                require_available=contract_requires_available_transaction(
                    self._contract_payload
                ),
            )
        return result

    def trace(self) -> list[dict[str, Any]]:
        return self.delegate.trace()

    def _ensure_contract(self, run_dir: Path) -> None:
        if self._contract_attempted:
            return
        self._contract_attempted = True
        if self._router_payload is None:
            return

        try:
            minimal = CONTRACT.build_result_contract(
                self._router_payload["route"],
                self._router_payload["goal_ledger"],
            )
        except CONTRACT.ResultContractError as exc:
            raise OS.ProblemSolvingError(f"Result Contract 기반 생성 실패: {exc}") from exc
        if minimal is None:
            self._contract_generation = "skipped_simple_direct"
            return

        contract_prompt = build_contract_prompt(self.request, self._router_payload)
        compiled: dict[str, Any] | None = None
        for index, profile in enumerate(self.profiles):
            invocation = OS.InvocationSpec(
                name="result-contract" if index == 0 else f"result-contract-fallback-{index}",
                phase="contract",
                route=None,
                profile=profile,
                schema_path=CONTRACT_SCHEMA_PATH,
            )
            try:
                candidate = self.delegate.execute(contract_prompt, run_dir, invocation)
                compiled = validate_compiled_contract(candidate, self._router_payload)
            except (OS.ProblemSolvingError, CONTRACT.ResultContractError) as exc:
                self._contract_trace.append(
                    {
                        "name": invocation.name,
                        "model": profile.model,
                        "reasoning_effort": profile.reasoning_effort,
                        "outcome": "rejected",
                        "error": str(exc),
                    }
                )
                continue
            self._contract_trace.append(
                {
                    "name": invocation.name,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "accepted",
                }
            )
            self._contract_generation = "model_compiled"
            break

        if compiled is None:
            compiled = validate_compiled_contract(
                minimal.to_dict(),
                self._router_payload,
            )
            self._contract_generation = "minimal_fallback"

        contract = CONTRACT.ResultContract(
            version=compiled["version"],
            route=compiled["route"],
            result_type=compiled["result_type"],
            must_preserve=tuple(compiled["must_preserve"]),
            required_outputs=tuple(
                CONTRACT.RequiredOutput(**item) for item in compiled["required_outputs"]
            ),
            evidence_requirements=CONTRACT.EvidenceRequirements(
                minimum_sources=compiled["evidence_requirements"]["minimum_sources"],
                source_roles=tuple(compiled["evidence_requirements"]["source_roles"]),
                claim_source_mapping=compiled["evidence_requirements"]["claim_source_mapping"],
            ),
            user_review=CONTRACT.UserReview(
                needed=compiled["user_review"]["needed"],
                evidence_types=tuple(compiled["user_review"]["evidence_types"]),
            ),
            failure_policy=compiled["failure_policy"],
        )
        path = CONTRACT.write_result_contract(run_dir, contract)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self._contract_payload = compiled
        self._contract_path = path
        self._contract_sha256 = digest

    def contract_payload(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._contract_payload)

    def contract_record(self) -> dict[str, Any] | None:
        if (
            self._contract_payload is None
            or self._contract_path is None
            or self._contract_sha256 is None
        ):
            return None
        return {
            "version": self._contract_payload["version"],
            "path": self._contract_path.name,
            "sha256": self._contract_sha256,
            "route": self._contract_payload["route"],
            "result_type": self._contract_payload["result_type"],
            "delivered_to_executor": True,
            "generation": self._contract_generation,
            "generation_trace": copy.deepcopy(self._contract_trace),
            "enforcement": "pending_phase_b",
        }


def _assessment_name(label: str, index: int) -> str:
    base = "result-contract-assessment"
    if label:
        base += f"-{label}"
    return base if index == 0 else f"{base}-fallback-{index}"


LIVE_TRANSACTION_PATTERN = re.compile(
    r"현재\s*(?:구매|판매|주문|예약)\s*(?:가능|여부|상태)|"
    r"(?:판매|구매|주문|예약)\s*(?:가능\s*)?(?:여부|상태)|"
    r"재고|품절|결제\s*(?:가능|버튼)|"
    r"\b(?:currently available|available to buy|in stock|sold out|purchase status)\b",
    re.IGNORECASE,
)
LIVE_BROWSER_EVIDENCE_PATTERN = re.compile(
    r"\[LIVE_BROWSER\]\s+url=(\S+)\s+status=(available|sold_out|unknown)\b"
)
AVAILABLE_TRANSACTION_PATTERN = re.compile(
    r"(?:현재\s*)?(?:구매|판매|주문|예약)\s*가능(?:한|해야|함|상품|대상)|"
    r"\b(?:currently available|available to buy|in-stock)\s+(?:item|product|listing)s?\b",
    re.IGNORECASE,
)


def contract_requires_live_transaction(contract: dict[str, Any]) -> bool:
    texts = [
        *contract.get("must_preserve", []),
        *[
            item.get("description", "")
            for item in contract.get("required_outputs", [])
            if isinstance(item, dict)
        ],
    ]
    return contract.get("route") == "RESEARCH" and any(
        isinstance(value, str) and LIVE_TRANSACTION_PATTERN.search(value)
        for value in texts
    )


def contract_requires_available_transaction(contract: dict[str, Any]) -> bool:
    texts = [
        *contract.get("must_preserve", []),
        *[
            item.get("description", "")
            for item in contract.get("required_outputs", [])
            if isinstance(item, dict)
        ],
    ]
    return any(
        isinstance(value, str) and AVAILABLE_TRANSACTION_PATTERN.search(value)
        for value in texts
    )


def enforce_live_transaction_capability(
    assessment: dict[str, Any],
    contract: dict[str, Any],
    capabilities: Any,
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Reject cached-search claims of live transaction availability."""

    if not contract_requires_live_transaction(contract):
        return assessment

    live_browser = getattr(capabilities, "live_browser", False)
    statuses: list[tuple[str, str]] = []
    for evidence in execution.get("evidence", []):
        finding_text = evidence.get("finding", "") if isinstance(evidence, dict) else ""
        match = LIVE_BROWSER_EVIDENCE_PATTERN.search(str(finding_text))
        if match:
            statuses.append((match.group(1), match.group(2)))

    if not live_browser:
        finding = (
            "웹 검색·캐시 페이지는 현재 판매 상태를 증명하지 못합니다. "
            "실시간 브라우저에서 구매·재고·주문 UI 확인이 필요합니다."
        )
    elif not statuses:
        finding = "현재 판매 상태를 확인한 실시간 브라우저 영수증이 없습니다."
    else:
        require_available = contract_requires_available_transaction(contract)
        invalid = [
            (url, status)
            for url, status in statuses
            if status == "unknown" or (require_available and status == "sold_out")
        ]
        if not invalid:
            return assessment
        finding = "실시간 브라우저 검증 미통과: " + "; ".join(
            f"{url}={status}" for url, status in invalid
        )

    result = copy.deepcopy(assessment)
    descriptions = {
        item["id"]: item["description"] for item in contract["required_outputs"]
    }
    affected: list[str] = []
    for item in result["requirements"]:
        description = descriptions.get(item["id"], "")
        if item["id"] == "goal-completion" or LIVE_TRANSACTION_PATTERN.search(
            description
        ):
            item["status"] = "unverifiable"
            item["finding"] = finding
            item["evidence_refs"] = []
            affected.append(item["id"])
    if not affected:
        return result

    result["overall_status"] = "missing"
    result["missing_requirement_ids"] = list(
        dict.fromkeys([*result["missing_requirement_ids"], *affected])
    )
    result["missing_conditions"] = list(
        dict.fromkeys([*result["missing_conditions"], finding])
    )
    result["evidence_check"] = {
        "status": "unverifiable",
        "finding": finding,
    }
    return result


def assess_execution(
    engine: CompatibleEngine,
    profiles: Sequence[Any],
    run_dir: Path,
    contract: dict[str, Any],
    contract_sha256: str,
    execution: dict[str, Any],
    *,
    label: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    observations = ENFORCEMENT.collect_observations(run_dir, execution)
    prompt = ENFORCEMENT.build_assessment_prompt(
        contract,
        contract_sha256,
        execution,
        observations,
    )
    trace: list[dict[str, Any]] = []
    assessment: dict[str, Any] | None = None
    generation = "model_assessed"
    last_error = ""
    for index, profile in enumerate(profiles):
        invocation = OS.InvocationSpec(
            name=_assessment_name(label, index),
            phase="assessment",
            route=None,
            profile=profile,
            schema_path=ASSESSMENT_SCHEMA_PATH,
        )
        try:
            candidate = engine.execute(prompt, run_dir, invocation)
            assessment = ENFORCEMENT.validate_assessment(
                candidate,
                contract,
                contract_sha256,
                observations,
            )
        except (OS.ProblemSolvingError, ENFORCEMENT.ContractEnforcementError) as exc:
            last_error = str(exc)
            trace.append(
                {
                    "name": invocation.name,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "rejected",
                    "error": last_error,
                }
            )
            continue
        trace.append(
            {
                "name": invocation.name,
                "model": profile.model,
                "reasoning_effort": profile.reasoning_effort,
                "outcome": "accepted",
            }
        )
        break

    if assessment is None:
        generation = "deterministic_fallback"
        assessment = ENFORCEMENT.deterministic_fallback_assessment(
            contract,
            contract_sha256,
            observations,
            last_error or "계약 검증 모델이 유효한 판정을 반환하지 못했습니다.",
        )

    assessment = enforce_live_transaction_capability(
        assessment,
        contract,
        engine.capabilities(),
        execution,
    )

    suffix = f"-{label}" if label else ""
    path = ENFORCEMENT.write_json_atomic(
        run_dir / f"result_contract_assessment{suffix}.json",
        assessment,
    )
    record = {
        "path": path.name,
        "sha256": ENFORCEMENT.sha256_file(path),
        "generation": generation,
        "trace": trace,
        "overall_status": assessment["overall_status"],
        "missing_requirement_ids": assessment["missing_requirement_ids"],
        "missing_conditions": assessment["missing_conditions"],
        "observations": observations,
    }
    return assessment, record


def _repair_target(
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[str, Any] | None:
    route_record = payload["route"]
    selected = route_record["selected_route"]
    if selected == "HYBRID":
        routes = [route_record["primary_route"], route_record["secondary_route"]]
        if any(route in {"CODE", "PROJECT"} for route in routes):
            return None
        repair_route = route_record["secondary_route"]
    else:
        if selected in {"CODE", "PROJECT"}:
            return None
        repair_route = selected
    if repair_route not in OS.SINGLE_ROUTES:
        return None
    route_policy = policy["routes"][repair_route]
    profile = route_policy["fallback"] or route_policy["primary"]
    return repair_route, profile


def _persist_runtime_state(
    run_dir: Path,
    payload: dict[str, Any],
    engine: CompatibleEngine,
) -> None:
    run_record = payload.get("run")
    if isinstance(run_record, dict):
        run_record["engine_trace"] = engine.trace()

    route_path = run_dir / "route.json"
    route_record = json.loads(route_path.read_text(encoding="utf-8"))
    execution = payload["execution"]
    route_record.update(
        {
            "execution_status": execution["status"],
            "capabilities_used": execution["capabilities_used"],
            "needed_capability": execution["needed_capability"],
            "handoff": execution["handoff"],
            "artifacts": execution["artifacts"],
            "evidence": execution["evidence"],
            "limitations": execution["limitations"],
            "run": payload["run"],
        }
    )
    if "result_contract" in payload:
        route_record["result_contract"] = payload["result_contract"]
    OS.write_json(route_path, route_record)
    (run_dir / "result.md").write_text(OS.result_markdown(payload), encoding="utf-8")


def enforce_result_contract(
    request: str,
    run_dir: Path,
    payload: dict[str, Any],
    engine: CompatibleEngine,
    policy: dict[str, Any],
    contract: dict[str, Any],
    record: dict[str, Any],
) -> None:
    validation: dict[str, Any] = {
        "version": 1,
        "initial_assessment": None,
        "repair_allowed": False,
        "repair_attempted": False,
        "repair": None,
        "final_assessment": None,
        "outcome": "not_assessed",
    }
    execution = payload["execution"]
    if execution["status"] in {"blocked_by_capability", "handoff"}:
        validation["outcome"] = "skipped_non_completed"
        record["enforcement"] = "validated_phase_b"
        record["validation"] = validation
        return

    initial, initial_record = assess_execution(
        engine,
        contract_profiles(policy),
        run_dir,
        contract,
        record["sha256"],
        execution,
    )
    validation["initial_assessment"] = initial_record
    if initial["overall_status"] == "satisfied":
        validation["final_assessment"] = initial_record
        validation["outcome"] = (
            "satisfied_initially"
            if execution["status"] == "completed"
            else "satisfied_but_partial"
        )
        record["enforcement"] = "validated_phase_b"
        record["validation"] = validation
        return

    ENFORCEMENT.write_json_atomic(
        run_dir / "result_contract_original_execution.json",
        {"execution": execution},
    )
    repair_target = (
        None
        if contract_requires_live_transaction(contract)
        and not getattr(engine.capabilities(), "live_browser", False)
        else _repair_target(payload, policy)
    )
    validation["repair_allowed"] = repair_target is not None
    candidate_execution = execution
    final_assessment = initial
    final_record = initial_record

    if repair_target is not None:
        validation["repair_attempted"] = True
        repair_route, repair_profile = repair_target
        repair_prompt = ENFORCEMENT.build_repair_prompt(
            request,
            payload["goal_ledger"],
            contract,
            initial,
            execution,
        )
        repair_invocation = OS.InvocationSpec(
            name="result-contract-repair",
            phase="repair",
            route=repair_route,
            profile=repair_profile,
            schema_path=OS.EXECUTION_SCHEMA_PATH,
        )
        repair_record: dict[str, Any] = {
            "route": repair_route,
            "model": repair_profile.model,
            "reasoning_effort": repair_profile.reasoning_effort,
            "outcome": "failed",
        }
        try:
            repair_payload = engine.execute(repair_prompt, run_dir, repair_invocation)
            if (
                contract_requires_live_transaction(contract)
                and getattr(engine.capabilities(), "live_browser", False)
            ):
                repair_payload = LIVE_BROWSER.verify_execution(
                    repair_payload,
                    run_dir,
                    repair_invocation.name,
                    chrome_path=LIVE_BROWSER.find_chrome(),
                    require_available=contract_requires_available_transaction(contract),
                )
            candidate_execution = OS.validate_execution_output(
                copy.deepcopy(repair_payload),
                repair_route,
                repair_profile,
                engine.capabilities(),
            )
            repair_record["outcome"] = "completed"
            repaired_assessment, repaired_record = assess_execution(
                engine,
                contract_profiles(policy),
                run_dir,
                contract,
                record["sha256"],
                candidate_execution,
                label="after-repair",
            )
            final_assessment = repaired_assessment
            final_record = repaired_record
        except (OS.ProblemSolvingError, ENFORCEMENT.ContractEnforcementError) as exc:
            repair_record["error"] = str(exc)
        validation["repair"] = repair_record

    validation["final_assessment"] = final_record
    if (
        validation["repair_attempted"]
        and validation["repair"]
        and validation["repair"]["outcome"] == "completed"
        and final_assessment["overall_status"] == "satisfied"
        and candidate_execution["status"] == "completed"
    ):
        payload["execution"] = candidate_execution
        validation["outcome"] = "satisfied_after_repair"
    else:
        payload["execution"] = ENFORCEMENT.apply_failure_policy(
            candidate_execution,
            contract,
            final_assessment,
        )
        validation["outcome"] = (
            "downgraded_after_repair"
            if validation["repair_attempted"]
            else "downgraded_without_repair"
        )

    record["enforcement"] = "validated_phase_b"
    record["validation"] = validation


def run_request(
    request: str,
    *,
    context_path: Path | None = None,
    output_root: Path = OS.RUNS_DIR,
    engine: CompatibleEngine,
    model_policy: dict[str, Any] | None = None,
    model_policy_path: Path = OS.DEFAULT_MODEL_POLICY_PATH,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    policy = model_policy or OS.load_model_policy(model_policy_path)
    wrapped = ContractAwareEngine(
        engine,
        request=request,
        profiles=contract_profiles(policy),
    )
    run_dir, payload = OS.run_request(
        request,
        context_path=context_path,
        output_root=output_root,
        engine=wrapped,
        model_policy=policy,
        model_policy_path=model_policy_path,
        run_id=run_id,
    )
    contract = wrapped.contract_payload()
    record = wrapped.contract_record()
    if contract is not None and record is not None:
        payload["result_contract"] = record
        enforce_result_contract(
            request,
            run_dir,
            payload,
            engine,
            policy,
            contract,
            record,
        )
    _persist_runtime_state(run_dir, payload, engine)
    return run_dir, payload


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = OS.build_parser().parse_args(argv)
    if args.allow_workspace_write and not args.write_scope:
        print(
            "ERROR: --allow-workspace-write에는 --write-scope가 하나 이상 필요합니다.",
            file=sys.stderr,
        )
        return 1
    if args.write_scope and not args.allow_workspace_write:
        print(
            "ERROR: --write-scope는 --allow-workspace-write와 함께 사용해야 합니다.",
            file=sys.stderr,
        )
        return 1

    allowed_write_paths: list[str] | None = None
    write_approval: dict[str, Any] | None = None
    if args.allow_workspace_write:
        try:
            allowed_write_paths, write_approval = OS.build_cli_write_approval(
                args.workspace,
                args.request,
                args.write_scope,
            )
        except OS.ProblemSolvingError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    engine = OS.CodexEngine(
        args.workspace,
        allow_workspace_write=args.allow_workspace_write,
        allowed_write_paths=allowed_write_paths,
        write_approval=write_approval,
        enable_search=not args.no_search,
    )
    try:
        run_dir, payload = run_request(
            args.request,
            context_path=args.context_file,
            output_root=args.runs_dir,
            engine=engine,
            model_policy_path=args.model_policy,
            run_id=args.run_id,
        )
    except OS.ProblemSolvingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print((run_dir / "result.md").read_text(encoding="utf-8").rstrip())
    print(f"\n실행 기록: {run_dir}")
    return 2 if payload["execution"]["status"] == "blocked_by_capability" else 0


if __name__ == "__main__":
    raise SystemExit(main())
