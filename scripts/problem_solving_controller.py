#!/usr/bin/env python3
"""Run a domain-neutral PSOS controller with at most one material method change."""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Protocol


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os_contract_runtime as CONTRACT_RUNTIME


OS = CONTRACT_RUNTIME.OS
ROOT = SCRIPT_DIR.parent
CONTROLLER_REPLAN_SCHEMA_PATH = (
    ROOT / "schemas" / "problem-solving-controller-replan.schema.json"
)
MAX_METHOD_CHANGES = 1
MUTATING_ROUTES = {"CODE", "PROJECT"}
SINGLE_ROUTES = set(OS.SINGLE_ROUTES)
EXECUTION_OUTCOMES = {"completed", "partial", "blocked", "handoff"}


class ControllerError(OS.ProblemSolvingError):
    """Raised when the bounded controller cannot preserve its contract."""


class AttemptRunner(Protocol):
    def __call__(
        self,
        request: str,
        *,
        context_path: Path | None,
        output_root: Path,
        engine: Any,
        model_policy: dict[str, Any],
        run_id: str,
    ) -> tuple[Path, dict[str, Any]]: ...


class ReplanSelector(Protocol):
    def __call__(
        self,
        request: str,
        payload: dict[str, Any],
        attempt: dict[str, Any],
        *,
        engine: Any,
        policy: dict[str, Any],
        controller_dir: Path,
    ) -> dict[str, Any]: ...


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControllerError(f"{label}이 비어 있습니다.")
    return value.strip()


def _route_is_mutating(route_record: Mapping[str, Any]) -> bool:
    selected = route_record.get("selected_route")
    if selected in MUTATING_ROUTES:
        return True
    if selected == "HYBRID":
        return any(
            route_record.get(key) in MUTATING_ROUTES
            for key in ("primary_route", "secondary_route")
        )
    return False


def _has_side_effects(execution: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, dict) and item.get("action") in {"created", "modified"}
        for item in execution.get("artifacts", [])
    )


def _contract_status(payload: Mapping[str, Any]) -> tuple[str, list[str]]:
    record = payload.get("result_contract")
    if not isinstance(record, dict):
        return "not_applicable", []
    validation = record.get("validation")
    if not isinstance(validation, dict):
        return "unknown", []
    final = validation.get("final_assessment")
    if not isinstance(final, dict):
        return "unknown", []
    status = final.get("overall_status")
    if status not in {"satisfied", "missing", "unverifiable"}:
        status = "unknown"
    missing = final.get("missing_conditions", [])
    if not isinstance(missing, list):
        missing = []
    return status, [
        item.strip() for item in missing if isinstance(item, str) and item.strip()
    ]


def _attempt_outcome(execution_status: str, contract_status: str) -> str:
    if execution_status == "blocked_by_capability":
        return "blocked"
    if execution_status == "handoff":
        return "handoff"
    if execution_status == "completed" and contract_status in {
        "satisfied",
        "not_applicable",
    }:
        return "completed"
    return "partial"


def _attempt_score(
    outcome: str,
    contract_status: str,
    missing_conditions: list[str],
    *,
    route_matches_controller: bool,
) -> int:
    score = {
        "completed": 500,
        "partial": 250,
        "handoff": 100,
        "blocked": 0,
    }[outcome]
    score += {
        "satisfied": 80,
        "not_applicable": 60,
        "missing": 0,
        "unverifiable": -20,
        "unknown": -40,
    }[contract_status]
    score -= min(len(missing_conditions), 20) * 5
    if not route_matches_controller:
        score -= 1000
    return score


def summarize_attempt(
    attempt_number: int,
    run_dir: Path,
    payload: Mapping[str, Any],
    *,
    expected_route: str | None = None,
) -> dict[str, Any]:
    route_record = payload.get("route")
    execution = payload.get("execution")
    if not isinstance(route_record, dict) or not isinstance(execution, dict):
        raise ControllerError("PSOS attempt payload에 route 또는 execution이 없습니다.")
    execution_status = execution.get("status")
    if execution_status not in OS.EXECUTION_STATUSES:
        raise ControllerError(
            f"attempt execution.status가 올바르지 않습니다: {execution_status}"
        )
    route = route_record.get("selected_route")
    if route not in OS.ROUTES and not (
        route is None and execution_status == "blocked_by_capability"
    ):
        raise ControllerError(f"attempt route가 올바르지 않습니다: {route}")
    contract_status, missing_conditions = _contract_status(payload)
    route_matches = expected_route is None or route == expected_route
    if not route_matches:
        missing_conditions = [
            *missing_conditions,
            f"controller가 지정한 {expected_route} 대신 {route}가 선택됨",
        ]
    outcome = _attempt_outcome(execution_status, contract_status)
    side_effects = _has_side_effects(execution)
    mutating_route = _route_is_mutating(route_record)
    score = _attempt_score(
        outcome,
        contract_status,
        missing_conditions,
        route_matches_controller=route_matches,
    )
    return {
        "attempt": attempt_number,
        "run_path": str(run_dir),
        "route": route,
        "execution_status": execution_status,
        "contract_status": contract_status,
        "missing_conditions": missing_conditions,
        "side_effects": side_effects,
        "mutating_route": mutating_route,
        "route_matches_controller": route_matches,
        "score": score,
        "outcome": outcome,
    }


def can_change_method(attempt: Mapping[str, Any], used_changes: int) -> bool:
    if used_changes >= MAX_METHOD_CHANGES:
        return False
    if attempt.get("outcome") != "partial":
        return False
    if attempt.get("side_effects") or attempt.get("mutating_route"):
        return False
    return attempt.get("route") in OS.ROUTES


def build_replan_prompt(
    request: str,
    payload: Mapping[str, Any],
    attempt: Mapping[str, Any],
    capabilities: Any,
) -> str:
    current_route = attempt["route"]
    allowed = sorted(SINGLE_ROUTES - {current_route})
    return f"""당신은 Personal Problem-Solving OS의 bounded Controller다.

결과 자체를 다시 작성하지 말고, 첫 시도가 실제 완료 조건을 충족하지 못한 이유를 보고
물질적으로 다른 해결 방법을 딱 한 번 사용할 가치가 있는지만 결정한다.

[규칙]
1. decision은 change_method 또는 stop이다.
2. change_method라면 target_route는 현재 경로와 다른 단일 경로 하나여야 한다.
3. 한 번의 변경은 route, tool, information_source, interaction 중 한 차원만 바꾼다.
4. 같은 검색이나 같은 답변을 더 길게 반복하는 것은 변경이 아니다.
5. capability 부족처럼 경로를 바꿔도 해결되지 않으면 stop한다.
6. 사용자 목표·고정 조건·완료 조건은 바꾸지 않는다.
7. CODE나 PROJECT는 실제 파일 작업이 목표이고 승인된 write capability가 있을 때만 고른다.
8. HYBRID는 이번 bounded method change의 target으로 사용하지 않는다.

[허용 target_route]
{json.dumps(allowed, ensure_ascii=False)}

[현재 capability]
{json.dumps(asdict(capabilities), ensure_ascii=False, indent=2)}

[사용자 요청]
{request.strip()}

[Goal Ledger]
{json.dumps(payload.get("goal_ledger", {}), ensure_ascii=False, indent=2)}

[첫 시도 관찰]
{json.dumps(dict(attempt), ensure_ascii=False, indent=2)}
"""


def validate_replan_output(value: Any, current_route: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"replan"}:
        raise ControllerError("replan 최상위 형식이 올바르지 않습니다.")
    replan = value["replan"]
    required = {
        "decision",
        "target_route",
        "changed_dimension",
        "reason",
        "expected_gain",
    }
    if not isinstance(replan, dict) or set(replan) != required:
        raise ControllerError("replan 필드가 올바르지 않습니다.")
    decision = replan["decision"]
    if decision not in {"change_method", "stop"}:
        raise ControllerError("지원하지 않는 replan decision입니다.")
    reason = _text(replan["reason"], "replan.reason")
    expected_gain = _text(replan["expected_gain"], "replan.expected_gain")
    dimension = replan["changed_dimension"]
    if dimension not in {
        "route",
        "tool",
        "information_source",
        "interaction",
        "none",
    }:
        raise ControllerError("지원하지 않는 changed_dimension입니다.")
    target = replan["target_route"]
    if decision == "stop":
        if target is not None or dimension != "none":
            raise ControllerError(
                "stop은 target_route 없이 changed_dimension=none이어야 합니다."
            )
    else:
        if target not in SINGLE_ROUTES:
            raise ControllerError(
                "change_method target_route가 단일 PSOS 경로가 아닙니다."
            )
        if target == current_route:
            raise ControllerError("method change가 현재 route를 반복했습니다.")
        if dimension == "none":
            raise ControllerError(
                "change_method에는 실제 changed_dimension이 필요합니다."
            )
    return {
        "decision": decision,
        "target_route": target,
        "changed_dimension": dimension,
        "reason": reason,
        "expected_gain": expected_gain,
    }


def select_replan(
    request: str,
    payload: dict[str, Any],
    attempt: dict[str, Any],
    *,
    engine: Any,
    policy: dict[str, Any],
    controller_dir: Path,
) -> dict[str, Any]:
    base = policy["router_fallback"]
    profile = OS.ModelProfile(
        model=base.model,
        reasoning_effort=base.reasoning_effort,
        web_search=False,
        sandbox="read-only",
    )
    invocation = OS.InvocationSpec(
        name="controller-replan",
        phase="controller",
        route=None,
        profile=profile,
        schema_path=CONTROLLER_REPLAN_SCHEMA_PATH,
    )
    raw = engine.execute(
        build_replan_prompt(
            request,
            payload,
            attempt,
            engine.capabilities(),
        ),
        controller_dir,
        invocation,
    )
    result = validate_replan_output(raw, attempt["route"])
    if (
        result["decision"] == "change_method"
        and result["target_route"] in MUTATING_ROUTES
        and not engine.capabilities().workspace_write
    ):
        return {
            "decision": "stop",
            "target_route": None,
            "changed_dimension": "none",
            "reason": "쓰기 승인이 없어 CODE/PROJECT로 안전하게 전환할 수 없습니다.",
            "expected_gain": "현재 결과를 honest partial로 유지합니다.",
        }
    return result


def _controller_directive(
    original_context: str,
    payload: Mapping[str, Any],
    attempt: Mapping[str, Any],
    replan: Mapping[str, Any],
) -> str:
    directive = f"""[PSOS Controller method-change directive]

This block is an execution-control instruction, not a new user preference.
Preserve the original user goal, fixed constraints, and completion condition.
The previous attempt used {attempt["route"]} and remained incomplete.
For this one bounded retry, select exactly {replan["target_route"]} as the route.
Change only this material dimension: {replan["changed_dimension"]}.
Reason: {replan["reason"]}
Expected gain: {replan["expected_gain"]}
Do not repeat the previous method under a different explanation.

[Previous Goal Ledger]
{json.dumps(payload.get("goal_ledger", {}), ensure_ascii=False, indent=2)}

[Observed missing conditions]
{json.dumps(attempt.get("missing_conditions", []), ensure_ascii=False, indent=2)}
"""
    if original_context.strip():
        return original_context.rstrip() + "\n\n" + directive
    return directive


def _default_attempt_runner(
    request: str,
    *,
    context_path: Path | None,
    output_root: Path,
    engine: Any,
    model_policy: dict[str, Any],
    run_id: str,
) -> tuple[Path, dict[str, Any]]:
    return CONTRACT_RUNTIME.run_request(
        request,
        context_path=context_path,
        output_root=output_root,
        engine=engine,
        model_policy=model_policy,
        run_id=run_id,
    )


def _decision(
    *,
    after_attempt: int,
    action: str,
    target_route: str | None,
    changed_dimension: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "after_attempt": after_attempt,
        "action": action,
        "target_route": target_route,
        "changed_dimension": changed_dimension,
        "reason": reason,
    }


def _validate_state(state: Mapping[str, Any]) -> None:
    required = {
        "version",
        "controller_id",
        "request",
        "goal",
        "budget",
        "attempts",
        "decisions",
        "chosen_attempt",
        "outcome",
        "result_path",
    }
    if set(state) != required:
        raise ControllerError("controller state 최상위 필드가 올바르지 않습니다.")
    if state["version"] != 1:
        raise ControllerError("controller state version은 1이어야 합니다.")
    _text(state["controller_id"], "controller_id")
    _text(state["request"], "request")
    if state["outcome"] not in EXECUTION_OUTCOMES:
        raise ControllerError("controller outcome이 올바르지 않습니다.")
    attempts = state["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise ControllerError("controller attempts는 1~2개여야 합니다.")
    budget = state["budget"]
    if budget != {
        "max_method_changes": MAX_METHOD_CHANGES,
        "used_method_changes": len(attempts) - 1,
    }:
        raise ControllerError(
            "controller method-change budget 기록이 일치하지 않습니다."
        )
    if state["chosen_attempt"] not in {item["attempt"] for item in attempts}:
        raise ControllerError("chosen_attempt가 attempts에 없습니다.")
    _text(state["result_path"], "result_path")


def _write_state(controller_dir: Path, state: dict[str, Any]) -> None:
    _validate_state(state)
    OS.write_json(controller_dir / "controller_state.json", state)


def _choose_attempt(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    return max(attempts, key=lambda item: (item["score"], -item["attempt"]))


def run_controller_request(
    request: str,
    *,
    context_path: Path | None = None,
    output_root: Path = OS.RUNS_DIR,
    engine: Any,
    model_policy: dict[str, Any] | None = None,
    model_policy_path: Path = OS.DEFAULT_MODEL_POLICY_PATH,
    run_id: str | None = None,
    attempt_runner: AttemptRunner | None = None,
    replan_selector: ReplanSelector | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    cleaned_request = _text(request, "사용자 요청")
    chosen_id = run_id or (
        "controller-" + OS.make_run_id().removeprefix("psos-")
    )
    if not re.fullmatch(r"[A-Za-z0-9._-]+", chosen_id):
        raise ControllerError(
            "run-id는 영문자, 숫자, 점, 밑줄, 하이픈만 허용합니다."
        )
    controller_dir = output_root.expanduser().resolve() / chosen_id
    if controller_dir.exists():
        raise ControllerError(
            f"이미 존재하는 controller run-id입니다: {chosen_id}"
        )
    controller_dir.mkdir(parents=True)
    attempts_root = controller_dir / "attempts"
    attempts_root.mkdir()

    policy = model_policy or OS.load_model_policy(model_policy_path)
    runner = attempt_runner or _default_attempt_runner
    selector = replan_selector or select_replan

    run1_dir, payload1 = runner(
        cleaned_request,
        context_path=context_path,
        output_root=attempts_root,
        engine=engine,
        model_policy=policy,
        run_id="attempt-1",
    )
    attempt1 = summarize_attempt(1, run1_dir, payload1)
    attempts = [attempt1]
    payloads = {1: payload1}
    decisions: list[dict[str, Any]] = []

    if attempt1["outcome"] == "completed":
        decisions.append(
            _decision(
                after_attempt=1,
                action="finish",
                target_route=None,
                changed_dimension="none",
                reason="첫 시도가 완료 조건을 충족했습니다.",
            )
        )
    elif not can_change_method(attempt1, 0):
        decisions.append(
            _decision(
                after_attempt=1,
                action="stop_incomplete",
                target_route=None,
                changed_dimension="none",
                reason=(
                    "capability 차단, 파일 변경 가능성, 또는 mutating route 때문에 "
                    "자동 method change를 수행하지 않았습니다."
                ),
            )
        )
    else:
        try:
            replan = selector(
                cleaned_request,
                payload1,
                attempt1,
                engine=engine,
                policy=policy,
                controller_dir=controller_dir,
            )
            replan = validate_replan_output(
                {"replan": replan}, attempt1["route"]
            )
        except OS.ProblemSolvingError as exc:
            replan = {
                "decision": "stop",
                "target_route": None,
                "changed_dimension": "none",
                "reason": f"method-change 판단 실패: {exc}",
                "expected_gain": "첫 시도의 honest partial을 보존합니다.",
            }
        if replan["decision"] == "stop":
            decisions.append(
                _decision(
                    after_attempt=1,
                    action="stop_incomplete",
                    target_route=None,
                    changed_dimension="none",
                    reason=replan["reason"],
                )
            )
        else:
            decisions.append(
                _decision(
                    after_attempt=1,
                    action="change_method",
                    target_route=replan["target_route"],
                    changed_dimension=replan["changed_dimension"],
                    reason=replan["reason"],
                )
            )
            original_context, _ = OS.read_context(context_path)
            retry_context = _controller_directive(
                original_context,
                payload1,
                attempt1,
                replan,
            )
            retry_context_path = controller_dir / "attempt-2-context.md"
            retry_context_path.write_text(retry_context, encoding="utf-8")
            run2_dir, payload2 = runner(
                cleaned_request,
                context_path=retry_context_path,
                output_root=attempts_root,
                engine=engine,
                model_policy=policy,
                run_id="attempt-2",
            )
            attempt2 = summarize_attempt(
                2,
                run2_dir,
                payload2,
                expected_route=replan["target_route"],
            )
            attempts.append(attempt2)
            payloads[2] = payload2
            decisions.append(
                _decision(
                    after_attempt=2,
                    action=(
                        "finish"
                        if attempt2["outcome"] == "completed"
                        else "stop_incomplete"
                    ),
                    target_route=None,
                    changed_dimension="none",
                    reason=(
                        "변경한 방법이 완료 조건을 충족했습니다."
                        if attempt2["outcome"] == "completed"
                        else "허용된 한 번의 method change 후에도 완료 조건이 남았습니다."
                    ),
                )
            )

    chosen = _choose_attempt(attempts)
    chosen_payload = payloads[chosen["attempt"]]
    result_source = Path(chosen["run_path"]) / "result.md"
    if not result_source.is_file():
        raise ControllerError(
            f"선택된 attempt result.md가 없습니다: {result_source}"
        )
    result_path = controller_dir / "result.md"
    shutil.copyfile(result_source, result_path)

    ledger = chosen_payload.get("goal_ledger", {})
    goal = {
        "parent_goal": str(
            ledger.get("parent_goal", cleaned_request)
        ).strip(),
        "fixed_constraints": [
            item.strip()
            for item in ledger.get("fixed_constraints", [])
            if isinstance(item, str) and item.strip()
        ],
        "completion_condition": str(
            ledger.get(
                "completion_condition",
                "사용자 요청에 맞는 실제 결과",
            )
        ).strip(),
    }
    state = {
        "version": 1,
        "controller_id": chosen_id,
        "request": cleaned_request,
        "goal": goal,
        "budget": {
            "max_method_changes": MAX_METHOD_CHANGES,
            "used_method_changes": len(attempts) - 1,
        },
        "attempts": attempts,
        "decisions": decisions,
        "chosen_attempt": chosen["attempt"],
        "outcome": chosen["outcome"],
        "result_path": str(result_path),
    }
    _write_state(controller_dir, state)
    return controller_dir, chosen_payload, state


def build_parser():
    parser = OS.build_parser()
    parser.description = __doc__
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
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
        controller_dir, _payload, state = run_controller_request(
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

    print((controller_dir / "result.md").read_text(encoding="utf-8").rstrip())
    print(f"\nController 기록: {controller_dir}")
    if state["outcome"] == "blocked":
        return 2
    if state["outcome"] in {"partial", "handoff"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
