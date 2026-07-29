#!/usr/bin/env python3
"""Approve, atomically apply, and roll back evaluated policy changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_feedback as feedback
import problem_solving_os as runtime
import problem_solving_policy_evaluation as evaluation
import problem_solving_policy_proposal as proposal
import problem_solving_review as review


ROOT = SCRIPT_DIR.parent
RUNS_DIR = ROOT / "runs"
APPROVALS_DIR = ROOT / "policy-approvals"
CHANGES_DIR = ROOT / "policy-changes"


class PolicyChangeError(Exception):
    """A policy change that cannot proceed safely."""


def meaningful(value: str, label: str) -> str:
    try:
        return feedback.validate_meaningful_text(value, label)
    except feedback.FeedbackError as exc:
        raise PolicyChangeError(str(exc)) from exc


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return feedback.read_json(path.expanduser().resolve())
    except feedback.FeedbackError as exc:
        raise PolicyChangeError(f"{label}: {exc}") from exc


def portable_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def resolve_stored_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.expanduser().resolve()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as exc:
        raise PolicyChangeError(f"atomic file write failed: {path}: {exc}") from exc


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        feedback.atomic_write_json(path, payload)
    except OSError as exc:
        raise PolicyChangeError(f"atomic JSON write failed: {path}: {exc}") from exc


def ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PolicyChangeError(f"cannot create directory: {path}: {exc}") from exc


def validate_candidate_policy(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "router",
        "router_fallback",
        "routes",
    }:
        raise PolicyChangeError("candidate policy has invalid top-level fields.")
    if payload["version"] != 1:
        raise PolicyChangeError("candidate policy version is unsupported.")
    if not isinstance(payload["routes"], dict) or set(payload["routes"]) != (
        runtime.SINGLE_ROUTES
    ):
        raise PolicyChangeError("candidate policy does not define every route.")
    try:
        runtime.parse_model_profile(payload["router"], "router")
        runtime.parse_model_profile(
            payload["router_fallback"],
            "router_fallback",
        )
        for route, value in payload["routes"].items():
            if not isinstance(value, dict) or set(value) != {
                "primary",
                "fallback",
            }:
                raise PolicyChangeError(
                    f"candidate policy route is invalid: {route}"
                )
            runtime.parse_model_profile(
                value["primary"],
                f"routes.{route}.primary",
            )
            if value["fallback"] is not None:
                runtime.parse_model_profile(
                    value["fallback"],
                    f"routes.{route}.fallback",
                )
    except runtime.ProblemSolvingError as exc:
        raise PolicyChangeError(str(exc)) from exc


def load_validated_sources(
    proposal_path: Path,
    evaluation_path: Path,
    *,
    runs_root: Path,
    baseline_snapshot: dict[str, Any] | None = None,
    candidate_snapshot: dict[str, Any] | None = None,
) -> tuple[
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    proposal_file = proposal_path.expanduser().resolve()
    proposal_record = read_json(proposal_file, "proposal")
    try:
        baseline_policy, candidate_policy, route_scope = proposal.validate_proposal(
            proposal_record,
            runs_root=runs_root,
            policy_snapshot=baseline_snapshot,
        )
    except proposal.ProposalError as exc:
        raise PolicyChangeError(str(exc)) from exc
    validate_candidate_policy(candidate_policy)
    if candidate_snapshot is not None and candidate_policy != candidate_snapshot:
        raise PolicyChangeError(
            "approval candidate policy snapshot no longer matches."
        )
    evaluation_file = evaluation_path.expanduser().resolve()
    evaluation_record = read_json(evaluation_file, "evaluation")
    try:
        evaluation.validate_evaluation_record(
            evaluation_record,
            proposal_file,
            proposal_record,
            baseline_policy,
            candidate_policy,
            route_scope,
            runs_root=runs_root,
        )
    except evaluation.EvaluationError as exc:
        raise PolicyChangeError(str(exc)) from exc
    if evaluation_record["status"] != "passed":
        raise PolicyChangeError("only a passed evaluation can be approved.")
    return (
        proposal_file,
        proposal_record,
        evaluation_file,
        evaluation_record,
        baseline_policy,
        candidate_policy,
    )


def approval_id(
    proposal_sha256: str,
    evaluation_sha256: str,
    approver: str,
    reason: str,
    evidence: list[str],
) -> str:
    payload = {
        "proposal_sha256": proposal_sha256,
        "evaluation_sha256": evaluation_sha256,
        "approver": approver,
        "reason": reason,
        "evidence": evidence,
    }
    return "approval-" + review.canonical_sha256(payload)[:20]


def approve_policy_change(
    proposal_path: Path,
    evaluation_path: Path,
    approver: str,
    reason: str,
    evidence: list[str] | None = None,
    *,
    runs_root: Path = RUNS_DIR,
    output_dir: Path = APPROVALS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    approver = meaningful(approver, "approver")
    reason = meaningful(reason, "approval reason")
    evidence = [
        meaningful(value, "approval evidence")
        for value in (evidence or [])
    ]
    if not evidence:
        raise PolicyChangeError("approval requires at least one evidence item.")
    (
        proposal_file,
        proposal_record,
        evaluation_file,
        evaluation_record,
        baseline_policy,
        candidate_policy,
    ) = load_validated_sources(
        proposal_path,
        evaluation_path,
        runs_root=runs_root,
    )
    proposal_sha256 = feedback.file_sha256(proposal_file)
    evaluation_sha256 = feedback.file_sha256(evaluation_file)
    identifier = approval_id(
        proposal_sha256,
        evaluation_sha256,
        approver,
        reason,
        evidence,
    )
    payload = {
        "version": 1,
        "approval_id": identifier,
        "created_at": feedback.utc_now(),
        "decision": "approved",
        "sources": {
            "proposal_path": portable_path(proposal_file),
            "proposal_id": proposal_record["proposal_id"],
            "proposal_sha256": proposal_sha256,
            "evaluation_path": portable_path(evaluation_file),
            "evaluation_id": evaluation_record["evaluation_id"],
            "evaluation_sha256": evaluation_sha256,
        },
        "policy_snapshot": {
            "policy_path": proposal_record["target"]["policy_path"],
            "before_sha256": proposal_record["target"]["policy_sha256"],
            "after_sha256": bytes_sha256(json_bytes(candidate_policy)),
            "baseline": baseline_policy,
            "candidate": candidate_policy,
        },
        "approver": approver,
        "reason": reason,
        "evidence": evidence,
        "safeguards": {
            "one_time_application": True,
            "requires_explicit_policy_path": True,
            "backup_required": True,
            "rollback_required": True,
            "policy_applied": False,
        },
    }
    destination = output_dir.expanduser().resolve()
    ensure_directory(destination)
    path = destination / f"{identifier}.json"
    if path.is_file():
        existing = read_json(path, "existing approval")
        comparable = dict(payload)
        comparable["created_at"] = existing.get("created_at")
        if existing != comparable:
            raise PolicyChangeError("existing approval does not match.")
        return path, existing, False
    atomic_write_json(path, payload)
    return path, payload, True


def validate_approval(
    payload: dict[str, Any],
    *,
    runs_root: Path = RUNS_DIR,
) -> tuple[
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    expected = {
        "version",
        "approval_id",
        "created_at",
        "decision",
        "sources",
        "policy_snapshot",
        "approver",
        "reason",
        "evidence",
        "safeguards",
    }
    if set(payload) != expected or payload.get("version") != 1:
        raise PolicyChangeError("approval record has an invalid format.")
    if payload.get("decision") != "approved":
        raise PolicyChangeError("approval decision is not approved.")
    if not isinstance(payload.get("created_at"), str):
        raise PolicyChangeError("approval created_at is invalid.")
    approver = payload.get("approver")
    reason = payload.get("reason")
    evidence = payload.get("evidence")
    if not isinstance(approver, str) or not isinstance(reason, str):
        raise PolicyChangeError("approval identity or reason is invalid.")
    meaningful(approver, "approval approver")
    meaningful(reason, "approval reason")
    if not isinstance(evidence, list) or not evidence or not all(
        isinstance(value, str) for value in evidence
    ):
        raise PolicyChangeError("approval evidence is invalid.")
    for value in evidence:
        meaningful(value, "approval evidence")
    sources = payload.get("sources")
    source_fields = {
        "proposal_path",
        "proposal_id",
        "proposal_sha256",
        "evaluation_path",
        "evaluation_id",
        "evaluation_sha256",
    }
    if not isinstance(sources, dict) or set(sources) != source_fields:
        raise PolicyChangeError("approval sources are invalid.")
    if not isinstance(sources.get("proposal_path"), str) or not isinstance(
        sources.get("evaluation_path"), str
    ):
        raise PolicyChangeError("approval source paths are invalid.")
    proposal_file = resolve_stored_path(sources["proposal_path"])
    evaluation_file = resolve_stored_path(sources["evaluation_path"])
    policy_snapshot = payload.get("policy_snapshot")
    snapshot_fields = {
        "policy_path",
        "before_sha256",
        "after_sha256",
        "baseline",
        "candidate",
    }
    if not isinstance(policy_snapshot, dict) or set(policy_snapshot) != (
        snapshot_fields
    ):
        raise PolicyChangeError("approval policy snapshot is invalid.")
    baseline_snapshot = policy_snapshot.get("baseline")
    candidate_snapshot = policy_snapshot.get("candidate")
    if not isinstance(baseline_snapshot, dict) or not isinstance(
        candidate_snapshot, dict
    ):
        raise PolicyChangeError("approval policy snapshots must be objects.")
    loaded = load_validated_sources(
        proposal_file,
        evaluation_file,
        runs_root=runs_root,
        baseline_snapshot=baseline_snapshot,
        candidate_snapshot=candidate_snapshot,
    )
    proposal_record = loaded[1]
    evaluation_record = loaded[3]
    proposal_sha256 = feedback.file_sha256(proposal_file)
    evaluation_sha256 = feedback.file_sha256(evaluation_file)
    if sources != {
        "proposal_path": portable_path(proposal_file),
        "proposal_id": proposal_record["proposal_id"],
        "proposal_sha256": proposal_sha256,
        "evaluation_path": portable_path(evaluation_file),
        "evaluation_id": evaluation_record["evaluation_id"],
        "evaluation_sha256": evaluation_sha256,
    }:
        raise PolicyChangeError("approval sources no longer match.")
    proposal_record = loaded[1]
    expected_policy_snapshot = {
        "policy_path": proposal_record["target"]["policy_path"],
        "before_sha256": proposal_record["target"]["policy_sha256"],
        "after_sha256": bytes_sha256(json_bytes(loaded[5])),
        "baseline": loaded[4],
        "candidate": loaded[5],
    }
    if policy_snapshot != expected_policy_snapshot:
        raise PolicyChangeError("approval policy snapshot no longer matches.")
    expected_safeguards = {
        "one_time_application": True,
        "requires_explicit_policy_path": True,
        "backup_required": True,
        "rollback_required": True,
        "policy_applied": False,
    }
    if payload.get("safeguards") != expected_safeguards:
        raise PolicyChangeError("approval safeguards are invalid.")
    expected_id = approval_id(
        proposal_sha256,
        evaluation_sha256,
        approver,
        reason,
        evidence,
    )
    if payload.get("approval_id") != expected_id:
        raise PolicyChangeError("approval ID does not match its content.")
    return loaded


def change_id(
    approval_identifier: str,
    before_sha256: str,
    after_sha256: str,
) -> str:
    payload = {
        "approval_id": approval_identifier,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
    }
    return "change-" + review.canonical_sha256(payload)[:20]


def expected_change_record(
    identifier: str,
    approval_file: Path,
    approval_record: dict[str, Any],
    policy_file: Path,
    backup_path: Path,
    before_sha256: str,
    after_sha256: str,
    *,
    prepared_at: str,
    status: str,
    applied_at: str | None,
    rolled_back_at: str | None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "change_id": identifier,
        "status": status,
        "approval": {
            "approval_path": portable_path(approval_file),
            "approval_id": approval_record["approval_id"],
            "approval_sha256": feedback.file_sha256(approval_file),
        },
        "policy_path": portable_path(policy_file),
        "backup_path": portable_path(backup_path),
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "prepared_at": prepared_at,
        "applied_at": applied_at,
        "rolled_back_at": rolled_back_at,
    }


def validate_change_receipt(
    receipt: dict[str, Any],
    identifier: str,
    approval_file: Path,
    approval_record: dict[str, Any],
    policy_file: Path,
    backup_path: Path,
    before_sha256: str,
    after_sha256: str,
) -> dict[str, Any]:
    required = {
        "version",
        "change_id",
        "status",
        "approval",
        "policy_path",
        "backup_path",
        "before_sha256",
        "after_sha256",
        "prepared_at",
        "applied_at",
        "rolled_back_at",
    }
    if set(receipt) != required or receipt.get("version") != 1:
        raise PolicyChangeError("change receipt has an invalid format.")
    if receipt.get("change_id") != identifier:
        raise PolicyChangeError("change receipt ID does not match.")
    status = receipt.get("status")
    if status not in {"prepared", "applied", "rolled_back"}:
        raise PolicyChangeError("change receipt state is invalid.")
    prepared_at = receipt.get("prepared_at")
    applied_at = receipt.get("applied_at")
    rolled_back_at = receipt.get("rolled_back_at")
    if not isinstance(prepared_at, str):
        raise PolicyChangeError("change prepared_at is invalid.")
    if status == "prepared" and (
        applied_at is not None or rolled_back_at is not None
    ):
        raise PolicyChangeError("prepared receipt has invalid timestamps.")
    if status == "applied" and (
        not isinstance(applied_at, str) or rolled_back_at is not None
    ):
        raise PolicyChangeError("applied receipt has invalid timestamps.")
    if status == "rolled_back" and (
        not isinstance(applied_at, str)
        or not isinstance(rolled_back_at, str)
    ):
        raise PolicyChangeError("rolled-back receipt has invalid timestamps.")
    expected = expected_change_record(
        identifier,
        approval_file,
        approval_record,
        policy_file,
        backup_path,
        before_sha256,
        after_sha256,
        prepared_at=prepared_at,
        status=status,
        applied_at=applied_at,
        rolled_back_at=rolled_back_at,
    )
    if receipt != expected:
        raise PolicyChangeError("change receipt does not match approved sources.")
    return receipt


def apply_policy_change(
    approval_path: Path,
    expected_policy_path: Path,
    *,
    runs_root: Path = RUNS_DIR,
    changes_dir: Path = CHANGES_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    approval_file = approval_path.expanduser().resolve()
    approval_record = read_json(approval_file, "approval")
    loaded = validate_approval(approval_record, runs_root=runs_root)
    proposal_record = loaded[1]
    baseline_policy = loaded[4]
    candidate_policy = loaded[5]
    policy_file = expected_policy_path.expanduser().resolve()
    stored_policy_file = resolve_stored_path(
        proposal_record["target"]["policy_path"]
    )
    if policy_file != stored_policy_file:
        raise PolicyChangeError(
            "explicit policy path does not match the approved proposal."
        )
    if not policy_file.is_file():
        raise PolicyChangeError(f"active policy file does not exist: {policy_file}")
    after_bytes = json_bytes(candidate_policy)
    before_sha256 = feedback.file_sha256(policy_file)
    proposal_before_sha256 = proposal_record["target"]["policy_sha256"]
    if before_sha256 != proposal_before_sha256:
        candidate_sha256 = bytes_sha256(after_bytes)
        if before_sha256 != candidate_sha256:
            raise PolicyChangeError("active policy changed after approval.")
    else:
        candidate_sha256 = bytes_sha256(after_bytes)

    destination = changes_dir.expanduser().resolve()
    ensure_directory(destination)
    identifier = change_id(
        approval_record["approval_id"],
        proposal_before_sha256,
        candidate_sha256,
    )
    backup_path = destination / f"{identifier}.before.json"
    receipt_path = destination / f"{identifier}.json"
    original_bytes = policy_file.read_bytes()
    if backup_path.is_file():
        if feedback.file_sha256(backup_path) != proposal_before_sha256:
            raise PolicyChangeError("existing policy backup is invalid.")
    else:
        if bytes_sha256(original_bytes) != proposal_before_sha256:
            raise PolicyChangeError(
                "cannot create backup after policy already changed."
            )
        atomic_write_bytes(backup_path, original_bytes)

    if receipt_path.is_file():
        receipt = read_json(receipt_path, "change receipt")
        validate_change_receipt(
            receipt,
            identifier,
            approval_file,
            approval_record,
            policy_file,
            backup_path,
            proposal_before_sha256,
            candidate_sha256,
        )
        status = receipt.get("status")
        active_sha256 = feedback.file_sha256(policy_file)
        if status == "applied" and active_sha256 == candidate_sha256:
            return receipt_path, receipt, False
        if status == "rolled_back" and active_sha256 == proposal_before_sha256:
            raise PolicyChangeError("a rolled-back approval cannot be reapplied.")
        if status != "prepared":
            raise PolicyChangeError("change receipt has an invalid state.")
        prepared_at = receipt.get("prepared_at")
        if not isinstance(prepared_at, str):
            raise PolicyChangeError("prepared receipt timestamp is invalid.")
    else:
        prepared_at = feedback.utc_now()
        receipt = expected_change_record(
            identifier,
            approval_file,
            approval_record,
            policy_file,
            backup_path,
            proposal_before_sha256,
            candidate_sha256,
            prepared_at=prepared_at,
            status="prepared",
            applied_at=None,
            rolled_back_at=None,
        )
        atomic_write_json(receipt_path, receipt)

    active_sha256 = feedback.file_sha256(policy_file)
    if active_sha256 == proposal_before_sha256:
        atomic_write_bytes(policy_file, after_bytes)
    elif active_sha256 != candidate_sha256:
        raise PolicyChangeError("active policy changed during application.")
    if feedback.file_sha256(policy_file) != candidate_sha256:
        raise PolicyChangeError("candidate policy write verification failed.")
    applied = expected_change_record(
        identifier,
        approval_file,
        approval_record,
        policy_file,
        backup_path,
        proposal_before_sha256,
        candidate_sha256,
        prepared_at=prepared_at,
        status="applied",
        applied_at=feedback.utc_now(),
        rolled_back_at=None,
    )
    atomic_write_json(receipt_path, applied)
    return receipt_path, applied, True


def rollback_policy_change(
    receipt_path: Path,
    expected_policy_path: Path,
    *,
    runs_root: Path = RUNS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    receipt_file = receipt_path.expanduser().resolve()
    receipt = read_json(receipt_file, "change receipt")
    approval_reference = receipt.get("approval")
    if not isinstance(approval_reference, dict) or set(approval_reference) != {
        "approval_path",
        "approval_id",
        "approval_sha256",
    }:
        raise PolicyChangeError("change approval reference is invalid.")
    approval_path_value = approval_reference.get("approval_path")
    if not isinstance(approval_path_value, str):
        raise PolicyChangeError("change approval path is invalid.")
    approval_file = resolve_stored_path(approval_path_value)
    approval_record = read_json(approval_file, "approval")
    loaded = validate_approval(approval_record, runs_root=runs_root)
    proposal_record = loaded[1]
    candidate_policy = loaded[5]
    if approval_reference != {
        "approval_path": portable_path(approval_file),
        "approval_id": approval_record["approval_id"],
        "approval_sha256": feedback.file_sha256(approval_file),
    }:
        raise PolicyChangeError("change approval reference no longer matches.")
    policy_file = expected_policy_path.expanduser().resolve()
    proposal_policy_file = resolve_stored_path(
        proposal_record["target"]["policy_path"]
    )
    if policy_file != proposal_policy_file:
        raise PolicyChangeError(
            "explicit policy path does not match the approved proposal."
        )
    if not policy_file.is_file():
        raise PolicyChangeError(f"active policy file does not exist: {policy_file}")
    before_sha256 = proposal_record["target"]["policy_sha256"]
    after_sha256 = bytes_sha256(json_bytes(candidate_policy))
    identifier = change_id(
        approval_record["approval_id"],
        before_sha256,
        after_sha256,
    )
    if receipt_file.name != f"{identifier}.json":
        raise PolicyChangeError("change receipt filename does not match.")
    backup_path = receipt_file.parent / f"{identifier}.before.json"
    validate_change_receipt(
        receipt,
        identifier,
        approval_file,
        approval_record,
        policy_file,
        backup_path,
        before_sha256,
        after_sha256,
    )
    if not backup_path.is_file():
        raise PolicyChangeError("policy backup does not exist.")
    if feedback.file_sha256(backup_path) != receipt["before_sha256"]:
        raise PolicyChangeError("policy backup hash does not match receipt.")
    active_sha256 = feedback.file_sha256(policy_file)
    if receipt["status"] == "rolled_back":
        if active_sha256 != receipt["before_sha256"]:
            raise PolicyChangeError("rolled-back policy changed unexpectedly.")
        return receipt_file, receipt, False
    if receipt["status"] != "applied":
        raise PolicyChangeError("only an applied change can be rolled back.")
    if active_sha256 == receipt["after_sha256"]:
        atomic_write_bytes(policy_file, backup_path.read_bytes())
    elif active_sha256 != receipt["before_sha256"]:
        raise PolicyChangeError(
            "active policy changed after application; refusing rollback."
        )
    if feedback.file_sha256(policy_file) != receipt["before_sha256"]:
        raise PolicyChangeError("rollback write verification failed.")
    rolled_back = dict(receipt)
    rolled_back["status"] = "rolled_back"
    rolled_back["rolled_back_at"] = feedback.utc_now()
    atomic_write_json(receipt_file, rolled_back)
    return receipt_file, rolled_back, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Approve, apply, or roll back an evaluated policy change.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    approve = subparsers.add_parser("approve")
    approve.add_argument("--proposal", required=True, type=Path)
    approve.add_argument("--evaluation", required=True, type=Path)
    approve.add_argument("--approver", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--evidence", action="append", default=[])
    approve.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    approve.add_argument("--output-dir", type=Path, default=APPROVALS_DIR)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--approval", required=True, type=Path)
    apply_parser.add_argument("--policy-path", required=True, type=Path)
    apply_parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    apply_parser.add_argument("--changes-dir", type=Path, default=CHANGES_DIR)
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--receipt", required=True, type=Path)
    rollback.add_argument("--policy-path", required=True, type=Path)
    rollback.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "approve":
            path, record, changed = approve_policy_change(
                args.proposal,
                args.evaluation,
                args.approver,
                args.reason,
                args.evidence,
                runs_root=args.runs_root,
                output_dir=args.output_dir,
            )
            print(
                f"policy approval: {'created' if changed else 'already_exists'}"
            )
            print(f"approval_id: {record['approval_id']}")
            print("policy applied: no")
        elif args.command == "apply":
            path, record, changed = apply_policy_change(
                args.approval,
                args.policy_path,
                runs_root=args.runs_root,
                changes_dir=args.changes_dir,
            )
            print(
                f"policy change: {'applied' if changed else 'already_applied'}"
            )
            print(f"change_id: {record['change_id']}")
            print(f"status: {record['status']}")
        else:
            path, record, changed = rollback_policy_change(
                args.receipt,
                args.policy_path,
                runs_root=args.runs_root,
            )
            print(
                f"policy rollback: {'rolled_back' if changed else 'already_rolled_back'}"
            )
            print(f"change_id: {record['change_id']}")
            print(f"status: {record['status']}")
    except PolicyChangeError as exc:
        print(f"policy change failed: {exc}", file=sys.stderr)
        return 2
    print(f"record: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
