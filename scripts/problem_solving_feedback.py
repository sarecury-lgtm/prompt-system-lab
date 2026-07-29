#!/usr/bin/env python3
"""Record strong, explicit outcome feedback for a problem-solving run."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
REQUIRED_RUN_FILES = {
    "request.txt",
    "goal_ledger.json",
    "route.json",
    "result.md",
}
SIGNALS = {
    "adopted",
    "corrected",
    "rejected",
    "execution_succeeded",
    "execution_failed",
    "wrong_route",
}
EVIDENCE_REQUIRED_SIGNALS = {"adopted", "execution_succeeded"}
WEAK_FEEDBACK = {
    "좋아",
    "좋음",
    "ㅇㅇ",
    "응",
    "계속",
    "ㄱㄱ",
    "오케이",
    "ok",
    "okay",
    "good",
    "continue",
    "go",
}


class FeedbackError(Exception):
    """A feedback event that cannot be recorded safely."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_feedback(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.strip().lower(), flags=re.UNICODE)


def validate_meaningful_text(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise FeedbackError(f"{label}가 비어 있습니다.")
    if normalize_feedback(normalized) in {
        normalize_feedback(item) for item in WEAK_FEEDBACK
    }:
        raise FeedbackError(
            f"{label}가 약한 반응만 포함합니다. 실제 사용·정정·실행 결과를 구체적으로 기록하세요."
        )
    return normalized


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackError(f"JSON 파일을 읽을 수 없습니다: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FeedbackError(f"JSON 최상위 값은 object여야 합니다: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def validate_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = sorted(
        name for name in REQUIRED_RUN_FILES if not (run_dir / name).is_file()
    )
    if missing:
        raise FeedbackError(
            "학습 기록에 필요한 run 파일이 없습니다: " + ", ".join(missing)
        )
    ledger = read_json(run_dir / "goal_ledger.json")
    route = read_json(run_dir / "route.json")
    if not isinstance(route.get("selected_route"), str):
        raise FeedbackError("route.json.selected_route가 유효하지 않습니다.")
    if not isinstance(route.get("execution_status"), str):
        raise FeedbackError("route.json.execution_status가 유효하지 않습니다.")
    return ledger, route


def event_id(
    run_id: str,
    signal: str,
    note: str,
    evidence: list[str],
) -> str:
    canonical = json.dumps(
        {
            "run_id": run_id,
            "signal": signal,
            "note": note,
            "evidence": evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "feedback-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def initial_record(
    run_dir: Path,
    route: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": 1,
        "run_id": run_dir.name,
        "source": {
            "selected_route": route["selected_route"],
            "execution_status": route["execution_status"],
            "goal_ledger_sha256": file_sha256(run_dir / "goal_ledger.json"),
            "result_sha256": file_sha256(run_dir / "result.md"),
        },
        "events": [],
        "summary": {
            "event_count": 0,
            "signals": {},
            "last_recorded_at": None,
        },
        "default_policy_changed": False,
    }


def validate_existing_record(
    payload: dict[str, Any],
    run_dir: Path,
    route: dict[str, Any],
) -> dict[str, Any]:
    expected = {
        "version",
        "run_id",
        "source",
        "events",
        "summary",
        "default_policy_changed",
    }
    if set(payload) != expected or payload.get("version") != 1:
        raise FeedbackError("기존 learning_record.json 형식이 유효하지 않습니다.")
    if payload.get("run_id") != run_dir.name:
        raise FeedbackError("기존 learning record의 run_id가 디렉터리와 다릅니다.")
    if not isinstance(payload.get("events"), list):
        raise FeedbackError("기존 learning record의 events가 배열이 아닙니다.")
    if payload.get("default_policy_changed") is not False:
        raise FeedbackError("학습 기록이 기본 정책을 변경했다고 주장합니다.")
    event_fields = {
        "event_id",
        "recorded_at",
        "signal",
        "note",
        "evidence",
        "eligible_for_default_change",
        "promotion_state",
    }
    signals: dict[str, int] = {}
    for event in payload["events"]:
        if not isinstance(event, dict) or set(event) != event_fields:
            raise FeedbackError("기존 learning event 형식이 유효하지 않습니다.")
        if event.get("signal") not in SIGNALS:
            raise FeedbackError("기존 learning event signal이 유효하지 않습니다.")
        if event.get("eligible_for_default_change") is not False:
            raise FeedbackError("검토되지 않은 event가 기본값 변경 대상으로 표시됐습니다.")
        if event.get("promotion_state") != "candidate":
            raise FeedbackError("지원하지 않는 learning event 승격 상태입니다.")
        if not isinstance(event.get("evidence"), list):
            raise FeedbackError("기존 learning event evidence가 배열이 아닙니다.")
        signal = event["signal"]
        signals[signal] = signals.get(signal, 0) + 1
    expected_summary = {
        "event_count": len(payload["events"]),
        "signals": signals,
        "last_recorded_at": (
            payload["events"][-1]["recorded_at"] if payload["events"] else None
        ),
    }
    if payload.get("summary") != expected_summary:
        raise FeedbackError("기존 learning record summary가 event와 일치하지 않습니다.")
    expected_source = {
        "selected_route": route["selected_route"],
        "execution_status": route["execution_status"],
        "goal_ledger_sha256": file_sha256(run_dir / "goal_ledger.json"),
        "result_sha256": file_sha256(run_dir / "result.md"),
    }
    if payload.get("source") != expected_source:
        raise FeedbackError("run 산출물이 learning record 생성 후 변경되었습니다.")
    return payload


def record_feedback(
    run_id: str,
    signal: str,
    note: str,
    evidence: list[str] | None = None,
    *,
    runs_root: Path = RUNS_DIR,
) -> tuple[Path, dict[str, Any], bool]:
    if signal not in SIGNALS:
        raise FeedbackError(f"지원하지 않는 feedback signal입니다: {signal}")
    note = validate_meaningful_text(note, "note")
    evidence = [
        validate_meaningful_text(item, "evidence")
        for item in (evidence or [])
    ]
    if signal in EVIDENCE_REQUIRED_SIGNALS and not evidence:
        raise FeedbackError(
            f"{signal} 신호에는 실제 사용 또는 실행 결과 evidence가 필요합니다."
        )

    root = runs_root.expanduser().resolve()
    run_dir = (root / run_id).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise FeedbackError("run-id가 runs root 밖을 가리킵니다.") from exc
    if not run_dir.is_dir():
        raise FeedbackError(f"run 디렉터리가 없습니다: {run_dir}")
    _, route = validate_run(run_dir)

    record_path = run_dir / "learning_record.json"
    if record_path.is_file():
        record = validate_existing_record(read_json(record_path), run_dir, route)
    else:
        record = initial_record(run_dir, route)

    identifier = event_id(run_dir.name, signal, note, evidence)
    if any(item.get("event_id") == identifier for item in record["events"]):
        return record_path, record, False

    recorded_at = utc_now()
    event = {
        "event_id": identifier,
        "recorded_at": recorded_at,
        "signal": signal,
        "note": note,
        "evidence": evidence,
        "eligible_for_default_change": False,
        "promotion_state": "candidate",
    }
    record["events"].append(event)
    signals: dict[str, int] = {}
    for item in record["events"]:
        item_signal = item.get("signal")
        if isinstance(item_signal, str):
            signals[item_signal] = signals.get(item_signal, 0) + 1
    record["summary"] = {
        "event_count": len(record["events"]),
        "signals": signals,
        "last_recorded_at": recorded_at,
    }
    record["default_policy_changed"] = False
    atomic_write_json(record_path, record)
    return record_path, record, True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record explicit outcome feedback without changing default policy.",
    )
    parser.add_argument("--run-id", required=True, help="runs/<run-id>의 run id")
    parser.add_argument("--signal", required=True, choices=sorted(SIGNALS))
    parser.add_argument("--note", required=True, help="구체적인 채택·정정·실행 결과")
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="실제 사용 위치나 관찰 결과. 여러 번 지정 가능",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=RUNS_DIR,
        help="기본값: 저장소의 runs 디렉터리",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record_path, record, created = record_feedback(
            args.run_id,
            args.signal,
            args.note,
            args.evidence,
            runs_root=args.runs_root,
        )
    except FeedbackError as exc:
        print(f"feedback 기록 실패: {exc}", file=sys.stderr)
        return 2
    identifier = event_id(
        Path(args.run_id).name,
        args.signal,
        args.note.strip(),
        [item.strip() for item in args.evidence],
    )
    recorded_event = next(
        item for item in record["events"] if item["event_id"] == identifier
    )
    print(f"feedback 기록: {'created' if created else 'already_exists'}")
    print(f"signal: {recorded_event['signal']}")
    print(f"event_id: {recorded_event['event_id']}")
    print(f"default policy changed: no")
    print(f"record: {record_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
