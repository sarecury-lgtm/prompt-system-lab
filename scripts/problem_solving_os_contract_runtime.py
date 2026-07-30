#!/usr/bin/env python3
"""Run canonical PSOS with a request-specific Result Contract.

This integration adapter deliberately wraps the canonical runtime instead of
copying its orchestration. It observes the accepted router result, builds and
persists ``result_contract.json`` before the first executor call, appends the
contract to executor prompts, and anchors the contract path and hash in the run
record.

Contract enforcement and focused repair are Phase B concerns. This adapter only
establishes the Phase A generation, persistence, and prompt-delivery boundary.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os.py"
CONTRACT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_contract.py"


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


class ContractAwareEngine:
    """Inject a validated router-derived contract before executor invocations."""

    def __init__(self, delegate: CompatibleEngine) -> None:
        self.delegate = delegate
        self._router_payload: dict[str, Any] | None = None
        self._contract_payload: dict[str, Any] | None = None
        self._contract_path: Path | None = None
        self._contract_sha256: str | None = None
        self._contract_attempted = False

    def capabilities(self) -> Any:
        return self.delegate.capabilities()

    def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]:
        if invocation.phase == "router":
            result = self.delegate.execute(prompt, run_dir, invocation)
            try:
                self._router_payload = OS.validate_route_output(copy.deepcopy(result))
            except OS.ProblemSolvingError:
                # The canonical router fallback owns invalid-router recovery.
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
            contract = CONTRACT.build_result_contract(
                self._router_payload["route"],
                self._router_payload["goal_ledger"],
            )
        except CONTRACT.ResultContractError as exc:
            raise OS.ProblemSolvingError(f"Result Contract 생성 실패: {exc}") from exc
        if contract is None:
            return
        path = CONTRACT.write_result_contract(run_dir, contract)
        payload = CONTRACT.validate_result_contract(contract.to_dict())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self._contract_payload = payload
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
    wrapped = ContractAwareEngine(engine)
    run_dir, payload = OS.run_request(
        request,
        context_path=context_path,
        output_root=output_root,
        engine=wrapped,
        model_policy=model_policy,
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
