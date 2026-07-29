#!/usr/bin/env python3
"""Manually review outcome-learning candidates without changing policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_feedback as feedback


ROOT = SCRIPT_DIR.parent
RUNS_DIR = ROOT / "runs"
DECISIONS = {"promote", "reject"}


class ReviewError(Exception):
    """A learning candidate that cannot be reviewed safely."""


def canonical_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def review_id(
    run_id: str,
    event_id: str,
    decision: str,
    reviewer: str,
    reason: str,
    evidence: list[str],
) -> str:
    payload = {
        "run_id": run_id,
        "event_id": event_id,
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
        "evidence": evidence,
    }
    return "review-" + canonical_sha256(payload)[:20]


def meaningful(value: str, label: str) -> str:
    try:
        return feedback.validate_meaningful_text(value, label)
    except feedback.FeedbackError as exc:
        raise ReviewError(str(exc)) from exc


def resolve_run(run_id: str, runs_root: Path) -> Path:
    root = runs_root.expanduser().resolve()
    run_dir = (root / run_id).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise ReviewError("run-id points outside the runs root.") from exc
    if not run_dir.is_dir():
        raise ReviewError(f"run directory does not exist: {run_dir}")
    return run_dir


def load_learning_record(run_dir: Path) -> dict[str, Any]:
    record_path = run_dir / "learning_record.json"
    if not record_path.is_file():
        raise ReviewError(f"learning record does not exist: {record_path}")
    try:
        _, route = feedback.validate_run(run_dir)
        return feedback.validate_existing_record(
            feedback.read_json(record_path),
            run_dir,
            route,
        )
    except feedback.FeedbackError as exc:
        raise ReviewError(str(exc)) from exc


def initial_review_record(
    run_dir: Path,
    learning_record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": 1,
        "run_id": run_dir.name,
        "source": dict(learning_record["source"]),
        "decisions": [],
        "summary": {
            "decision_count": 0,
            "promoted": 0,
            "rejected": 0,
        },
        "default_policy_changed": False,
    }


def validate_review_record(
    payload: dict[str, Any],
    run_dir: Path,
    learning_record: dict[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "version",
        "run_id",
        "source",
        "decisions",
        "summary",
        "default_policy_changed",
    }
    if set(payload) != expected_fields or payload.get("version") != 1:
        raise ReviewError("existing learning_review.json has an invalid format.")
    if payload.get("run_id") != run_dir.name:
        raise ReviewError("review run_id does not match the run directory.")
    if payload.get("source") != learning_record["source"]:
        raise ReviewError("review source does not match the learning record.")
    if payload.get("default_policy_changed") is not False:
        raise ReviewError("review record claims that default policy changed.")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ReviewError("review decisions must be an array.")

    events = {
        event["event_id"]: event
        for event in learning_record["events"]
    }
    decision_fields = {
        "review_id",
        "recorded_at",
        "event_id",
        "event_sha256",
        "decision",
        "reviewer",
        "reason",
        "evidence",
        "eligible_for_policy_proposal",
        "policy_applied",
    }
    reviewed_events: set[str] = set()
    seen_review_ids: set[str] = set()
    promoted = 0
    rejected = 0
    for item in decisions:
        if not isinstance(item, dict) or set(item) != decision_fields:
            raise ReviewError("existing review decision has an invalid format.")
        decision = item.get("decision")
        if decision not in DECISIONS:
            raise ReviewError("existing review decision is not supported.")
        event_identifier = item.get("event_id")
        event = events.get(event_identifier)
        if event is None:
            raise ReviewError("review decision references an unknown event.")
        if item.get("event_sha256") != canonical_sha256(event):
            raise ReviewError("review decision event hash does not match.")
        if event_identifier in reviewed_events:
            raise ReviewError("an event has more than one immutable decision.")
        reviewed_events.add(event_identifier)

        reviewer = item.get("reviewer")
        reason = item.get("reason")
        evidence = item.get("evidence")
        if not isinstance(reviewer, str) or not isinstance(reason, str):
            raise ReviewError("reviewer and reason must be strings.")
        meaningful(reviewer, "existing reviewer")
        meaningful(reason, "existing review reason")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(value, str) for value in evidence
        ):
            raise ReviewError("existing review evidence must be a non-empty string array.")
        for value in evidence:
            meaningful(value, "existing review evidence")
        if not isinstance(item.get("recorded_at"), str):
            raise ReviewError("existing review recorded_at is invalid.")

        identifier = review_id(
            run_dir.name,
            event_identifier,
            decision,
            reviewer,
            reason,
            evidence,
        )
        if item.get("review_id") != identifier:
            raise ReviewError("existing review ID does not match its content.")
        if identifier in seen_review_ids:
            raise ReviewError("existing review ID is duplicated.")
        seen_review_ids.add(identifier)

        eligible = decision == "promote"
        if item.get("eligible_for_policy_proposal") is not eligible:
            raise ReviewError("review eligibility does not match its decision.")
        if item.get("policy_applied") is not False:
            raise ReviewError("review decision claims that policy was applied.")
        if eligible:
            promoted += 1
        else:
            rejected += 1

    expected_summary = {
        "decision_count": len(decisions),
        "promoted": promoted,
        "rejected": rejected,
    }
    if payload.get("summary") != expected_summary:
        raise ReviewError("review summary does not match its decisions.")
    return payload


def record_review(
    run_id: str,
    event_identifier: str,
    decision: str,
    reviewer: str,
    reason: str,
    evidence: list[str] | None = None,
    *,
    runs_root: Path = RUNS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    if decision not in DECISIONS:
        raise ReviewError(f"unsupported review decision: {decision}")
    reviewer = meaningful(reviewer, "reviewer")
    reason = meaningful(reason, "reason")
    evidence = [
        meaningful(value, "evidence")
        for value in (evidence or [])
    ]
    if not evidence:
        raise ReviewError("manual review requires at least one evidence item.")

    run_dir = resolve_run(run_id, runs_root)
    learning_record = load_learning_record(run_dir)
    event = next(
        (
            item
            for item in learning_record["events"]
            if item["event_id"] == event_identifier
        ),
        None,
    )
    if event is None:
        raise ReviewError(f"learning event does not exist: {event_identifier}")

    record_path = run_dir / "learning_review.json"
    if record_path.is_file():
        try:
            review_record = feedback.read_json(record_path)
        except feedback.FeedbackError as exc:
            raise ReviewError(str(exc)) from exc
        review_record = validate_review_record(
            review_record,
            run_dir,
            learning_record,
        )
    else:
        review_record = initial_review_record(run_dir, learning_record)

    identifier = review_id(
        run_dir.name,
        event_identifier,
        decision,
        reviewer,
        reason,
        evidence,
    )
    existing = next(
        (
            item
            for item in review_record["decisions"]
            if item["event_id"] == event_identifier
        ),
        None,
    )
    if existing is not None:
        if existing["review_id"] == identifier:
            return record_path, review_record, False
        raise ReviewError(
            "this event already has an immutable review decision; "
            "record a new feedback event instead of overwriting it."
        )

    item = {
        "review_id": identifier,
        "recorded_at": feedback.utc_now(),
        "event_id": event_identifier,
        "event_sha256": canonical_sha256(event),
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
        "evidence": evidence,
        "eligible_for_policy_proposal": decision == "promote",
        "policy_applied": False,
    }
    review_record["decisions"].append(item)
    review_record["summary"] = {
        "decision_count": len(review_record["decisions"]),
        "promoted": sum(
            value["decision"] == "promote"
            for value in review_record["decisions"]
        ),
        "rejected": sum(
            value["decision"] == "reject"
            for value in review_record["decisions"]
        ),
    }
    review_record["default_policy_changed"] = False
    feedback.atomic_write_json(record_path, review_record)
    return record_path, review_record, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manually promote or reject one learning candidate without "
            "changing model or route policy."
        ),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path, record, created = record_review(
            args.run_id,
            args.event_id,
            args.decision,
            args.reviewer,
            args.reason,
            args.evidence,
            runs_root=args.runs_root,
        )
    except ReviewError as exc:
        print(f"learning review failed: {exc}", file=sys.stderr)
        return 2

    identifier = review_id(
        Path(args.run_id).name,
        args.event_id,
        args.decision,
        args.reviewer.strip(),
        args.reason.strip(),
        [value.strip() for value in args.evidence],
    )
    reviewed = next(
        item for item in record["decisions"] if item["review_id"] == identifier
    )
    print(f"learning review: {'created' if created else 'already_exists'}")
    print(f"decision: {reviewed['decision']}")
    print(f"review_id: {reviewed['review_id']}")
    print(f"eligible for policy proposal: {str(reviewed['eligible_for_policy_proposal']).lower()}")
    print("default policy changed: no")
    print(f"record: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
