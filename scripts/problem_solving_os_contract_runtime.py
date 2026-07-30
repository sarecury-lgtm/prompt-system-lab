#!/usr/bin/env python3
"""Run canonical PSOS with an AI-compiled request-specific Result Contract.

The adapter wraps the canonical runtime instead of copying its orchestration. After
an accepted router result, it skips trivial DIRECT requests, asks a bounded contract
compiler to turn the request and Goal Ledger into observable completion conditions,
persists ``result_contract.json``, appends the contract to executor prompts, and
anchors the contract path and hash in the run record.

Contract enforcement and focused repair remain Phase B concerns. This adapter
establishes contract compilation, persistence, and prompt delivery without changing
the canonical backup, receipt, rollback, or model-policy lifecycle.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Protocol, Sequence


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os.py"
CONTRACT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_contract.py"
CONTRACT_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-result-contract.schema.json"


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
        return self.delegate.execute(prompt, run_dir, invocation)

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
            "enforcement": "prompt_only_phase_a",
        }


def _attach_contract_record(
    run_dir: Path,
    payload: dict[str, Any],
    record: dict[str, Any] | None,
) -> None:
    if record is None:
        return
    payload["result_contract"] = record
    run_record = payload.get("run")
    if isinstance(run_record, dict):
        run_record["result_contract"] = record

    route_path = run_dir / "route.json"
    route_record = json.loads(route_path.read_text(encoding="utf-8"))
    route_record["result_contract"] = record
    if isinstance(route_record.get("run"), dict):
        route_record["run"]["result_contract"] = record
    OS.write_json(route_path, route_record)


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
    _attach_contract_record(run_dir, payload, wrapped.contract_record())
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
