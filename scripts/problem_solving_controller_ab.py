#!/usr/bin/env python3
"""Prepare and run a low-waste blind A/B evaluation of PSOS baseline vs Controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import problem_solving_controller as CONTROLLER
    import problem_solving_os_contract_runtime as BASELINE
except ImportError:  # pragma: no cover - allows standalone syntax checks
    CONTROLLER = None
    BASELINE = None


ROOT = SCRIPT_DIR.parent
DEFAULT_CASES_PATH = ROOT / "evaluation" / "psos-controller" / "eval_cases.json"
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "controller-ab"
ARM_NAMES = ("baseline", "controller")
ALLOWED_ROUTES = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT", "HYBRID"}
CASE_FIELDS = {
    "id",
    "domain",
    "stage",
    "request",
    "context",
    "expected_primary_route",
    "requires_live_web",
    "workspace_fixture",
    "allow_workspace_write",
    "write_scopes",
    "must_preserve",
    "observable_completion",
    "critical_failures",
}


class EvaluationError(ValueError):
    """Raised when an evaluation package would be unsafe or non-comparable."""


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label}이 비어 있습니다.")
    return value.strip()


def _strings(value: Any, label: str, *, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise EvaluationError(f"{label}은 문자열 배열이어야 합니다.")
    cleaned = [item.strip() for item in value]
    if len(cleaned) < minimum:
        raise EvaluationError(f"{label}은 최소 {minimum}개여야 합니다.")
    if len(set(cleaned)) != len(cleaned):
        raise EvaluationError(f"{label}에 중복이 있습니다.")
    return cleaned


def validate_suite(payload: Any, *, root: Path = ROOT) -> dict[str, Any]:
    required = {"version", "purpose", "pilot_policy", "review_rubric", "cases"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise EvaluationError("evaluation suite 최상위 형식이 올바르지 않습니다.")
    if payload["version"] != 1:
        raise EvaluationError("evaluation suite version은 1이어야 합니다.")
    _text(payload["purpose"], "purpose")

    pilot = payload["pilot_policy"]
    if not isinstance(pilot, dict) or set(pilot) != {
        "default_case_ids",
        "maximum_live_cases_without_override",
        "stop_after_pilot_when",
    }:
        raise EvaluationError("pilot_policy 형식이 올바르지 않습니다.")
    default_ids = _strings(pilot["default_case_ids"], "default_case_ids", minimum=1)
    maximum = pilot["maximum_live_cases_without_override"]
    if not isinstance(maximum, int) or not 1 <= maximum <= 2:
        raise EvaluationError("기본 live pilot은 최대 2개 사례만 허용합니다.")
    if len(default_ids) > maximum:
        raise EvaluationError("default_case_ids가 기본 live pilot 한도를 넘습니다.")
    _strings(pilot["stop_after_pilot_when"], "stop_after_pilot_when", minimum=3)

    rubric = payload["review_rubric"]
    if not isinstance(rubric, dict) or set(rubric) != {
        "scale",
        "criteria",
        "winner_options",
    }:
        raise EvaluationError("review_rubric 형식이 올바르지 않습니다.")
    _text(rubric["scale"], "review_rubric.scale")
    criteria = rubric["criteria"]
    if not isinstance(criteria, list) or len(criteria) < 4:
        raise EvaluationError("review criteria가 부족합니다.")
    criterion_ids: set[str] = set()
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != {"id", "question"}:
            raise EvaluationError("review criterion 형식이 올바르지 않습니다.")
        criterion_id = _text(criterion["id"], "criterion.id")
        if criterion_id in criterion_ids:
            raise EvaluationError(f"criterion ID가 중복되었습니다: {criterion_id}")
        criterion_ids.add(criterion_id)
        _text(criterion["question"], f"{criterion_id}.question")
    winners = _strings(rubric["winner_options"], "winner_options", minimum=4)
    if set(winners) != {"A", "B", "tie", "neither"}:
        raise EvaluationError("winner_options는 A/B/tie/neither여야 합니다.")

    cases = payload["cases"]
    if not isinstance(cases, list) or len(cases) < 4:
        raise EvaluationError("서로 다른 최소 4개 평가 사례가 필요합니다.")
    ids: set[str] = set()
    domains: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
            raise EvaluationError("evaluation case 형식이 올바르지 않습니다.")
        case = dict(raw)
        case_id = _text(case["id"], "case.id")
        if case_id in ids:
            raise EvaluationError(f"case ID가 중복되었습니다: {case_id}")
        ids.add(case_id)
        domain = _text(case["domain"], f"{case_id}.domain")
        domains.add(domain)
        if case["stage"] not in {"pilot", "followup"}:
            raise EvaluationError(f"{case_id}.stage가 올바르지 않습니다.")
        _text(case["request"], f"{case_id}.request")
        if not isinstance(case["context"], str):
            raise EvaluationError(f"{case_id}.context는 문자열이어야 합니다.")
        if case["expected_primary_route"] not in ALLOWED_ROUTES - {"HYBRID"}:
            raise EvaluationError(f"{case_id}.expected_primary_route가 올바르지 않습니다.")
        for key in ("requires_live_web", "allow_workspace_write"):
            if not isinstance(case[key], bool):
                raise EvaluationError(f"{case_id}.{key}는 boolean이어야 합니다.")
        scopes = _strings(case["write_scopes"], f"{case_id}.write_scopes")
        if case["allow_workspace_write"] and not scopes:
            raise EvaluationError(f"{case_id} 쓰기 사례에는 write_scopes가 필요합니다.")
        if not case["allow_workspace_write"] and scopes:
            raise EvaluationError(f"{case_id} 읽기 전용 사례에는 write_scopes를 둘 수 없습니다.")
        fixture = case["workspace_fixture"]
        if fixture is not None:
            fixture = _text(fixture, f"{case_id}.workspace_fixture")
            fixture_path = (root / fixture).resolve()
            if not fixture_path.is_dir():
                raise EvaluationError(f"{case_id} fixture가 없습니다: {fixture}")
            try:
                fixture_path.relative_to(root.resolve())
            except ValueError as exc:
                raise EvaluationError(f"{case_id} fixture가 저장소 밖입니다.") from exc
        elif case["allow_workspace_write"]:
            raise EvaluationError(f"{case_id} 쓰기 사례에는 격리 fixture가 필요합니다.")
        case["must_preserve"] = _strings(
            case["must_preserve"], f"{case_id}.must_preserve", minimum=2
        )
        case["observable_completion"] = _strings(
            case["observable_completion"],
            f"{case_id}.observable_completion",
            minimum=3,
        )
        case["critical_failures"] = _strings(
            case["critical_failures"], f"{case_id}.critical_failures", minimum=3
        )
        normalized_cases.append(case)

    if len(domains) < 4:
        raise EvaluationError("평가 사례가 최소 4개 서로 다른 도메인을 덮어야 합니다.")
    unknown_defaults = set(default_ids) - ids
    if unknown_defaults:
        raise EvaluationError(f"존재하지 않는 default case: {sorted(unknown_defaults)}")
    stage_by_id = {case["id"]: case["stage"] for case in normalized_cases}
    if any(stage_by_id[case_id] != "pilot" for case_id in default_ids):
        raise EvaluationError("기본 사례는 모두 pilot stage여야 합니다.")

    return {
        **payload,
        "pilot_policy": {**pilot, "default_case_ids": default_ids},
        "cases": normalized_cases,
    }


def load_suite(path: Path = DEFAULT_CASES_PATH, *, root: Path = ROOT) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"evaluation suite를 읽을 수 없습니다: {path}: {exc}") from exc
    return validate_suite(payload, root=root)


def select_cases(
    suite: Mapping[str, Any],
    case_ids: list[str] | None,
    *,
    allow_more_cases: bool,
) -> list[dict[str, Any]]:
    requested = case_ids or list(suite["pilot_policy"]["default_case_ids"])
    if len(set(requested)) != len(requested):
        raise EvaluationError("case-id가 중복되었습니다.")
    maximum = suite["pilot_policy"]["maximum_live_cases_without_override"]
    if len(requested) > maximum and not allow_more_cases:
        raise EvaluationError(
            f"기본 live pilot은 {maximum}개까지만 실행합니다. "
            "더 돌리려면 --allow-more-cases가 필요합니다."
        )
    by_id = {case["id"]: case for case in suite["cases"]}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise EvaluationError(f"알 수 없는 case-id: {missing}")
    return [by_id[case_id] for case_id in requested]


def blind_mapping(case_id: str, seed: int) -> dict[str, str]:
    digest = hashlib.sha256(f"blind:{seed}:{case_id}".encode("utf-8")).digest()
    if digest[0] % 2 == 0:
        return {"A": "baseline", "B": "controller"}
    return {"A": "controller", "B": "baseline"}


def arm_order(case_id: str, seed: int) -> list[str]:
    arms = list(ARM_NAMES)
    random.Random(f"order:{seed}:{case_id}").shuffle(arms)
    return arms


def _blank_review(case_id: str, criteria: list[dict[str, str]]) -> dict[str, Any]:
    empty_scores = {criterion["id"]: None for criterion in criteria}
    return {
        "case_id": case_id,
        "scores": {"A": dict(empty_scores), "B": dict(empty_scores)},
        "winner": None,
        "critical_failures": {"A": [], "B": []},
        "notes": "",
    }


def build_blind_packet(
    suite: Mapping[str, Any],
    selected: list[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Mapping[str, Any]]] | None,
    *,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    criteria = suite["review_rubric"]["criteria"]
    packet_cases: list[dict[str, Any]] = []
    key: dict[str, Any] = {"version": 1, "seed": seed, "cases": {}}
    ready = results is not None
    for case in selected:
        mapping = blind_mapping(case["id"], seed)
        key["cases"][case["id"]] = mapping
        outputs = {"A": None, "B": None}
        if results is not None:
            case_results = results[case["id"]]
            outputs = {
                label: case_results[arm]["result_markdown"]
                for label, arm in mapping.items()
            }
        packet_cases.append(
            {
                "case_id": case["id"],
                "domain": case["domain"],
                "request": case["request"],
                "context": case["context"],
                "must_preserve": case["must_preserve"],
                "observable_completion": case["observable_completion"],
                "critical_failure_definitions": case["critical_failures"],
                "outputs": outputs,
                "review": _blank_review(case["id"], criteria),
            }
        )
    packet = {
        "version": 1,
        "status": "ready_for_blind_review" if ready else "prepared_awaiting_live_results",
        "instructions": [
            "Review A and B without opening arm_key.json or metrics.json.",
            "Judge task completion and constraint preservation before writing a winner.",
            "Record a critical failure only when it matches the pre-registered definition.",
            "Save completed reviews as blind_review_response.json before unblinding."
        ],
        "rubric": suite["review_rubric"],
        "cases": packet_cases,
    }
    return packet, key


def _plan_payload(
    suite: Mapping[str, Any],
    selected: list[Mapping[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    return {
        "version": 1,
        "purpose": suite["purpose"],
        "seed": seed,
        "live_model_calls_started": False,
        "case_ids": [case["id"] for case in selected],
        "arm_order": {case["id"]: arm_order(case["id"], seed) for case in selected},
        "pilot_stop_conditions": suite["pilot_policy"]["stop_after_pilot_when"],
    }


def report_template(selected: list[Mapping[str, Any]]) -> str:
    cases = "\n".join(f"- `{case['id']}` ({case['domain']})" for case in selected)
    return f"""# PSOS Controller A/B evaluation report

Status: **not run / blind review pending**

## Pre-registered cases

{cases}

## Evaluation order

1. Run the selected cases with identical requests, context and model policy for both arms.
2. Review `blind_review_packet.json` without opening `arm_key.json` or `metrics.json`.
3. Save the completed rubric as `blind_review_response.json`.
4. Generate this report again with the `report` command to unblind quality and cost together.

## Quality result

Not available until blind review is completed.

## Unblinded cost and routing result

Not available until blind review is completed.

## Promotion decision

No CORE promotion can be inferred from a prepared package or from fewer than four distinct reviewed domains.
"""


def prepare_experiment(
    suite: Mapping[str, Any],
    selected: list[Mapping[str, Any]],
    output_dir: Path,
    *,
    seed: int,
) -> Path:
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise EvaluationError(f"이미 존재하는 experiment 경로입니다: {output_dir}")
    output_dir.mkdir(parents=True)
    packet, _key = build_blind_packet(suite, selected, None, seed=seed)
    _write_json(output_dir / "experiment_plan.json", _plan_payload(suite, selected, seed=seed))
    _write_json(output_dir / "blind_review_packet.json", packet)
    (output_dir / "evaluation_report.md").write_text(
        report_template(selected), encoding="utf-8"
    )
    return output_dir


def _contract_status(payload: Mapping[str, Any]) -> str:
    record = payload.get("result_contract")
    if not isinstance(record, dict):
        return "not_applicable"
    validation = record.get("validation")
    final = validation.get("final_assessment") if isinstance(validation, dict) else None
    status = final.get("overall_status") if isinstance(final, dict) else None
    return status if status in {"satisfied", "missing", "unverifiable"} else "unknown"


def _make_engine(case: Mapping[str, Any], workspace: Path, request: str) -> Any:
    if BASELINE is None:
        raise EvaluationError("PSOS runtime을 불러올 수 없습니다.")
    OS = BASELINE.OS
    allowed_paths = None
    approval = None
    if case["allow_workspace_write"]:
        allowed_paths, approval = OS.build_cli_write_approval(
            workspace, request, case["write_scopes"]
        )
    return OS.CodexEngine(
        workspace,
        allow_workspace_write=case["allow_workspace_write"],
        allowed_write_paths=allowed_paths,
        write_approval=approval,
        enable_search=case["requires_live_web"],
    )


def execute_live_arm(
    case: Mapping[str, Any],
    arm: str,
    *,
    case_dir: Path,
    context_path: Path,
    model_policy_path: Path,
) -> dict[str, Any]:
    if BASELINE is None or CONTROLLER is None:
        raise EvaluationError("PSOS runtime을 불러올 수 없습니다.")
    arm_dir = case_dir / "arms" / arm
    arm_dir.mkdir(parents=True)
    fixture = case["workspace_fixture"]
    if fixture is not None:
        workspace = case_dir / "workspaces" / arm
        shutil.copytree(ROOT / fixture, workspace)
    else:
        workspace = ROOT
    policy = BASELINE.OS.load_model_policy(model_policy_path)
    engine = _make_engine(case, workspace, case["request"])
    started = time.perf_counter()
    if arm == "baseline":
        run_dir, payload = BASELINE.run_request(
            case["request"],
            context_path=context_path,
            output_root=arm_dir,
            engine=engine,
            model_policy=policy,
            run_id="run",
        )
        state = None
        route = payload["route"].get("selected_route")
        outcome = payload["execution"]["status"]
        method_changes = 0
        attempt_count = 1
    elif arm == "controller":
        run_dir, payload, state = CONTROLLER.run_controller_request(
            case["request"],
            context_path=context_path,
            output_root=arm_dir,
            engine=engine,
            model_policy=policy,
            run_id="run",
        )
        chosen = next(
            item for item in state["attempts"] if item["attempt"] == state["chosen_attempt"]
        )
        route = chosen["route"]
        outcome = state["outcome"]
        method_changes = state["budget"]["used_method_changes"]
        attempt_count = len(state["attempts"])
    else:
        raise EvaluationError(f"알 수 없는 arm입니다: {arm}")
    elapsed = time.perf_counter() - started
    result_path = run_dir / "result.md"
    if not result_path.is_file():
        raise EvaluationError(f"{arm} result.md가 없습니다: {result_path}")
    trace = engine.trace()
    return {
        "arm": arm,
        "result_markdown": result_path.read_text(encoding="utf-8"),
        "result_path": str(result_path),
        "workspace": str(workspace),
        "route": route,
        "expected_route": case["expected_primary_route"],
        "expected_route_match": (
            state["attempts"][0]["route"] == case["expected_primary_route"]
            if state is not None
            else route == case["expected_primary_route"]
        ),
        "execution_status": payload["execution"]["status"],
        "outcome": outcome,
        "contract_status": _contract_status(payload),
        "method_changes": method_changes,
        "attempt_count": attempt_count,
        "elapsed_seconds": round(elapsed, 3),
        "model_call_count": len(trace),
        "web_search_call_count": sum(bool(item.get("web_search")) for item in trace),
        "models": sorted(
            {
                item.get("model")
                for item in trace
                if isinstance(item.get("model"), str) and item.get("model")
            }
        ),
        "trace_routes": [
            item.get("route") for item in trace if item.get("route") is not None
        ],
    }


ArmExecutor = Callable[..., dict[str, Any]]


def run_live_experiment(
    suite: Mapping[str, Any],
    selected: list[Mapping[str, Any]],
    output_dir: Path,
    *,
    seed: int,
    model_policy_path: Path,
    arm_executor: ArmExecutor = execute_live_arm,
) -> Path:
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise EvaluationError(f"이미 존재하는 experiment 경로입니다: {output_dir}")
    output_dir.mkdir(parents=True)
    plan = _plan_payload(suite, selected, seed=seed)
    plan["live_model_calls_started"] = True
    _write_json(output_dir / "experiment_plan.json", plan)

    results: dict[str, dict[str, dict[str, Any]]] = {}
    metrics: dict[str, Any] = {"version": 1, "cases": {}}
    for case in selected:
        case_dir = output_dir / "cases" / case["id"]
        case_dir.mkdir(parents=True)
        context_path = case_dir / "context.txt"
        context_path.write_text(case["context"].rstrip() + "\n", encoding="utf-8")
        results[case["id"]] = {}
        for arm in arm_order(case["id"], seed):
            result = arm_executor(
                case,
                arm,
                case_dir=case_dir,
                context_path=context_path,
                model_policy_path=model_policy_path,
            )
            results[case["id"]][arm] = result
        metrics["cases"][case["id"]] = {
            arm: {
                key: value
                for key, value in result.items()
                if key not in {"result_markdown", "arm"}
            }
            for arm, result in results[case["id"]].items()
        }
        _write_json(case_dir / "raw_results.json", results[case["id"]])

    packet, key = build_blind_packet(suite, selected, results, seed=seed)
    _write_json(output_dir / "blind_review_packet.json", packet)
    _write_json(output_dir / "arm_key.json", key)
    _write_json(output_dir / "metrics.json", metrics)
    (output_dir / "evaluation_report.md").write_text(
        report_template(selected), encoding="utf-8"
    )
    return output_dir


def _validate_review_response(
    response: Any,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(response, dict) or set(response) != {"version", "reviews"}:
        raise EvaluationError("blind review response 형식이 올바르지 않습니다.")
    if response["version"] != 1 or not isinstance(response["reviews"], list):
        raise EvaluationError("blind review response version/reviews가 올바르지 않습니다.")
    criteria = [item["id"] for item in packet["rubric"]["criteria"]]
    expected_cases = {item["case_id"] for item in packet["cases"]}
    seen: set[str] = set()
    for review in response["reviews"]:
        if not isinstance(review, dict) or set(review) != {
            "case_id",
            "scores",
            "winner",
            "critical_failures",
            "notes",
        }:
            raise EvaluationError("review 항목 형식이 올바르지 않습니다.")
        case_id = _text(review["case_id"], "review.case_id")
        if case_id in seen or case_id not in expected_cases:
            raise EvaluationError(f"review case가 중복되었거나 알 수 없습니다: {case_id}")
        seen.add(case_id)
        if review["winner"] not in {"A", "B", "tie", "neither"}:
            raise EvaluationError(f"{case_id} winner가 올바르지 않습니다.")
        scores = review["scores"]
        if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
            raise EvaluationError(f"{case_id} scores가 올바르지 않습니다.")
        for label in ("A", "B"):
            if not isinstance(scores[label], dict) or set(scores[label]) != set(criteria):
                raise EvaluationError(f"{case_id}.{label} criterion이 일치하지 않습니다.")
            if not all(isinstance(value, int) and 0 <= value <= 4 for value in scores[label].values()):
                raise EvaluationError(f"{case_id}.{label} score는 0~4 정수여야 합니다.")
        failures = review["critical_failures"]
        if not isinstance(failures, dict) or set(failures) != {"A", "B"}:
            raise EvaluationError(f"{case_id} critical_failures가 올바르지 않습니다.")
        _strings(failures["A"], f"{case_id}.failures.A")
        _strings(failures["B"], f"{case_id}.failures.B")
        if not isinstance(review["notes"], str):
            raise EvaluationError(f"{case_id}.notes는 문자열이어야 합니다.")
    if seen != expected_cases:
        raise EvaluationError("모든 blind case에 대한 review가 필요합니다.")
    return response


def generate_report(experiment_dir: Path, review_file: Path) -> Path:
    experiment_dir = experiment_dir.expanduser().resolve()
    try:
        packet = json.loads((experiment_dir / "blind_review_packet.json").read_text(encoding="utf-8"))
        key = json.loads((experiment_dir / "arm_key.json").read_text(encoding="utf-8"))
        metrics = json.loads((experiment_dir / "metrics.json").read_text(encoding="utf-8"))
        response = json.loads(review_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"report 입력을 읽을 수 없습니다: {exc}") from exc
    response = _validate_review_response(response, packet)
    by_case = {review["case_id"]: review for review in response["reviews"]}
    lines = [
        "# PSOS Controller A/B evaluation report",
        "",
        "Status: **blind review completed and unblinded**",
        "",
        "## Blind quality judgments",
        "",
    ]
    controller_wins = 0
    baseline_wins = 0
    reviewed_domains = 0
    packet_by_case = {item["case_id"]: item for item in packet["cases"]}
    for case_id, review in by_case.items():
        mapping = key["cases"][case_id]
        winner = review["winner"]
        actual_winner = mapping[winner] if winner in {"A", "B"} else winner
        controller_wins += actual_winner == "controller"
        baseline_wins += actual_winner == "baseline"
        reviewed_domains += 1
        lines.extend(
            [
                f"### {case_id} ({packet_by_case[case_id]['domain']})",
                "",
                f"- Blind winner: `{winner}` → `{actual_winner}`",
                f"- A scores: `{json.dumps(review['scores']['A'], ensure_ascii=False)}`",
                f"- B scores: `{json.dumps(review['scores']['B'], ensure_ascii=False)}`",
                f"- A critical failures: `{json.dumps(review['critical_failures']['A'], ensure_ascii=False)}`",
                f"- B critical failures: `{json.dumps(review['critical_failures']['B'], ensure_ascii=False)}`",
                f"- Notes: {review['notes'] or '없음'}",
                "",
            ]
        )
    lines.extend(["## Unblinded cost and routing metrics", ""])
    for case_id, case_metrics in metrics["cases"].items():
        base = case_metrics["baseline"]
        ctrl = case_metrics["controller"]
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- Baseline: route `{base['route']}`, status `{base['execution_status']}`, calls `{base['model_call_count']}`, elapsed `{base['elapsed_seconds']}s`",
                f"- Controller: route `{ctrl['route']}`, status `{ctrl['execution_status']}`, calls `{ctrl['model_call_count']}`, elapsed `{ctrl['elapsed_seconds']}s`, method changes `{ctrl['method_changes']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Decision gate",
            "",
            f"- Controller blind wins: **{controller_wins}**",
            f"- Baseline blind wins: **{baseline_wins}**",
            f"- Reviewed domains: **{reviewed_domains}**",
        ]
    )
    if reviewed_domains < 4:
        lines.append("- Verdict: pilot evidence only. CORE promotion is not evaluable yet.")
    else:
        lines.append(
            "- Verdict: four-domain evidence exists, but promotion still requires explicit user approval and a separate review of critical failures and cost."
        )
    report_path = experiment_dir / "evaluation_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-file", type=Path, default=DEFAULT_CASES_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate the pre-registered suite without model calls")

    prepare = subparsers.add_parser("prepare", help="write a no-model-call experiment package")
    prepare.add_argument("--case-id", action="append", default=[])
    prepare.add_argument("--allow-more-cases", action="store_true")
    prepare.add_argument("--seed", type=int, default=20260806)
    prepare.add_argument("--output-dir", type=Path, required=True)

    run = subparsers.add_parser("run", help="run live baseline/controller arms")
    run.add_argument("--case-id", action="append", default=[])
    run.add_argument("--allow-more-cases", action="store_true")
    run.add_argument("--seed", type=int, default=20260806)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--model-policy", type=Path)
    run.add_argument(
        "--confirm-live",
        action="store_true",
        help="required acknowledgement that this command spends Codex usage",
    )

    report = subparsers.add_parser("report", help="unblind a completed review and render report")
    report.add_argument("--experiment-dir", type=Path, required=True)
    report.add_argument("--review-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        suite = load_suite(args.cases_file)
        if args.command == "validate":
            print(
                f"OK: {len(suite['cases'])} cases, "
                f"{len({case['domain'] for case in suite['cases']})} domains"
            )
            return 0
        if args.command == "report":
            path = generate_report(args.experiment_dir, args.review_file)
            print(path)
            return 0
        requested_ids = args.case_id or (
            [case["id"] for case in suite["cases"]]
            if args.command == "prepare"
            else None
        )
        selected = select_cases(
            suite,
            requested_ids,
            allow_more_cases=(
                True if args.command == "prepare" else args.allow_more_cases
            ),
        )
        if args.command == "prepare":
            path = prepare_experiment(suite, selected, args.output_dir, seed=args.seed)
            print(path)
            return 0
        if not args.confirm_live:
            raise EvaluationError(
                "live 실행은 Codex 사용량을 소모합니다. 확인 후 --confirm-live를 추가하세요."
            )
        model_policy = args.model_policy
        if model_policy is None:
            if BASELINE is None:
                raise EvaluationError("기본 model policy를 찾을 수 없습니다.")
            model_policy = BASELINE.OS.DEFAULT_MODEL_POLICY_PATH
        path = run_live_experiment(
            suite,
            selected,
            args.output_dir,
            seed=args.seed,
            model_policy_path=model_policy,
        )
        print(path)
        return 0
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
