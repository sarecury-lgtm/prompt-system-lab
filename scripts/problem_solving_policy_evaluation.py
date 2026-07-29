#!/usr/bin/env python3
"""Evaluate a draft policy proposal with paired, fixed-request runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_feedback as feedback
import problem_solving_policy_proposal as proposal
import problem_solving_review as review


ROOT = SCRIPT_DIR.parent
RUNS_DIR = ROOT / "runs"
EVALUATIONS_DIR = ROOT / "policy-evaluations"
JUDGMENTS = {"candidate_better", "equivalent", "candidate_worse"}
MINIMUM_EVALUATION_CASES = 3


class EvaluationError(Exception):
    """A policy evaluation that cannot be trusted."""


def meaningful(value: str, label: str) -> str:
    try:
        return feedback.validate_meaningful_text(value, label)
    except feedback.FeedbackError as exc:
        raise EvaluationError(str(exc)) from exc


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return feedback.read_json(path.expanduser().resolve())
    except feedback.FeedbackError as exc:
        raise EvaluationError(f"{label}: {exc}") from exc


def resolve_run(run_id: str, runs_root: Path) -> Path:
    try:
        return review.resolve_run(run_id, runs_root)
    except review.ReviewError as exc:
        raise EvaluationError(str(exc)) from exc


def load_evaluation_run(
    run_id: str,
    *,
    runs_root: Path,
    expected_policy: dict[str, Any],
) -> dict[str, Any]:
    run_dir = resolve_run(run_id, runs_root)
    try:
        _, route = feedback.validate_run(run_dir)
    except feedback.FeedbackError as exc:
        raise EvaluationError(str(exc)) from exc
    run = route.get("run")
    if not isinstance(run, dict):
        raise EvaluationError(f"route.json.run is missing for {run_id}.")
    if run.get("run_id") != run_dir.name:
        raise EvaluationError(f"embedded run_id does not match {run_id}.")
    if run.get("model_policy") != expected_policy:
        raise EvaluationError(f"embedded model policy does not match for {run_id}.")
    request_path = run_dir / "request.txt"
    result_path = run_dir / "result.md"
    request_text = request_path.read_text(encoding="utf-8").strip()
    if not request_text:
        raise EvaluationError(f"evaluation request is empty for {run_id}.")
    return {
        "run_id": run_dir.name,
        "request_sha256": feedback.file_sha256(request_path),
        "result_sha256": feedback.file_sha256(result_path),
        "selected_route": route["selected_route"],
        "execution_status": route["execution_status"],
    }


def validate_judgments(
    payload: dict[str, Any],
    proposal_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    expected = {"version", "proposal_id", "evaluator", "cases"}
    if set(payload) != expected or payload.get("version") != 1:
        raise EvaluationError("judgment file has an invalid format.")
    if payload.get("proposal_id") != proposal_id:
        raise EvaluationError("judgment proposal_id does not match.")
    evaluator = payload.get("evaluator")
    if not isinstance(evaluator, str):
        raise EvaluationError("judgment evaluator must be a string.")
    evaluator = meaningful(evaluator, "evaluator")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise EvaluationError("judgment cases must be an array.")
    case_fields = {
        "case_id",
        "baseline_run_id",
        "candidate_run_id",
        "judgment",
        "evidence",
    }
    seen_case_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict) or set(item) != case_fields:
            raise EvaluationError("judgment case has an invalid format.")
        case_id = item.get("case_id")
        baseline_run_id = item.get("baseline_run_id")
        candidate_run_id = item.get("candidate_run_id")
        judgment = item.get("judgment")
        evidence = item.get("evidence")
        if not all(
            isinstance(value, str)
            for value in (case_id, baseline_run_id, candidate_run_id)
        ):
            raise EvaluationError("judgment case identifiers are invalid.")
        case_id = meaningful(case_id, "case_id")
        if case_id in seen_case_ids:
            raise EvaluationError("judgment case_id is duplicated.")
        seen_case_ids.add(case_id)
        if baseline_run_id == candidate_run_id:
            raise EvaluationError("baseline and candidate run IDs must differ.")
        if judgment not in JUDGMENTS:
            raise EvaluationError("judgment value is not supported.")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(value, str) for value in evidence
        ):
            raise EvaluationError(
                "judgment evidence must be a non-empty string array."
            )
        evidence = [meaningful(value, "judgment evidence") for value in evidence]
        validated.append(
            {
                "case_id": case_id,
                "baseline_run_id": baseline_run_id,
                "candidate_run_id": candidate_run_id,
                "judgment": judgment,
                "evidence": evidence,
            }
        )
    return evaluator, validated


def evaluation_id(
    proposal_sha256: str,
    evaluator: str,
    cases: list[dict[str, Any]],
) -> str:
    payload = {
        "proposal_sha256": proposal_sha256,
        "evaluator": evaluator,
        "cases": cases,
    }
    return "evaluation-" + review.canonical_sha256(payload)[:20]


def validate_evaluation_record(
    payload: dict[str, Any],
    proposal_file: Path,
    proposal_record: dict[str, Any],
    baseline_policy: dict[str, Any],
    candidate_policy: dict[str, Any],
    route_scope: str | None,
    *,
    runs_root: Path = RUNS_DIR,
) -> dict[str, Any]:
    expected_fields = {
        "version",
        "evaluation_id",
        "created_at",
        "proposal",
        "status",
        "evaluator",
        "cases",
        "summary",
        "gate",
    }
    if set(payload) != expected_fields or payload.get("version") != 1:
        raise EvaluationError("evaluation record has an invalid format.")
    if not isinstance(payload.get("created_at"), str):
        raise EvaluationError("evaluation created_at is invalid.")
    proposal_sha256 = feedback.file_sha256(proposal_file)
    if payload.get("proposal") != {
        "proposal_id": proposal_record["proposal_id"],
        "proposal_sha256": proposal_sha256,
    }:
        raise EvaluationError("evaluation proposal reference does not match.")
    stored_cases = payload.get("cases")
    if not isinstance(stored_cases, list):
        raise EvaluationError("evaluation cases must be an array.")
    judgment_cases: list[dict[str, Any]] = []
    for item in stored_cases:
        if not isinstance(item, dict):
            raise EvaluationError("evaluation case has an invalid format.")
        judgment_cases.append(
            {
                key: item.get(key)
                for key in (
                    "case_id",
                    "baseline_run_id",
                    "candidate_run_id",
                    "judgment",
                    "evidence",
                )
            }
        )
    evaluator, validated_judgments = validate_judgments(
        {
            "version": 1,
            "proposal_id": proposal_record["proposal_id"],
            "evaluator": payload.get("evaluator"),
            "cases": judgment_cases,
        },
        proposal_record["proposal_id"],
    )

    training_run_ids = {
        item["run_id"] for item in proposal_record["candidates"]
    }
    used_run_ids: set[str] = set()
    request_hashes: set[str] = set()
    expected_cases: list[dict[str, Any]] = []
    for item in validated_judgments:
        baseline = load_evaluation_run(
            item["baseline_run_id"],
            runs_root=runs_root,
            expected_policy=baseline_policy,
        )
        candidate = load_evaluation_run(
            item["candidate_run_id"],
            runs_root=runs_root,
            expected_policy=candidate_policy,
        )
        pair_ids = {baseline["run_id"], candidate["run_id"]}
        if pair_ids & training_run_ids:
            raise EvaluationError(
                "evaluation runs reuse proposal evidence runs."
            )
        if pair_ids & used_run_ids:
            raise EvaluationError("evaluation run is reused across cases.")
        used_run_ids.update(pair_ids)
        if baseline["request_sha256"] != candidate["request_sha256"]:
            raise EvaluationError("evaluation paired requests do not match.")
        request_hash = baseline["request_sha256"]
        if request_hash in request_hashes:
            raise EvaluationError("evaluation request is reused across cases.")
        request_hashes.add(request_hash)
        if route_scope is not None and (
            baseline["selected_route"] != route_scope
            or candidate["selected_route"] != route_scope
        ):
            raise EvaluationError("evaluation route does not match proposal.")
        if (
            item["judgment"] == "candidate_better"
            and baseline["result_sha256"] == candidate["result_sha256"]
        ):
            raise EvaluationError(
                "candidate_better has an unchanged result hash."
            )
        expected_cases.append(
            {
                **item,
                "request_sha256": request_hash,
                "baseline": baseline,
                "candidate": candidate,
            }
        )
    if stored_cases != expected_cases:
        raise EvaluationError("evaluation cases no longer match source runs.")

    failures: list[str] = []
    if len(expected_cases) < MINIMUM_EVALUATION_CASES:
        failures.append(f"requires_at_least_{MINIMUM_EVALUATION_CASES}_cases")
    for item in expected_cases:
        if item["candidate"]["execution_status"] != "completed":
            failures.append(f"candidate_not_completed:{item['case_id']}")
        if item["judgment"] == "candidate_worse":
            failures.append(f"quality_regression:{item['case_id']}")
    if not any(
        item["judgment"] == "candidate_better" for item in expected_cases
    ):
        failures.append("no_demonstrated_quality_improvement")
    expected_status = "passed" if not failures else "failed"
    if payload.get("status") != expected_status:
        raise EvaluationError("evaluation status does not match gate results.")
    expected_summary = {
        "case_count": len(expected_cases),
        "candidate_better": sum(
            item["judgment"] == "candidate_better" for item in expected_cases
        ),
        "equivalent": sum(
            item["judgment"] == "equivalent" for item in expected_cases
        ),
        "candidate_worse": sum(
            item["judgment"] == "candidate_worse" for item in expected_cases
        ),
        "candidate_completed": sum(
            item["candidate"]["execution_status"] == "completed"
            for item in expected_cases
        ),
    }
    if payload.get("summary") != expected_summary:
        raise EvaluationError("evaluation summary does not match cases.")
    expected_gate = {
        "minimum_cases": MINIMUM_EVALUATION_CASES,
        "failures": failures,
        "requires_human_approval": True,
        "automatic_application_allowed": False,
        "policy_applied": False,
    }
    if payload.get("gate") != expected_gate:
        raise EvaluationError("evaluation gate does not match cases.")
    expected_id = evaluation_id(proposal_sha256, evaluator, expected_cases)
    if payload.get("evaluation_id") != expected_id:
        raise EvaluationError("evaluation ID does not match its content.")
    return payload


def evaluate_policy_proposal(
    proposal_path: Path,
    judgment_path: Path,
    *,
    runs_root: Path = RUNS_DIR,
    output_dir: Path = EVALUATIONS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    proposal_file = proposal_path.expanduser().resolve()
    proposal_record = read_json(proposal_file, "proposal")
    try:
        baseline_policy, candidate_policy, route_scope = proposal.validate_proposal(
            proposal_record,
            runs_root=runs_root,
        )
    except proposal.ProposalError as exc:
        raise EvaluationError(str(exc)) from exc
    evaluator, judgments = validate_judgments(
        read_json(judgment_path, "judgments"),
        proposal_record["proposal_id"],
    )

    training_run_ids = {
        item["run_id"] for item in proposal_record["candidates"]
    }
    used_run_ids: set[str] = set()
    request_hashes: set[str] = set()
    evaluated_cases: list[dict[str, Any]] = []
    for item in judgments:
        baseline = load_evaluation_run(
            item["baseline_run_id"],
            runs_root=runs_root,
            expected_policy=baseline_policy,
        )
        candidate = load_evaluation_run(
            item["candidate_run_id"],
            runs_root=runs_root,
            expected_policy=candidate_policy,
        )
        pair_ids = {baseline["run_id"], candidate["run_id"]}
        if pair_ids & training_run_ids:
            raise EvaluationError(
                "evaluation runs must be separate from proposal evidence runs."
            )
        if pair_ids & used_run_ids:
            raise EvaluationError("an evaluation run is reused across cases.")
        used_run_ids.update(pair_ids)
        if baseline["request_sha256"] != candidate["request_sha256"]:
            raise EvaluationError(
                f"paired requests differ for case {item['case_id']}."
            )
        request_hash = baseline["request_sha256"]
        if request_hash in request_hashes:
            raise EvaluationError("the same request is reused across cases.")
        request_hashes.add(request_hash)
        if route_scope is not None and (
            baseline["selected_route"] != route_scope
            or candidate["selected_route"] != route_scope
        ):
            raise EvaluationError(
                f"route-specific evaluation left {route_scope} "
                f"for case {item['case_id']}."
            )
        if (
            item["judgment"] == "candidate_better"
            and baseline["result_sha256"] == candidate["result_sha256"]
        ):
            raise EvaluationError(
                "candidate_better requires a different candidate result."
            )
        evaluated_cases.append(
            {
                **item,
                "request_sha256": request_hash,
                "baseline": baseline,
                "candidate": candidate,
            }
        )

    gate_failures: list[str] = []
    if len(evaluated_cases) < MINIMUM_EVALUATION_CASES:
        gate_failures.append(
            f"requires_at_least_{MINIMUM_EVALUATION_CASES}_cases"
        )
    for item in evaluated_cases:
        if item["candidate"]["execution_status"] != "completed":
            gate_failures.append(
                f"candidate_not_completed:{item['case_id']}"
            )
        if item["judgment"] == "candidate_worse":
            gate_failures.append(f"quality_regression:{item['case_id']}")
    if not any(
        item["judgment"] == "candidate_better"
        for item in evaluated_cases
    ):
        gate_failures.append("no_demonstrated_quality_improvement")

    proposal_sha256 = feedback.file_sha256(proposal_file)
    identifier = evaluation_id(proposal_sha256, evaluator, evaluated_cases)
    status = "passed" if not gate_failures else "failed"
    payload = {
        "version": 1,
        "evaluation_id": identifier,
        "created_at": feedback.utc_now(),
        "proposal": {
            "proposal_id": proposal_record["proposal_id"],
            "proposal_sha256": proposal_sha256,
        },
        "status": status,
        "evaluator": evaluator,
        "cases": evaluated_cases,
        "summary": {
            "case_count": len(evaluated_cases),
            "candidate_better": sum(
                item["judgment"] == "candidate_better"
                for item in evaluated_cases
            ),
            "equivalent": sum(
                item["judgment"] == "equivalent"
                for item in evaluated_cases
            ),
            "candidate_worse": sum(
                item["judgment"] == "candidate_worse"
                for item in evaluated_cases
            ),
            "candidate_completed": sum(
                item["candidate"]["execution_status"] == "completed"
                for item in evaluated_cases
            ),
        },
        "gate": {
            "minimum_cases": MINIMUM_EVALUATION_CASES,
            "failures": gate_failures,
            "requires_human_approval": True,
            "automatic_application_allowed": False,
            "policy_applied": False,
        },
    }
    destination = output_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    evaluation_path = destination / f"{identifier}.json"
    if evaluation_path.is_file():
        existing = read_json(evaluation_path, "existing evaluation")
        comparable = dict(payload)
        comparable["created_at"] = existing.get("created_at")
        if existing != comparable:
            raise EvaluationError(
                "existing evaluation does not match this evaluation."
            )
        return evaluation_path, existing, False
    feedback.atomic_write_json(evaluation_path, payload)
    return evaluation_path, payload, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a draft policy proposal with paired runs of the same "
            "fixed requests. This command never applies the proposal."
        ),
    )
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--judgments", required=True, type=Path)
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    parser.add_argument("--output-dir", type=Path, default=EVALUATIONS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path, evaluation, created = evaluate_policy_proposal(
            args.proposal,
            args.judgments,
            runs_root=args.runs_root,
            output_dir=args.output_dir,
        )
    except EvaluationError as exc:
        print(f"policy evaluation failed: {exc}", file=sys.stderr)
        return 2
    print(f"policy evaluation: {'created' if created else 'already_exists'}")
    print(f"evaluation_id: {evaluation['evaluation_id']}")
    print(f"status: {evaluation['status']}")
    print(f"cases: {evaluation['summary']['case_count']}")
    print("policy applied: no")
    print(f"evaluation: {path}")
    return 0 if evaluation["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
