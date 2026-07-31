#!/usr/bin/env python3
"""Prepare and finalize a manual baseline-versus-patch PROMPT review without an AI runner."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PROMPT_RUNTIME_PATH = ROOT / "scripts" / "prompt_runtime.py"
CASES_PATH = ROOT / "tests" / "fixtures" / "prompt-generation-applied-cases.json"
DEFAULT_OUTPUT_ROOT = ROOT / "runtime-results" / "prompt-patch-review"
REQUIRED_CASE_IDS = (
    "chart-trade-plan",
    "comment-natural-reply",
    "product-evidence-choice",
)
VARIANTS = ("baseline", "patched")
PLACEHOLDER = "<!-- 여기에 후보 답변을 붙여넣으세요 -->"


class PromptPatchReviewError(ValueError):
    """Raised when a manual review pack is incomplete or inconsistent."""


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROMPT_RUNTIME = _load_module(
    "prompt_runtime_for_manual_patch_review",
    PROMPT_RUNTIME_PATH,
)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptPatchReviewError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptPatchReviewError(f"{label}은 JSON 객체여야 합니다.")
    return value


def _write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")
    return path


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PromptPatchReviewError(f"{label}이 비어 있습니다.")
    return value.strip()


def load_cases(path: Path = CASES_PATH) -> dict[str, dict[str, Any]]:
    payload = _read_json(path, path.name)
    if payload.get("version") != 1 or not isinstance(payload.get("cases"), list):
        raise PromptPatchReviewError("적용 사례 fixture 형식이 올바르지 않습니다.")
    result: dict[str, dict[str, Any]] = {}
    for raw in payload["cases"]:
        if not isinstance(raw, dict):
            raise PromptPatchReviewError("적용 사례는 객체여야 합니다.")
        case_id = _require_text(raw.get("id"), "case.id")
        application = raw.get("application")
        if not isinstance(application, dict):
            raise PromptPatchReviewError(f"{case_id}.application이 객체가 아닙니다.")
        _require_text(application.get("input_markdown"), f"{case_id}.application.input")
        for key in ("criteria", "critical_failures"):
            values = application.get(key)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(item, str) or not item.strip() for item in values)
            ):
                raise PromptPatchReviewError(f"{case_id}.application.{key}가 올바르지 않습니다.")
        if case_id in result:
            raise PromptPatchReviewError(f"중복 case id: {case_id}")
        result[case_id] = raw
    return result


def baseline_prompt(case: Mapping[str, Any]) -> str:
    request = _require_text(case.get("request"), "case.request")
    baseline = PROMPT_RUNTIME.build_baseline(request, [])
    patterns = PROMPT_RUNTIME.normalize_patterns(list(case.get("used_patterns") or []))
    return (
        PROMPT_RUNTIME.build_pattern_only(baseline, patterns)
        if patterns
        else baseline
    )


def _patched_prompt(
    case: Mapping[str, Any],
    patch_dir: Path | None,
) -> tuple[str, str]:
    baseline = baseline_prompt(case)
    if patch_dir is None:
        return baseline, "baseline_retained"
    path = patch_dir / f"{case['id']}.md"
    if not path.is_file():
        return baseline, "baseline_retained"
    patched = _require_text(path.read_text(encoding="utf-8"), str(path))
    return patched, "patch_proposed" if patched != baseline else "baseline_retained"


def _candidate_mapping(case_id: str, baseline_sha: str, patched_sha: str) -> dict[str, str]:
    seed = f"{case_id}:{baseline_sha}:{patched_sha}"
    reverse = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 2
    ordered = list(reversed(VARIANTS)) if reverse else list(VARIANTS)
    return {"A": ordered[0], "B": ordered[1]}


def _case_pack_markdown(
    case: Mapping[str, Any],
    mapping: Mapping[str, str],
    prompts: Mapping[str, str],
) -> str:
    application = case["application"]
    criteria = "\n".join(f"- {item}" for item in application["criteria"])
    failures = "\n".join(f"- {item}" for item in application["critical_failures"])
    candidates = "\n\n".join(
        f"### 후보 {candidate_id}\n\n```text\n{prompts[variant]}\n```"
        for candidate_id, variant in mapping.items()
    )
    return f"""# {case['title']}

## 통제 과제 입력

{application['input_markdown']}

## 평가 기준

{criteria}

## 치명적 실패

{failures}

## 재사용 프롬프트 후보

{candidates}

## 실행 방법

1. 후보 A와 B를 각각 독립적으로 통제 과제 입력에 적용한다.
2. 결과 본문만 `answers/A.md`, `answers/B.md`에 넣는다.
3. 어느 후보가 baseline인지 추측하지 않고 `review.json`을 작성한다.
4. 짧다는 이유만으로 선호하지 않으며, 절차나 조건을 잃은 압축은 실패로 본다.
"""


def _review_template(case_id: str) -> dict[str, Any]:
    candidates = []
    for candidate_id in ("A", "B"):
        candidates.append(
            {
                "candidate_id": candidate_id,
                "requirement_preservation": 0,
                "task_correctness": 0,
                "actionability": 0,
                "calibration": 0,
                "format_cost": 0,
                "critical_failures": [],
                "finding": "",
            }
        )
    return {
        "version": 1,
        "case_id": case_id,
        "candidates": candidates,
        "preferred_candidate_ids": [],
        "conclusion": "",
    }


def prepare_review(
    *,
    case_ids: Sequence[str] = REQUIRED_CASE_IDS,
    patch_dir: Path | None = None,
    output_dir: Path | None = None,
    cases_path: Path = CASES_PATH,
) -> Path:
    cases = load_cases(cases_path)
    selected = list(case_ids)
    if not selected:
        raise PromptPatchReviewError("준비할 사례가 없습니다.")
    unknown = [case_id for case_id in selected if case_id not in cases]
    if unknown:
        raise PromptPatchReviewError("알 수 없는 case id: " + ", ".join(unknown))

    if output_dir is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = DEFAULT_OUTPUT_ROOT / stamp
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PromptPatchReviewError(f"출력 폴더가 비어 있지 않습니다: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_cases: list[dict[str, Any]] = []
    aggregate_sections = [
        "# PROMPT baseline·patch 수동 검증 팩",
        "",
        "이 팩은 Codex나 API를 호출하지 않는다. 같은 입력에 두 후보를 적용한 답변과 블라인드 판정만 기록한다.",
        "",
    ]

    for case_id in selected:
        case = cases[case_id]
        baseline = baseline_prompt(case)
        patched, proposal_status = _patched_prompt(case, patch_dir)
        prompts = {"baseline": baseline, "patched": patched}
        hashes = {key: _sha256_text(value) for key, value in prompts.items()}
        mapping = _candidate_mapping(case_id, hashes["baseline"], hashes["patched"])
        case_dir = output_dir / "cases" / case_id

        _write_text(case_dir / "prompts" / "baseline.md", baseline)
        _write_text(case_dir / "prompts" / "patched.md", patched)
        _write_text(case_dir / "answers" / "A.md", PLACEHOLDER)
        _write_text(case_dir / "answers" / "B.md", PLACEHOLDER)
        _write_json(case_dir / "review.json", _review_template(case_id))
        _write_json(
            case_dir / "mapping.private.json",
            {
                "version": 1,
                "case_id": case_id,
                "candidate_to_variant": mapping,
                "prompt_sha256": hashes,
            },
        )
        pack = _case_pack_markdown(case, mapping, prompts)
        _write_text(case_dir / "blind-pack.md", pack)
        _write_json(
            case_dir / "case.json",
            {
                "version": 1,
                "id": case_id,
                "title": case["title"],
                "request": case["request"],
                "application": case["application"],
                "proposal_status": proposal_status,
            },
        )
        aggregate_sections.extend([pack, "", "---", ""])

        manifest_cases.append(
            {
                "case_id": case_id,
                "title": case["title"],
                "directory": f"cases/{case_id}",
                "proposal_status": proposal_status,
                "patch_changed_prompt": hashes["baseline"] != hashes["patched"],
                "baseline_sha256": hashes["baseline"],
                "patched_sha256": hashes["patched"],
            }
        )

    _write_text(output_dir / "review-pack.md", "\n".join(aggregate_sections))
    _write_json(
        output_dir / "manifest.json",
        {
            "version": 1,
            "status": "awaiting_answers_and_blind_review",
            "engine": "none",
            "ai_runner_invoked": False,
            "cases_path": str(cases_path),
            "cases": manifest_cases,
        },
    )
    return output_dir


def _validate_review(value: Any, case_id: str) -> dict[str, Any]:
    expected = {
        "version",
        "case_id",
        "candidates",
        "preferred_candidate_ids",
        "conclusion",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise PromptPatchReviewError(f"{case_id}: review.json 필드가 올바르지 않습니다.")
    if value["version"] != 1 or value["case_id"] != case_id:
        raise PromptPatchReviewError(f"{case_id}: review 버전 또는 case_id가 다릅니다.")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise PromptPatchReviewError(f"{case_id}: 후보 평가는 정확히 2개여야 합니다.")
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, dict):
            raise PromptPatchReviewError(f"{case_id}: 후보 평가가 객체가 아닙니다.")
        expected_candidate = {
            "candidate_id",
            "requirement_preservation",
            "task_correctness",
            "actionability",
            "calibration",
            "format_cost",
            "critical_failures",
            "finding",
        }
        if set(item) != expected_candidate:
            raise PromptPatchReviewError(f"{case_id}: 후보 평가 필드가 올바르지 않습니다.")
        candidate_id = item["candidate_id"]
        if candidate_id not in {"A", "B"} or candidate_id in seen:
            raise PromptPatchReviewError(f"{case_id}: candidate_id가 올바르지 않습니다.")
        seen.add(candidate_id)
        for key in (
            "requirement_preservation",
            "task_correctness",
            "actionability",
            "calibration",
            "format_cost",
        ):
            if not isinstance(item[key], int) or not 1 <= item[key] <= 5:
                raise PromptPatchReviewError(f"{case_id}: {key}는 1~5 정수여야 합니다.")
        if not isinstance(item["critical_failures"], list) or any(
            not isinstance(entry, str) or not entry.strip()
            for entry in item["critical_failures"]
        ):
            raise PromptPatchReviewError(f"{case_id}: critical_failures가 올바르지 않습니다.")
        _require_text(item["finding"], f"{case_id}.{candidate_id}.finding")
    preferred = value["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or len(preferred) > 2
        or len(set(preferred)) != len(preferred)
        or any(item not in {"A", "B"} for item in preferred)
    ):
        raise PromptPatchReviewError(f"{case_id}: preferred_candidate_ids가 올바르지 않습니다.")
    _require_text(value["conclusion"], f"{case_id}.conclusion")
    return value


def _decision(
    mapping: Mapping[str, str],
    review: Mapping[str, Any],
    prompt_changed: bool,
) -> tuple[str, str]:
    if not prompt_changed:
        return "baseline_retained", "패치 후보가 baseline과 동일해 승격할 변경이 없습니다."

    preferred_variants = {
        mapping[candidate_id]
        for candidate_id in review["preferred_candidate_ids"]
    }
    candidate_records = {
        item["candidate_id"]: item for item in review["candidates"]
    }
    patched_ids = [
        candidate_id
        for candidate_id, variant in mapping.items()
        if variant == "patched"
    ]
    patched_failures = [
        failure
        for candidate_id in patched_ids
        for failure in candidate_records[candidate_id]["critical_failures"]
    ]
    if patched_failures:
        return "keep_baseline", "패치 후보에 치명적 실패가 기록되어 baseline을 유지합니다."
    if preferred_variants == {"patched"}:
        return "promote_patch", "블라인드 평가에서 패치 후보만 선호됐습니다."
    if preferred_variants == {"baseline"}:
        return "keep_baseline", "블라인드 평가에서 baseline 후보만 선호됐습니다."
    return "no_winner", "동률·무선호이므로 자동 승격하지 않습니다."


def finalize_review(run_dir: Path) -> Path:
    run_dir = run_dir.expanduser().resolve()
    manifest = _read_json(run_dir / "manifest.json", "manifest.json")
    if manifest.get("version") != 1 or not isinstance(manifest.get("cases"), list):
        raise PromptPatchReviewError("manifest.json 형식이 올바르지 않습니다.")

    rows: list[dict[str, Any]] = []
    for item in manifest["cases"]:
        case_id = _require_text(item.get("case_id"), "manifest.case_id")
        case_dir = run_dir / item["directory"]
        answers: dict[str, str] = {}
        for candidate_id in ("A", "B"):
            path = case_dir / "answers" / f"{candidate_id}.md"
            answer = _require_text(path.read_text(encoding="utf-8"), str(path))
            if PLACEHOLDER in answer:
                raise PromptPatchReviewError(f"{case_id}: 후보 {candidate_id} 답변이 비어 있습니다.")
            answers[candidate_id] = answer

        review = _validate_review(
            _read_json(case_dir / "review.json", f"{case_id}/review.json"),
            case_id,
        )
        mapping_record = _read_json(
            case_dir / "mapping.private.json",
            f"{case_id}/mapping.private.json",
        )
        mapping = mapping_record.get("candidate_to_variant")
        if not isinstance(mapping, dict) or set(mapping) != {"A", "B"}:
            raise PromptPatchReviewError(f"{case_id}: 후보 매핑이 올바르지 않습니다.")
        decision, reason = _decision(
            mapping,
            review,
            bool(item.get("patch_changed_prompt")),
        )
        revealed = {
            "version": 1,
            "case_id": case_id,
            "candidate_to_variant": mapping,
            "preferred_candidate_ids": review["preferred_candidate_ids"],
            "preferred_variants": [
                mapping[candidate_id]
                for candidate_id in review["preferred_candidate_ids"]
            ],
            "decision": decision,
            "reason": reason,
            "review_conclusion": review["conclusion"],
            "answer_sha256": {
                key: _sha256_text(value) for key, value in answers.items()
            },
        }
        _write_json(case_dir / "revealed-result.json", revealed)
        rows.append(
            {
                "case_id": case_id,
                "title": item["title"],
                "proposal_status": item["proposal_status"],
                "decision": decision,
                "reason": reason,
            }
        )

    status = (
        "completed_with_patch_candidates"
        if any(row["decision"] == "promote_patch" for row in rows)
        else "completed_without_promotion"
    )
    finalized = {**manifest, "status": status, "results": rows}
    _write_json(run_dir / "finalized.json", finalized)

    lines = [
        "# PROMPT baseline·patch 적용 검증 결과",
        "",
        "| 사례 | 패치 상태 | 판정 | 이유 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['title']} | {row['proposal_status']} | "
            f"**{row['decision']}** | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## 승격 규칙",
            "",
            "- `promote_patch`: 패치만 블라인드 선호되고 치명적 실패가 없음",
            "- `keep_baseline`: baseline 선호 또는 패치의 치명적 실패",
            "- `no_winner`: 동률·무선호",
            "- `baseline_retained`: 실제 패치가 제안되지 않음",
            "",
            "이 보고서는 후보 승격 권고만 기록하며 runtime bundle을 자동 변경하지 않습니다.",
        ]
    )
    report_path = _write_text(run_dir / "report.md", "\n".join(lines))
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="수동 블라인드 검증 팩 준비")
    prepare.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        choices=REQUIRED_CASE_IDS,
        help="포함할 사례. 생략하면 차트·댓글·상품 세 사례 모두 포함",
    )
    prepare.add_argument(
        "--patch-dir",
        type=Path,
        help="<case-id>.md 패치 후보 파일이 있는 폴더. 없는 사례는 baseline 유지",
    )
    prepare.add_argument("--output-dir", type=Path)
    prepare.add_argument("--cases", type=Path, default=CASES_PATH)

    finalize = subparsers.add_parser("finalize", help="답변과 블라인드 판정을 공개·정리")
    finalize.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            run_dir = prepare_review(
                case_ids=args.case_ids or REQUIRED_CASE_IDS,
                patch_dir=args.patch_dir,
                output_dir=args.output_dir,
                cases_path=args.cases,
            )
            print(f"검증 팩: {run_dir / 'review-pack.md'}")
            print(f"실행 폴더: {run_dir}")
            return 0
        report = finalize_review(args.run_dir)
        print(f"검증 결과: {report}")
        return 0
    except (OSError, PromptPatchReviewError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
