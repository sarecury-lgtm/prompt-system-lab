#!/usr/bin/env python3
"""Read-only operational status and integrity audit for the PSOS lifecycle."""

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
import problem_solving_policy_change as change
import problem_solving_policy_evaluation as evaluation
import problem_solving_policy_proposal as proposal
import problem_solving_review as review


ROOT = SCRIPT_DIR.parent
RUNS_DIR = ROOT / "runs"
PROPOSALS_DIR = ROOT / "policy-proposals"
EVALUATIONS_DIR = ROOT / "policy-evaluations"
APPROVALS_DIR = ROOT / "policy-approvals"
CHANGES_DIR = ROOT / "policy-changes"


def display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def json_files(path: Path, *, exclude_suffix: str | None = None) -> list[Path]:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        return []
    files = sorted(resolved.glob("*.json"))
    if exclude_suffix is not None:
        files = [item for item in files if not item.name.endswith(exclude_suffix)]
    return files


def error_text(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def validate_base_run(
    run_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = sorted(
        name
        for name in feedback.REQUIRED_RUN_FILES
        if not (run_dir / name).is_file()
    )
    if missing:
        raise feedback.FeedbackError(
            "run files are missing: " + ", ".join(missing)
        )
    ledger = feedback.read_json(run_dir / "goal_ledger.json")
    route = feedback.read_json(run_dir / "route.json")
    execution_status = route.get("execution_status")
    selected_route = route.get("selected_route")
    if not isinstance(execution_status, str):
        raise feedback.FeedbackError("route execution_status is invalid.")
    if execution_status == "completed" and not isinstance(selected_route, str):
        raise feedback.FeedbackError(
            "completed run does not have a selected route."
        )
    if selected_route is not None and not isinstance(selected_route, str):
        raise feedback.FeedbackError("route selected_route is invalid.")
    return ledger, route


def audit_runs(runs_root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    root = runs_root.expanduser().resolve()
    items: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "completed": 0,
        "not_completed": 0,
        "learning_records": 0,
        "learning_events": 0,
        "review_records": 0,
        "promoted": 0,
        "rejected": 0,
        "unreviewed": 0,
    }
    if not root.is_dir():
        return items, counts
    for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        counts["total"] += 1
        item: dict[str, Any] = {
            "run_id": run_dir.name,
            "path": display_path(run_dir),
            "valid": True,
            "execution_status": None,
            "learning_events": 0,
            "reviewed_events": 0,
            "promoted": 0,
            "rejected": 0,
            "issues": [],
        }
        learning: dict[str, Any] | None = None
        try:
            _, route = validate_base_run(run_dir)
            item["execution_status"] = route["execution_status"]
            if route["execution_status"] == "completed":
                counts["completed"] += 1
            else:
                counts["not_completed"] += 1
        except (feedback.FeedbackError, OSError) as exc:
            item["valid"] = False
            item["issues"].append(error_text(exc))
            route = None

        learning_path = run_dir / "learning_record.json"
        if learning_path.is_file():
            counts["learning_records"] += 1
            try:
                if route is None:
                    raise feedback.FeedbackError(
                        "cannot validate learning record for invalid run."
                    )
                _, learning_route = feedback.validate_run(run_dir)
                learning = feedback.validate_existing_record(
                    feedback.read_json(learning_path),
                    run_dir,
                    learning_route,
                )
                item["learning_events"] = len(learning["events"])
                counts["learning_events"] += len(learning["events"])
            except (feedback.FeedbackError, OSError) as exc:
                item["valid"] = False
                item["issues"].append(error_text(exc))

        review_path = run_dir / "learning_review.json"
        reviewed_event_ids: set[str] = set()
        if review_path.is_file():
            counts["review_records"] += 1
            try:
                if learning is None:
                    raise review.ReviewError(
                        "cannot validate review without a valid learning record."
                    )
                review_record = review.validate_review_record(
                    feedback.read_json(review_path),
                    run_dir,
                    learning,
                )
                for decision in review_record["decisions"]:
                    reviewed_event_ids.add(decision["event_id"])
                    if decision["decision"] == "promote":
                        item["promoted"] += 1
                    else:
                        item["rejected"] += 1
                item["reviewed_events"] = len(reviewed_event_ids)
                counts["promoted"] += item["promoted"]
                counts["rejected"] += item["rejected"]
            except (feedback.FeedbackError, review.ReviewError, OSError) as exc:
                item["valid"] = False
                item["issues"].append(error_text(exc))
        if learning is not None:
            unreviewed = sum(
                event["event_id"] not in reviewed_event_ids
                for event in learning["events"]
            )
            counts["unreviewed"] += unreviewed
        if item["valid"]:
            counts["valid"] += 1
        else:
            counts["invalid"] += 1
        items.append(item)
    return items, counts


def audit_approvals(
    approvals_dir: Path,
    runs_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    valid_sources: dict[str, Any] = {
        "proposal_paths": {},
        "evaluation_paths": {},
    }
    for path in json_files(approvals_dir):
        item = {
            "path": display_path(path),
            "valid": True,
            "approval_id": None,
            "issues": [],
        }
        try:
            record = change.read_json(path, "approval")
            loaded = change.validate_approval(record, runs_root=runs_root)
            item["approval_id"] = record["approval_id"]
            proposal_path = loaded[0]
            evaluation_path = loaded[2]
            valid_sources["proposal_paths"][str(proposal_path)] = {
                "loaded": loaded,
                "sha256": record["sources"]["proposal_sha256"],
            }
            valid_sources["evaluation_paths"][str(evaluation_path)] = {
                "loaded": loaded,
                "sha256": record["sources"]["evaluation_sha256"],
            }
        except (change.PolicyChangeError, OSError) as exc:
            item["valid"] = False
            item["issues"].append(error_text(exc))
        items.append(item)
    return items, valid_sources


def audit_proposals(
    proposals_dir: Path,
    runs_root: Path,
    approved_sources: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in json_files(proposals_dir):
        item = {
            "path": display_path(path),
            "valid": True,
            "proposal_id": None,
            "status": None,
            "validated_via": None,
            "issues": [],
        }
        try:
            record = feedback.read_json(path)
            item["proposal_id"] = record.get("proposal_id")
            item["status"] = record.get("status")
            approved = approved_sources.get(str(path.resolve()))
            if approved is not None:
                if feedback.file_sha256(path) != approved["sha256"]:
                    raise proposal.ProposalError(
                        "approved proposal hash no longer matches."
                    )
                item["validated_via"] = "approval_snapshot"
            else:
                proposal.validate_proposal(record, runs_root=runs_root)
                item["validated_via"] = "active_policy"
        except (feedback.FeedbackError, proposal.ProposalError, OSError) as exc:
            item["valid"] = False
            item["issues"].append(error_text(exc))
        items.append(item)
    return items


def audit_evaluations(
    evaluations_dir: Path,
    runs_root: Path,
    proposals_dir: Path,
    approved_sources: dict[str, Any],
) -> list[dict[str, Any]]:
    proposal_records: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    for path in json_files(proposals_dir):
        try:
            record = feedback.read_json(path)
            proposal_records[
                (record.get("proposal_id"), feedback.file_sha256(path))
            ] = (path, record)
        except (feedback.FeedbackError, OSError):
            continue
    items: list[dict[str, Any]] = []
    for path in json_files(evaluations_dir):
        item = {
            "path": display_path(path),
            "valid": True,
            "evaluation_id": None,
            "status": None,
            "validated_via": None,
            "issues": [],
        }
        try:
            record = evaluation.read_json(path, "evaluation")
            item["evaluation_id"] = record.get("evaluation_id")
            item["status"] = record.get("status")
            approved = approved_sources.get(str(path.resolve()))
            if approved is not None:
                if feedback.file_sha256(path) != approved["sha256"]:
                    raise evaluation.EvaluationError(
                        "approved evaluation hash no longer matches."
                    )
                item["validated_via"] = "approval_snapshot"
            else:
                reference = record.get("proposal")
                if not isinstance(reference, dict):
                    raise evaluation.EvaluationError(
                        "evaluation proposal reference is invalid."
                    )
                source = proposal_records.get(
                    (
                        reference.get("proposal_id"),
                        reference.get("proposal_sha256"),
                    )
                )
                if source is None:
                    raise evaluation.EvaluationError(
                        "referenced proposal file was not found."
                    )
                proposal_path, proposal_record = source
                baseline, candidate, route_scope = proposal.validate_proposal(
                    proposal_record,
                    runs_root=runs_root,
                )
                evaluation.validate_evaluation_record(
                    record,
                    proposal_path,
                    proposal_record,
                    baseline,
                    candidate,
                    route_scope,
                    runs_root=runs_root,
                )
                item["validated_via"] = "active_policy"
        except (
            evaluation.EvaluationError,
            proposal.ProposalError,
            OSError,
        ) as exc:
            item["valid"] = False
            item["issues"].append(error_text(exc))
        items.append(item)
    return items


def audit_changes(
    changes_dir: Path,
    runs_root: Path,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in json_files(changes_dir, exclude_suffix=".before.json"):
        item = {
            "path": display_path(path),
            "valid": True,
            "change_id": None,
            "receipt_status": None,
            "active_state": None,
            "issues": [],
        }
        try:
            inspected = change.inspect_policy_change(
                path,
                runs_root=runs_root,
            )
            receipt = inspected["receipt"]
            item["change_id"] = receipt["change_id"]
            item["receipt_status"] = receipt["status"]
            item["active_state"] = inspected["active_state"]
            if inspected["active_state"] == "drifted":
                item["valid"] = False
                item["issues"].append(
                    "active policy does not match receipt before/after hashes."
                )
        except (change.PolicyChangeError, OSError) as exc:
            item["valid"] = False
            item["issues"].append(error_text(exc))
        items.append(item)
    return items


def build_status(
    *,
    runs_root: Path = RUNS_DIR,
    proposals_dir: Path = PROPOSALS_DIR,
    evaluations_dir: Path = EVALUATIONS_DIR,
    approvals_dir: Path = APPROVALS_DIR,
    changes_dir: Path = CHANGES_DIR,
) -> dict[str, Any]:
    runs, run_counts = audit_runs(runs_root)
    approvals, approved_sources = audit_approvals(approvals_dir, runs_root)
    proposals = audit_proposals(
        proposals_dir,
        runs_root,
        approved_sources["proposal_paths"],
    )
    evaluations = audit_evaluations(
        evaluations_dir,
        runs_root,
        proposals_dir,
        approved_sources["evaluation_paths"],
    )
    changes = audit_changes(changes_dir, runs_root)
    invalid_count = (
        run_counts["invalid"]
        + sum(not item["valid"] for item in proposals)
        + sum(not item["valid"] for item in evaluations)
        + sum(not item["valid"] for item in approvals)
        + sum(not item["valid"] for item in changes)
    )
    summary = {
        "runs": run_counts,
        "proposals": {
            "total": len(proposals),
            "valid": sum(item["valid"] for item in proposals),
            "invalid": sum(not item["valid"] for item in proposals),
        },
        "evaluations": {
            "total": len(evaluations),
            "passed": sum(
                item["valid"] and item["status"] == "passed"
                for item in evaluations
            ),
            "failed": sum(
                item["valid"] and item["status"] == "failed"
                for item in evaluations
            ),
            "invalid": sum(not item["valid"] for item in evaluations),
        },
        "approvals": {
            "total": len(approvals),
            "valid": sum(item["valid"] for item in approvals),
            "invalid": sum(not item["valid"] for item in approvals),
        },
        "changes": {
            "total": len(changes),
            "applied": sum(
                item["valid"] and item["active_state"] == "applied"
                for item in changes
            ),
            "rolled_back": sum(
                item["valid"] and item["active_state"] == "rolled_back"
                for item in changes
            ),
            "recoverable": sum(
                item["valid"]
                and item["active_state"]
                in {
                    "ready_to_apply",
                    "application_needs_finalization",
                    "rollback_needs_finalization",
                }
                for item in changes
            ),
            "invalid": sum(not item["valid"] for item in changes),
        },
        "invalid_count": invalid_count,
    }
    next_actions: list[str] = []
    if invalid_count:
        next_actions.append("inspect_invalid_records")
    if run_counts["unreviewed"]:
        next_actions.append("review_learning_candidates")
    if run_counts["promoted"] < 2:
        next_actions.append("collect_more_real_outcomes")
    elif not summary["proposals"]["valid"]:
        next_actions.append("check_policy_proposal_eligibility")
    if (
        summary["proposals"]["valid"]
        and not summary["evaluations"]["passed"]
        and not summary["evaluations"]["failed"]
    ):
        next_actions.append("run_paired_policy_evaluation")
    if (
        summary["evaluations"]["passed"]
        and not summary["approvals"]["valid"]
    ):
        next_actions.append("approve_passed_policy_evaluation")
    if summary["approvals"]["valid"] and not summary["changes"]["total"]:
        next_actions.append("apply_or_defer_approved_policy")
    if summary["changes"]["recoverable"]:
        next_actions.append("resume_interrupted_policy_change")
    if summary["changes"]["applied"]:
        next_actions.append("monitor_applied_policy")
    if not next_actions:
        next_actions.append("continue_normal_operation")
    return {
        "version": 1,
        "generated_at": feedback.utc_now(),
        "status": "attention" if invalid_count else "healthy",
        "roots": {
            "runs": display_path(runs_root),
            "proposals": display_path(proposals_dir),
            "evaluations": display_path(evaluations_dir),
            "approvals": display_path(approvals_dir),
            "changes": display_path(changes_dir),
        },
        "summary": summary,
        "next_actions": next_actions,
        "items": {
            "runs": runs,
            "proposals": proposals,
            "evaluations": evaluations,
            "approvals": approvals,
            "changes": changes,
        },
    }


def print_human(status: dict[str, Any]) -> None:
    summary = status["summary"]
    runs = summary["runs"]
    print(f"PSOS status: {status['status']}")
    print(
        "runs: "
        f"{runs['valid']}/{runs['total']} valid, "
        f"{runs['completed']} completed, "
        f"{runs['not_completed']} not completed"
    )
    print(
        "learning: "
        f"{runs['learning_events']} events, "
        f"{runs['promoted']} promoted, "
        f"{runs['rejected']} rejected, "
        f"{runs['unreviewed']} unreviewed"
    )
    print(
        "policy lifecycle: "
        f"{summary['proposals']['valid']} proposals, "
        f"{summary['evaluations']['passed']} passed evaluations, "
        f"{summary['approvals']['valid']} approvals, "
        f"{summary['changes']['applied']} applied changes"
    )
    print(f"invalid records: {summary['invalid_count']}")
    print("next: " + ", ".join(status["next_actions"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only PSOS lifecycle status and integrity audit.",
    )
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    parser.add_argument("--proposals-dir", type=Path, default=PROPOSALS_DIR)
    parser.add_argument("--evaluations-dir", type=Path, default=EVALUATIONS_DIR)
    parser.add_argument("--approvals-dir", type=Path, default=APPROVALS_DIR)
    parser.add_argument("--changes-dir", type=Path, default=CHANGES_DIR)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = build_status(
        runs_root=args.runs_root,
        proposals_dir=args.proposals_dir,
        evaluations_dir=args.evaluations_dir,
        approvals_dir=args.approvals_dir,
        changes_dir=args.changes_dir,
    )
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print_human(status)
    return 0 if status["status"] == "healthy" else 2


if __name__ == "__main__":
    raise SystemExit(main())
