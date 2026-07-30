#!/usr/bin/env python3
"""Build and persist request-specific PSOS result contracts.

Phase A keeps this module independent from the canonical runtime. It can build a
contract from an existing run's Goal Ledger and route record, which lets the
contract shape and regression fixtures stabilize before the runtime invokes it
between routing and execution.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROUTES = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT", "HYBRID"}
RESULT_TYPES = {
    "answer",
    "research",
    "asset_reuse",
    "reusable_prompt",
    "code_change",
    "project_step",
    "hybrid",
}
VERIFICATION_METHODS = {"text", "evidence", "url", "artifact", "receipt", "visual"}
EVIDENCE_TYPES = {"web", "local", "command_output", "provided_context", "image"}
FAILURE_POLICIES = {"partial", "blocked", "no_winner"}
REQUIREMENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

ROUTE_RESULT_TYPES = {
    "DIRECT": "answer",
    "RESEARCH": "research",
    "REUSE": "asset_reuse",
    "PROMPT": "reusable_prompt",
    "CODE": "code_change",
    "PROJECT": "project_step",
    "HYBRID": "hybrid",
}

ROUTE_COMPLETION_VERIFICATION = {
    "DIRECT": "text",
    "RESEARCH": "evidence",
    "REUSE": "receipt",
    "PROMPT": "text",
    "CODE": "receipt",
    "PROJECT": "receipt",
    "HYBRID": "text",
}

ROUTE_EVIDENCE_DEFAULTS = {
    "DIRECT": (0, (), False),
    "RESEARCH": (1, ("fact",), True),
    "REUSE": (1, ("fact",), True),
    "PROMPT": (0, (), False),
    "CODE": (0, (), False),
    "PROJECT": (0, (), False),
    "HYBRID": (0, (), False),
}

ROUTE_FAILURE_DEFAULTS = {
    "DIRECT": "partial",
    "RESEARCH": "partial",
    "REUSE": "blocked",
    "PROMPT": "partial",
    "CODE": "blocked",
    "PROJECT": "partial",
    "HYBRID": "partial",
}


class ResultContractError(ValueError):
    """Raised when a result contract cannot be built or validated."""


@dataclass(frozen=True)
class RequiredOutput:
    id: str
    description: str
    verification: str


@dataclass(frozen=True)
class EvidenceRequirements:
    minimum_sources: int = 0
    source_roles: tuple[str, ...] = field(default_factory=tuple)
    claim_source_mapping: bool = False


@dataclass(frozen=True)
class UserReview:
    needed: bool = False
    evidence_types: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResultContract:
    version: int
    route: str
    result_type: str
    must_preserve: tuple[str, ...]
    required_outputs: tuple[RequiredOutput, ...]
    evidence_requirements: EvidenceRequirements
    user_review: UserReview
    failure_policy: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["must_preserve"] = list(self.must_preserve)
        payload["required_outputs"] = [asdict(item) for item in self.required_outputs]
        payload["evidence_requirements"]["source_roles"] = list(
            self.evidence_requirements.source_roles
        )
        payload["user_review"]["evidence_types"] = list(
            self.user_review.evidence_types
        )
        return payload


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultContractError(f"{label} must be a non-empty string")
    return value.strip()


def _unique_strings(values: Any, label: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ResultContractError(f"{label} must be an array of strings")
    normalized: list[str] = []
    for value in values:
        item = _nonempty_string(value, label)
        if item not in normalized:
            normalized.append(item)
    if not allow_empty and not normalized:
        raise ResultContractError(f"{label} must not be empty")
    return tuple(normalized)


def required_output(value: RequiredOutput | Mapping[str, Any]) -> RequiredOutput:
    if isinstance(value, RequiredOutput):
        item = value
    elif isinstance(value, Mapping) and set(value) == {"id", "description", "verification"}:
        item = RequiredOutput(
            id=_nonempty_string(value["id"], "required_outputs.id"),
            description=_nonempty_string(
                value["description"], "required_outputs.description"
            ),
            verification=_nonempty_string(
                value["verification"], "required_outputs.verification"
            ),
        )
    else:
        raise ResultContractError(
            "required output must contain exactly id, description, and verification"
        )
    if not REQUIREMENT_ID_PATTERN.fullmatch(item.id):
        raise ResultContractError(f"invalid required output id: {item.id}")
    if item.verification not in VERIFICATION_METHODS:
        raise ResultContractError(
            f"unsupported verification method: {item.verification}"
        )
    return item


def evidence_requirements(
    value: EvidenceRequirements | Mapping[str, Any] | None,
    *,
    route: str,
) -> EvidenceRequirements:
    if value is None:
        minimum, roles, mapping = ROUTE_EVIDENCE_DEFAULTS[route]
        return EvidenceRequirements(minimum, tuple(roles), mapping)
    if isinstance(value, EvidenceRequirements):
        requirements = value
    elif isinstance(value, Mapping) and set(value) == {
        "minimum_sources",
        "source_roles",
        "claim_source_mapping",
    }:
        minimum_sources = value["minimum_sources"]
        if isinstance(minimum_sources, bool) or not isinstance(minimum_sources, int):
            raise ResultContractError("minimum_sources must be an integer")
        requirements = EvidenceRequirements(
            minimum_sources=minimum_sources,
            source_roles=_unique_strings(value["source_roles"], "source_roles"),
            claim_source_mapping=value["claim_source_mapping"],
        )
    else:
        raise ResultContractError(
            "evidence requirements must contain exactly minimum_sources, "
            "source_roles, and claim_source_mapping"
        )
    if requirements.minimum_sources < 0:
        raise ResultContractError("minimum_sources must be zero or greater")
    if not isinstance(requirements.claim_source_mapping, bool):
        raise ResultContractError("claim_source_mapping must be boolean")
    return requirements


def user_review(value: UserReview | Mapping[str, Any] | None) -> UserReview:
    if value is None:
        return UserReview()
    if isinstance(value, UserReview):
        review = value
    elif isinstance(value, Mapping) and set(value) == {"needed", "evidence_types"}:
        review = UserReview(
            needed=value["needed"],
            evidence_types=_unique_strings(value["evidence_types"], "evidence_types"),
        )
    else:
        raise ResultContractError(
            "user review must contain exactly needed and evidence_types"
        )
    if not isinstance(review.needed, bool):
        raise ResultContractError("user_review.needed must be boolean")
    unsupported = sorted(set(review.evidence_types) - EVIDENCE_TYPES)
    if unsupported:
        raise ResultContractError(
            "unsupported user review evidence types: " + ", ".join(unsupported)
        )
    if review.needed and not review.evidence_types:
        raise ResultContractError(
            "user review evidence_types must not be empty when review is needed"
        )
    return review


def _selected_route(route: str | Mapping[str, Any]) -> str:
    selected = route.get("selected_route") if isinstance(route, Mapping) else route
    selected = _nonempty_string(selected, "route")
    if selected not in ROUTES:
        raise ResultContractError(f"unsupported route: {selected}")
    return selected


def build_result_contract(
    route: str | Mapping[str, Any],
    ledger: Mapping[str, Any],
    *,
    additional_outputs: Sequence[RequiredOutput | Mapping[str, Any]] = (),
    evidence: EvidenceRequirements | Mapping[str, Any] | None = None,
    review: UserReview | Mapping[str, Any] | None = None,
    failure_policy: str | None = None,
    skip_simple_direct: bool = True,
) -> ResultContract | None:
    """Build a minimal contract without inferring domain rules from keywords.

    Route defaults provide only generic safety. Domain-specific requirements are
    passed declaratively through ``additional_outputs``, ``evidence``, and
    ``review``. This keeps peaches, products, comments, and other examples out of
    the core builder.
    """

    selected = _selected_route(route)
    if not isinstance(ledger, Mapping):
        raise ResultContractError("ledger must be an object")
    fixed_constraints = _unique_strings(
        ledger.get("fixed_constraints"),
        "ledger.fixed_constraints",
        allow_empty=False,
    )
    completion_condition = _nonempty_string(
        ledger.get("completion_condition"),
        "ledger.completion_condition",
    )
    uncertainties = _unique_strings(
        ledger.get("important_uncertainties", []),
        "ledger.important_uncertainties",
    )

    parsed_additional = tuple(required_output(item) for item in additional_outputs)
    parsed_review = user_review(review)
    if (
        selected == "DIRECT"
        and skip_simple_direct
        and not parsed_additional
        and not uncertainties
        and not parsed_review.needed
        and evidence is None
        and failure_policy is None
    ):
        return None

    outputs = (
        RequiredOutput(
            id="goal-completion",
            description=completion_condition,
            verification=ROUTE_COMPLETION_VERIFICATION[selected],
        ),
        *parsed_additional,
    )
    ids = [item.id for item in outputs]
    if len(ids) != len(set(ids)):
        raise ResultContractError("required output ids must be unique")

    chosen_failure_policy = failure_policy or ROUTE_FAILURE_DEFAULTS[selected]
    if chosen_failure_policy not in FAILURE_POLICIES:
        raise ResultContractError(
            f"unsupported failure policy: {chosen_failure_policy}"
        )

    contract = ResultContract(
        version=1,
        route=selected,
        result_type=ROUTE_RESULT_TYPES[selected],
        must_preserve=fixed_constraints,
        required_outputs=outputs,
        evidence_requirements=evidence_requirements(evidence, route=selected),
        user_review=parsed_review,
        failure_policy=chosen_failure_policy,
    )
    validate_result_contract(contract.to_dict())
    return contract


def validate_result_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "version",
        "route",
        "result_type",
        "must_preserve",
        "required_outputs",
        "evidence_requirements",
        "user_review",
        "failure_policy",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ResultContractError("result contract fields do not match the schema")
    if payload["version"] != 1:
        raise ResultContractError("unsupported result contract version")
    selected = _selected_route(payload["route"])
    result_type = _nonempty_string(payload["result_type"], "result_type")
    if result_type not in RESULT_TYPES:
        raise ResultContractError(f"unsupported result type: {result_type}")
    if result_type != ROUTE_RESULT_TYPES[selected]:
        raise ResultContractError("result type does not match route")
    _unique_strings(payload["must_preserve"], "must_preserve", allow_empty=False)
    raw_outputs = payload["required_outputs"]
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise ResultContractError("required_outputs must not be empty")
    outputs = tuple(required_output(item) for item in raw_outputs)
    ids = [item.id for item in outputs]
    if len(ids) != len(set(ids)):
        raise ResultContractError("required output ids must be unique")
    evidence_requirements(payload["evidence_requirements"], route=selected)
    user_review(payload["user_review"])
    if payload["failure_policy"] not in FAILURE_POLICIES:
        raise ResultContractError("unsupported failure policy")
    return json.loads(json.dumps(payload, ensure_ascii=False))


def write_result_contract(run_dir: Path, contract: ResultContract) -> Path:
    run_dir = run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        raise ResultContractError(f"run directory does not exist: {run_dir}")
    destination = run_dir / "result_contract.json"
    payload = validate_result_contract(contract.to_dict())
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=run_dir,
        prefix=".result-contract-",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        temp_path.replace(destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return destination


def load_run_inputs(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = run_dir.expanduser().resolve()
    try:
        ledger = json.loads((run_dir / "goal_ledger.json").read_text(encoding="utf-8"))
        route = json.loads((run_dir / "route.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultContractError(f"cannot read run routing records: {exc}") from exc
    if not isinstance(ledger, dict) or not isinstance(route, dict):
        raise ResultContractError("run routing records must be JSON objects")
    return ledger, route


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--include-simple-direct",
        action="store_true",
        help="write a minimal contract even for a simple DIRECT run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ledger, route = load_run_inputs(args.run_dir)
        contract = build_result_contract(
            route,
            ledger,
            skip_simple_direct=not args.include_simple_direct,
        )
        if contract is None:
            print("simple DIRECT run: no result contract needed")
            return 0
        path = write_result_contract(args.run_dir, contract)
    except ResultContractError as exc:
        print(f"error: {exc}")
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
