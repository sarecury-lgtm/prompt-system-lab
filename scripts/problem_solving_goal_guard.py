#!/usr/bin/env python3
"""Enforce the PSOS parent goal, architectural classification, and promotion gates."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_GOAL_PATH = ROOT / "ACTIVE_GOAL.json"
SCOPE_PATH = ROOT / "governance" / "PSOS_CHANGE_SCOPE.json"
REGRESSION_PATH = ROOT / "governance" / "PSOS_CROSS_DOMAIN_REGRESSION.json"

CHANGE_CLASSES = {"CORE", "ADAPTER", "DOMAIN", "TEST"}
STATUS_BY_CLASS = {
    "CORE": {"candidate", "canonical"},
    "ADAPTER": {"experimental", "stable"},
    "DOMAIN": {"test-only", "experimental"},
    "TEST": {"test-only"},
}
REQUIRED_NON_GOAL_MARKERS = (
    "shopping-only",
    "candidate-correction-only",
    "prompt-generation-only",
    "agents or model calls",
)
REQUIRED_INVARIANT_MARKERS = (
    "smallest sufficient",
    "failed or incomplete",
    "Domain tools remain optional",
    "Weak continuation language",
)


class GoalGuardError(ValueError):
    """Raised when repository state drifts from the declared PSOS goal."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GoalGuardError(f"필수 거버넌스 파일이 없습니다: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise GoalGuardError(
            f"JSON 형식이 올바르지 않습니다: {path.relative_to(ROOT)}:{exc.lineno}"
        ) from exc
    if not isinstance(payload, dict):
        raise GoalGuardError(f"최상위 JSON은 객체여야 합니다: {path.relative_to(ROOT)}")
    return payload


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoalGuardError(f"{label}이 비어 있습니다.")
    return value.strip()


def _string_list(value: Any, label: str, *, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise GoalGuardError(f"{label}은 비어 있지 않은 문자열 배열이어야 합니다.")
    cleaned = [item.strip() for item in value]
    if len(cleaned) < minimum:
        raise GoalGuardError(f"{label}은 최소 {minimum}개여야 합니다.")
    if len(set(cleaned)) != len(cleaned):
        raise GoalGuardError(f"{label}에 중복 항목이 있습니다.")
    return cleaned


def validate_active_goal(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "project",
        "parent_goal",
        "optimization_order",
        "non_goals",
        "invariants",
        "current_task",
        "continuation_policy",
        "promotion_policy",
        "required_reading",
    }
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise GoalGuardError(f"ACTIVE_GOAL 필드 불일치: missing={missing}, extra={extra}")
    if payload["version"] != 1:
        raise GoalGuardError("ACTIVE_GOAL version은 1이어야 합니다.")
    _text(payload["project"], "project")
    parent_goal = _text(payload["parent_goal"], "parent_goal")
    if "ordinary user request" not in parent_goal or "smallest sufficient" not in parent_goal:
        raise GoalGuardError("parent_goal이 범용 요청과 최소 충분 해결 원칙을 모두 고정하지 않습니다.")

    _string_list(payload["optimization_order"], "optimization_order", minimum=4)
    non_goals = _string_list(payload["non_goals"], "non_goals", minimum=4)
    non_goal_text = "\n".join(non_goals)
    for marker in REQUIRED_NON_GOAL_MARKERS:
        if marker not in non_goal_text:
            raise GoalGuardError(f"non_goals에 필수 drift 방지 항목이 없습니다: {marker}")

    invariants = _string_list(payload["invariants"], "invariants", minimum=5)
    invariant_text = "\n".join(invariants)
    for marker in REQUIRED_INVARIANT_MARKERS:
        if marker not in invariant_text:
            raise GoalGuardError(f"invariants에 필수 원칙이 없습니다: {marker}")

    task = payload["current_task"]
    if not isinstance(task, dict) or set(task) != {
        "id",
        "objective",
        "allowed_change_classes",
        "explicitly_out_of_scope",
        "completion_conditions",
    }:
        raise GoalGuardError("current_task 형식이 올바르지 않습니다.")
    _text(task["id"], "current_task.id")
    _text(task["objective"], "current_task.objective")
    allowed = set(_string_list(
        task["allowed_change_classes"],
        "current_task.allowed_change_classes",
        minimum=1,
    ))
    if not allowed <= CHANGE_CLASSES:
        raise GoalGuardError("current_task에 지원하지 않는 change class가 있습니다.")
    _string_list(task["explicitly_out_of_scope"], "current_task.explicitly_out_of_scope", minimum=2)
    _string_list(task["completion_conditions"], "current_task.completion_conditions", minimum=4)

    continuation = payload["continuation_policy"]
    if not isinstance(continuation, dict) or set(continuation) != {
        "weak_continuations",
        "meaning",
        "requires_explicit_approval",
    }:
        raise GoalGuardError("continuation_policy 형식이 올바르지 않습니다.")
    weak = _string_list(continuation["weak_continuations"], "weak_continuations", minimum=4)
    if "ㄱㄱ" not in weak or "continue" not in weak:
        raise GoalGuardError("한국어와 영어의 약한 진행 명령이 모두 정의되어야 합니다.")
    meaning = _text(continuation["meaning"], "continuation_policy.meaning")
    if "only the current_task" not in meaning:
        raise GoalGuardError("약한 진행 명령이 current_task만 계속한다는 규칙이 없습니다.")
    approvals = _string_list(
        continuation["requires_explicit_approval"],
        "continuation_policy.requires_explicit_approval",
        minimum=4,
    )
    approval_text = "\n".join(approvals)
    for marker in ("changing parent_goal", "promoting DOMAIN or TEST", "merging"):
        if marker not in approval_text:
            raise GoalGuardError(f"명시적 승인 항목이 빠졌습니다: {marker}")

    promotion = payload["promotion_policy"]
    if not isinstance(promotion, dict) or set(promotion) != {
        "minimum_distinct_domains_for_core",
        "required_domains",
        "requirements",
    }:
        raise GoalGuardError("promotion_policy 형식이 올바르지 않습니다.")
    minimum = promotion["minimum_distinct_domains_for_core"]
    if not isinstance(minimum, int) or minimum < 4:
        raise GoalGuardError("CORE 승격에는 최소 4개 서로 다른 도메인이 필요합니다.")
    domains = _string_list(promotion["required_domains"], "promotion_policy.required_domains", minimum=minimum)
    if len(set(domains)) < minimum:
        raise GoalGuardError("CORE 승격 도메인 수가 부족합니다.")
    _string_list(promotion["requirements"], "promotion_policy.requirements", minimum=5)

    required_reading = _string_list(payload["required_reading"], "required_reading", minimum=4)
    for required_path in ("PSOS_MASTER.md", "AGENTS.md", "governance/PSOS_CHANGE_SCOPE.json"):
        if required_path not in required_reading:
            raise GoalGuardError(f"required_reading에 {required_path}가 없습니다.")
        if not (ROOT / required_path).is_file():
            raise GoalGuardError(f"required_reading 파일이 실제로 없습니다: {required_path}")

    return dict(payload)


def validate_regression(
    payload: Mapping[str, Any],
    active_goal: Mapping[str, Any],
) -> dict[str, Any]:
    if set(payload) != {
        "version",
        "purpose",
        "minimum_distinct_domains_for_core",
        "cases",
    }:
        raise GoalGuardError("cross-domain regression 최상위 형식이 올바르지 않습니다.")
    if payload["version"] != 1:
        raise GoalGuardError("cross-domain regression version은 1이어야 합니다.")
    _text(payload["purpose"], "regression purpose")
    expected_minimum = active_goal["promotion_policy"]["minimum_distinct_domains_for_core"]
    if payload["minimum_distinct_domains_for_core"] != expected_minimum:
        raise GoalGuardError("ACTIVE_GOAL과 regression의 최소 도메인 수가 다릅니다.")

    cases = payload["cases"]
    if not isinstance(cases, list) or len(cases) < expected_minimum:
        raise GoalGuardError("cross-domain regression 사례 수가 부족합니다.")
    required = {
        "id",
        "domain",
        "request_type",
        "representative_request",
        "expected_primary_capability",
        "required_behavior",
        "forbidden_overreach",
    }
    ids: set[str] = set()
    domains: set[str] = set()
    allowed_capabilities = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT", "HYBRID"}
    for case in cases:
        if not isinstance(case, dict) or set(case) != required:
            raise GoalGuardError("cross-domain regression case 형식이 올바르지 않습니다.")
        case_id = _text(case["id"], "regression case id")
        if case_id in ids:
            raise GoalGuardError(f"regression case ID가 중복되었습니다: {case_id}")
        ids.add(case_id)
        domains.add(_text(case["domain"], f"{case_id}.domain"))
        _text(case["request_type"], f"{case_id}.request_type")
        _text(case["representative_request"], f"{case_id}.representative_request")
        if case["expected_primary_capability"] not in allowed_capabilities:
            raise GoalGuardError(f"{case_id}의 capability가 올바르지 않습니다.")
        _string_list(case["required_behavior"], f"{case_id}.required_behavior", minimum=2)
        _string_list(case["forbidden_overreach"], f"{case_id}.forbidden_overreach", minimum=2)
    if len(domains) < expected_minimum:
        raise GoalGuardError(
            f"CORE 승격용 regression 도메인이 {len(domains)}개뿐입니다; "
            f"최소 {expected_minimum}개가 필요합니다."
        )
    required_domains = set(active_goal["promotion_policy"]["required_domains"])
    unknown = domains - required_domains
    if unknown:
        raise GoalGuardError(f"ACTIVE_GOAL에 선언되지 않은 regression 도메인: {sorted(unknown)}")
    return dict(payload)


def validate_scope(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "version",
        "branch",
        "base",
        "declared_purpose",
        "parent_goal_link",
        "branch_status",
        "default_product_promotion_approved",
        "components",
        "explicit_reclassification",
    }
    if set(payload) != required:
        raise GoalGuardError("PSOS_CHANGE_SCOPE 최상위 형식이 올바르지 않습니다.")
    if payload["version"] != 1:
        raise GoalGuardError("PSOS_CHANGE_SCOPE version은 1이어야 합니다.")
    _text(payload["branch"], "scope.branch")
    _text(payload["base"], "scope.base")
    _text(payload["declared_purpose"], "scope.declared_purpose")
    if payload["parent_goal_link"] != "ACTIVE_GOAL.json":
        raise GoalGuardError("scope는 ACTIVE_GOAL.json을 parent goal로 사용해야 합니다.")
    if payload["branch_status"] not in {"experimental", "candidate", "stable"}:
        raise GoalGuardError("지원하지 않는 branch_status입니다.")
    if not isinstance(payload["default_product_promotion_approved"], bool):
        raise GoalGuardError("default_product_promotion_approved는 boolean이어야 합니다.")

    components = payload["components"]
    if not isinstance(components, list) or not components:
        raise GoalGuardError("scope components가 비어 있습니다.")
    ids: set[str] = set()
    pattern_owner: dict[str, str] = {}
    for component in components:
        required_component = {
            "id",
            "change_class",
            "promotion_status",
            "runtime_default_enabled",
            "purpose",
            "patterns",
        }
        if not isinstance(component, dict) or set(component) != required_component:
            raise GoalGuardError("scope component 형식이 올바르지 않습니다.")
        component_id = _text(component["id"], "component.id")
        if component_id in ids:
            raise GoalGuardError(f"component ID가 중복되었습니다: {component_id}")
        ids.add(component_id)
        change_class = component["change_class"]
        if change_class not in CHANGE_CLASSES:
            raise GoalGuardError(f"{component_id}: 지원하지 않는 change_class입니다.")
        if component["promotion_status"] not in STATUS_BY_CLASS[change_class]:
            raise GoalGuardError(
                f"{component_id}: {change_class}에 허용되지 않는 promotion_status입니다."
            )
        if not isinstance(component["runtime_default_enabled"], bool):
            raise GoalGuardError(f"{component_id}: runtime_default_enabled는 boolean이어야 합니다.")
        if change_class in {"DOMAIN", "TEST"} and component["runtime_default_enabled"]:
            raise GoalGuardError(
                f"{component_id}: {change_class} 작업은 기본 실행 경로가 될 수 없습니다."
            )
        _text(component["purpose"], f"{component_id}.purpose")
        patterns = _string_list(component["patterns"], f"{component_id}.patterns", minimum=1)
        for pattern in patterns:
            if pattern in pattern_owner:
                raise GoalGuardError(
                    f"동일 패턴이 두 component에 선언되었습니다: {pattern} "
                    f"({pattern_owner[pattern]}, {component_id})"
                )
            pattern_owner[pattern] = component_id
        if any("adaptive_shopping" in pattern for pattern in patterns) and change_class != "DOMAIN":
            raise GoalGuardError("adaptive shopping 구현은 DOMAIN으로 분류해야 합니다.")
        if any("candidate_" in pattern for pattern in patterns) and change_class == "CORE":
            raise GoalGuardError("candidate 전용 구현은 CORE로 분류할 수 없습니다.")
        if change_class == "CORE" and component["promotion_status"] == "canonical":
            if not payload["default_product_promotion_approved"]:
                raise GoalGuardError(
                    f"{component_id}: canonical CORE에는 별도의 기본 승격 승인이 필요합니다."
                )

    reclassified = payload["explicit_reclassification"]
    if not isinstance(reclassified, list) or len(reclassified) < 3:
        raise GoalGuardError("explicit_reclassification은 핵심 이탈 사례를 기록해야 합니다.")
    seen_subjects: set[str] = set()
    for item in reclassified:
        if not isinstance(item, dict) or set(item) != {"subject", "classification", "reason"}:
            raise GoalGuardError("explicit_reclassification 항목 형식이 올바르지 않습니다.")
        subject = _text(item["subject"], "reclassification.subject")
        if subject in seen_subjects:
            raise GoalGuardError(f"reclassification subject가 중복되었습니다: {subject}")
        seen_subjects.add(subject)
        if item["classification"] not in CHANGE_CLASSES:
            raise GoalGuardError("reclassification classification이 올바르지 않습니다.")
        _text(item["reason"], "reclassification.reason")
    return dict(payload)


def classify_path(path: str, scope: Mapping[str, Any]) -> dict[str, Any]:
    normalized = path.replace("\\", "/").lstrip("./")
    matches: list[dict[str, Any]] = []
    for component in scope["components"]:
        if any(fnmatch.fnmatchcase(normalized, pattern) for pattern in component["patterns"]):
            matches.append(component)
    if not matches:
        raise GoalGuardError(f"분류되지 않은 변경 파일입니다: {normalized}")
    if len(matches) > 1:
        raise GoalGuardError(
            f"두 개 이상의 component에 동시에 분류된 파일입니다: {normalized} -> "
            + ", ".join(item["id"] for item in matches)
        )
    return matches[0]


def validate_changed_files(
    changed_files: Iterable[str],
    scope: Mapping[str, Any],
) -> dict[str, list[str]]:
    classified: dict[str, list[str]] = {item: [] for item in sorted(CHANGE_CLASSES)}
    seen = False
    for raw_path in changed_files:
        path = raw_path.strip()
        if not path:
            continue
        seen = True
        component = classify_path(path, scope)
        classified[component["change_class"]].append(path.replace("\\", "/"))
    if not seen:
        raise GoalGuardError("검사할 변경 파일이 없습니다.")
    return classified


def git_changed_files(base: str, head: str = "HEAD") -> list[str]:
    command = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        f"{base}...{head}",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GoalGuardError(f"git diff를 읽지 못했습니다: {detail}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def run_guard(changed_files: Iterable[str]) -> dict[str, Any]:
    active = validate_active_goal(_load_json(ACTIVE_GOAL_PATH))
    regression = validate_regression(_load_json(REGRESSION_PATH), active)
    scope = validate_scope(_load_json(SCOPE_PATH))
    classified = validate_changed_files(changed_files, scope)
    return {
        "status": "pass",
        "parent_goal": active["parent_goal"],
        "current_task": active["current_task"]["id"],
        "distinct_regression_domains": len({case["domain"] for case in regression["cases"]}),
        "classified_files": classified,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        help="Git base ref used with three-dot diff, for example origin/main.",
    )
    parser.add_argument("--head", default="HEAD")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Explicit changed path. May be repeated; bypasses git diff when supplied.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.changed_file:
            changed = args.changed_file
        elif args.base:
            changed = git_changed_files(args.base, args.head)
        else:
            raise GoalGuardError("--base 또는 하나 이상의 --changed-file이 필요합니다.")
        result = run_guard(changed)
    except GoalGuardError as exc:
        print(f"PSOS goal guard: FAIL\n{exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PSOS goal guard: PASS")
        print(f"current task: {result['current_task']}")
        print(f"cross-domain evidence slots: {result['distinct_regression_domains']}")
        for change_class, paths in result["classified_files"].items():
            if paths:
                print(f"{change_class}: {len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
