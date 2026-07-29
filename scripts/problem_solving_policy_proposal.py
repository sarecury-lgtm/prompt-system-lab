#!/usr/bin/env python3
"""Build an auditable policy proposal from independently reviewed outcomes."""

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
import problem_solving_review as review


ROOT = SCRIPT_DIR.parent
RUNS_DIR = ROOT / "runs"
POLICY_PATH = ROOT / "problem-solving-project" / "model-policy.json"
PROPOSALS_DIR = ROOT / "policy-proposals"
POLICY_LEAVES = {"model", "reasoning_effort", "web_search", "sandbox"}
MINIMUM_INDEPENDENT_RUNS = 2


class ProposalError(Exception):
    """A policy proposal that cannot be built safely."""


def meaningful(value: str, label: str) -> str:
    try:
        return feedback.validate_meaningful_text(value, label)
    except feedback.FeedbackError as exc:
        raise ProposalError(str(exc)) from exc


def parse_candidate(value: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ProposalError(
            "candidate must use RUN_ID:EVENT_ID format."
        )
    return parts[0].strip(), parts[1].strip()


def parse_proposed_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def policy_target(
    policy: dict[str, Any],
    target_path: str,
) -> tuple[Any, str | None]:
    parts = target_path.split(".")
    if (
        len(parts) == 2
        and parts[0] in {"router", "router_fallback"}
        and parts[1] in POLICY_LEAVES
    ):
        route_scope = None
    elif (
        len(parts) == 4
        and parts[0] == "routes"
        and parts[2] in {"primary", "fallback"}
        and parts[3] in POLICY_LEAVES
    ):
        route_scope = parts[1]
    else:
        raise ProposalError(
            "target must be router.<setting>, router_fallback.<setting>, "
            "or routes.<ROUTE>.<primary|fallback>.<setting>."
        )

    current: Any = policy
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise ProposalError(f"policy target does not exist: {target_path}")
        current = current[part]
    return current, route_scope


def load_promoted_candidate(
    run_id: str,
    event_id: str,
    *,
    runs_root: Path,
) -> dict[str, Any]:
    try:
        run_dir = review.resolve_run(run_id, runs_root)
        learning = review.load_learning_record(run_dir)
    except review.ReviewError as exc:
        raise ProposalError(str(exc)) from exc

    review_path = run_dir / "learning_review.json"
    if not review_path.is_file():
        raise ProposalError(f"learning review does not exist: {review_path}")
    try:
        review_record = review.validate_review_record(
            feedback.read_json(review_path),
            run_dir,
            learning,
        )
    except (feedback.FeedbackError, review.ReviewError) as exc:
        raise ProposalError(str(exc)) from exc

    event = next(
        (item for item in learning["events"] if item["event_id"] == event_id),
        None,
    )
    if event is None:
        raise ProposalError(
            f"learning event does not exist: {run_id}:{event_id}"
        )
    decision = next(
        (
            item
            for item in review_record["decisions"]
            if item["event_id"] == event_id
        ),
        None,
    )
    if (
        decision is None
        or decision["decision"] != "promote"
        or decision["eligible_for_policy_proposal"] is not True
        or decision["policy_applied"] is not False
    ):
        raise ProposalError(
            f"candidate is not promoted for policy proposal: {run_id}:{event_id}"
        )
    return {
        "run_id": run_dir.name,
        "event_id": event_id,
        "review_id": decision["review_id"],
        "event_sha256": decision["event_sha256"],
        "signal": event["signal"],
        "selected_route": learning["source"]["selected_route"],
        "goal_ledger_sha256": learning["source"]["goal_ledger_sha256"],
        "result_sha256": learning["source"]["result_sha256"],
        "reviewer": decision["reviewer"],
        "review_reason": decision["reason"],
        "review_evidence": decision["evidence"],
    }


def proposal_id(
    policy_sha256: str,
    title: str,
    target_path: str,
    proposed_value: Any,
    rationale: str,
    candidates: list[dict[str, Any]],
) -> str:
    payload = {
        "policy_sha256": policy_sha256,
        "title": title,
        "target_path": target_path,
        "proposed_value": proposed_value,
        "rationale": rationale,
        "review_ids": sorted(item["review_id"] for item in candidates),
    }
    return "proposal-" + review.canonical_sha256(payload)[:20]


def validate_independence(candidates: list[dict[str, Any]]) -> None:
    if len(candidates) < MINIMUM_INDEPENDENT_RUNS:
        raise ProposalError(
            f"at least {MINIMUM_INDEPENDENT_RUNS} promoted candidates are required."
        )
    run_ids = {item["run_id"] for item in candidates}
    if len(run_ids) < MINIMUM_INDEPENDENT_RUNS:
        raise ProposalError(
            f"at least {MINIMUM_INDEPENDENT_RUNS} distinct runs are required."
        )
    event_keys = {
        (item["run_id"], item["event_id"])
        for item in candidates
    }
    if len(event_keys) != len(candidates):
        raise ProposalError("the same candidate was supplied more than once.")
    source_fingerprints = {
        (
            item["goal_ledger_sha256"],
            item["result_sha256"],
        )
        for item in candidates
    }
    if len(source_fingerprints) < MINIMUM_INDEPENDENT_RUNS:
        raise ProposalError(
            "candidate runs do not have independent Goal Ledger and result hashes."
        )


def build_proposal(
    title: str,
    target_path: str,
    proposed_value: Any,
    rationale: str,
    candidate_keys: list[tuple[str, str]],
    *,
    runs_root: Path = RUNS_DIR,
    policy_path: Path = POLICY_PATH,
    output_dir: Path = PROPOSALS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    title = meaningful(title, "title")
    rationale = meaningful(rationale, "rationale")
    try:
        policy = feedback.read_json(policy_path.expanduser().resolve())
    except feedback.FeedbackError as exc:
        raise ProposalError(str(exc)) from exc
    current_value, route_scope = policy_target(policy, target_path)
    if type(current_value) is not type(proposed_value):
        raise ProposalError(
            "proposed value type does not match the current policy value type."
        )
    if current_value == proposed_value:
        raise ProposalError("proposed value is identical to the current policy value.")

    candidates = [
        load_promoted_candidate(
            run_id,
            event_id,
            runs_root=runs_root,
        )
        for run_id, event_id in candidate_keys
    ]
    candidates.sort(key=lambda item: (item["run_id"], item["event_id"]))
    validate_independence(candidates)
    if route_scope is not None:
        mismatched = [
            item["run_id"]
            for item in candidates
            if item["selected_route"] != route_scope
        ]
        if mismatched:
            raise ProposalError(
                f"route-specific target {route_scope} has evidence from other routes: "
                + ", ".join(mismatched)
            )

    policy_file = policy_path.expanduser().resolve()
    policy_sha256 = feedback.file_sha256(policy_file)
    try:
        policy_display_path = policy_file.relative_to(ROOT).as_posix()
    except ValueError:
        policy_display_path = str(policy_file)
    identifier = proposal_id(
        policy_sha256,
        title,
        target_path,
        proposed_value,
        rationale,
        candidates,
    )
    payload = {
        "version": 1,
        "proposal_id": identifier,
        "created_at": feedback.utc_now(),
        "status": "draft",
        "title": title,
        "target": {
            "policy_path": policy_display_path,
            "policy_sha256": policy_sha256,
            "json_path": target_path,
            "current_value": current_value,
            "proposed_value": proposed_value,
        },
        "rationale": rationale,
        "candidates": candidates,
        "evidence_summary": {
            "candidate_count": len(candidates),
            "independent_run_count": len(
                {item["run_id"] for item in candidates}
            ),
            "signals": sorted({item["signal"] for item in candidates}),
            "routes": sorted({item["selected_route"] for item in candidates}),
        },
        "safeguards": {
            "minimum_independent_runs": MINIMUM_INDEPENDENT_RUNS,
            "automatic_application_allowed": False,
            "requires_evaluation": True,
            "requires_human_approval": True,
            "default_policy_changed": False,
        },
    }
    destination = output_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    proposal_path = destination / f"{identifier}.json"
    if proposal_path.is_file():
        try:
            existing = feedback.read_json(proposal_path)
        except feedback.FeedbackError as exc:
            raise ProposalError(str(exc)) from exc
        comparable = dict(payload)
        comparable["created_at"] = existing.get("created_at")
        if existing != comparable:
            raise ProposalError(
                "existing proposal file does not match the requested proposal."
            )
        return proposal_path, existing, False
    feedback.atomic_write_json(proposal_path, payload)
    return proposal_path, payload, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a draft policy proposal from at least two independently "
            "reviewed outcomes without modifying the active policy."
        ),
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--proposed-value", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="RUN_ID:EVENT_ID; repeat for each promoted candidate",
    )
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    parser.add_argument("--policy-path", type=Path, default=POLICY_PATH)
    parser.add_argument("--output-dir", type=Path, default=PROPOSALS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path, proposal, created = build_proposal(
            args.title,
            args.target,
            parse_proposed_value(args.proposed_value),
            args.rationale,
            [parse_candidate(value) for value in args.candidate],
            runs_root=args.runs_root,
            policy_path=args.policy_path,
            output_dir=args.output_dir,
        )
    except ProposalError as exc:
        print(f"policy proposal failed: {exc}", file=sys.stderr)
        return 2
    print(f"policy proposal: {'created' if created else 'already_exists'}")
    print(f"proposal_id: {proposal['proposal_id']}")
    print(f"status: {proposal['status']}")
    print(
        "independent runs: "
        f"{proposal['evidence_summary']['independent_run_count']}"
    )
    print("default policy changed: no")
    print(f"proposal: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
