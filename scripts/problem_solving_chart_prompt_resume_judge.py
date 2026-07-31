#!/usr/bin/env python3
"""Resume only the blind assessment for an existing chart prompt comparison run."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_chart_prompt_batch as BATCH  # noqa: E402


Invoker = Callable[
    [str, Path, str, Path, Sequence[Path], BATCH.RunProfile],
    dict[str, Any],
]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> Path:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def latest_run_dir() -> Path:
    root = BATCH.DEFAULT_RESULTS_DIR
    if not root.is_dir():
        raise BATCH.ChartPromptBatchError(
            f"차트 비교 실행 폴더가 없습니다: {root}"
        )
    runs = [path for path in root.iterdir() if path.is_dir()]
    if not runs:
        raise BATCH.ChartPromptBatchError(
            f"차트 비교 실행 결과가 없습니다: {root}"
        )
    return max(runs, key=lambda path: path.stat().st_mtime)


def load_existing_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    prompt_root = run_dir / "inputs" / "prompts"
    image_root = run_dir / "inputs" / "images"
    candidate_root = run_dir / "candidates"
    if not prompt_root.is_dir() or not image_root.is_dir() or not candidate_root.is_dir():
        raise BATCH.ChartPromptBatchError(
            f"재개 가능한 차트 비교 실행 폴더가 아닙니다: {run_dir}"
        )

    prompts: list[BATCH.PromptInput] = []
    prompt_paths: dict[str, Path] = {}
    for path in sorted(prompt_root.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise BATCH.ChartPromptBatchError(f"복사된 프롬프트가 비어 있습니다: {path}")
        label = path.stem
        prompts.append(
            BATCH.PromptInput(
                label=label,
                source_path=path,
                text=text,
                sha256=_sha256_text(text),
            )
        )
        prompt_paths[label] = path
    if len(prompts) < 2:
        raise BATCH.ChartPromptBatchError("복사된 프롬프트가 두 개 미만입니다.")

    image_paths = [path for path in sorted(image_root.iterdir()) if path.is_file()]
    images = BATCH.parse_images(image_paths, None)
    copied_images = [item.source_path for item in images]

    context_path = run_dir / "inputs" / "context.md"
    context = (
        context_path.read_text(encoding="utf-8").strip()
        if context_path.is_file()
        else ""
    )
    digest = BATCH._bundle_digest(prompts, images, context)
    mapping = BATCH.candidate_mapping([item.label for item in prompts], digest)

    answers: dict[str, str] = {}
    for candidate_id in mapping:
        json_path = candidate_root / f"{candidate_id}.json"
        if not json_path.is_file():
            raise BATCH.ChartPromptBatchError(
                f"기존 후보 결과가 없습니다: {json_path}"
            )
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BATCH.ChartPromptBatchError(
                f"기존 후보 결과 JSON을 읽을 수 없습니다: {json_path}: {exc}"
            ) from exc
        answer = BATCH.validate_answer(payload)
        answers[candidate_id] = answer["answer_markdown"]

    return {
        "run_dir": run_dir,
        "prompts": prompts,
        "prompt_paths": prompt_paths,
        "images": images,
        "copied_images": copied_images,
        "context": context,
        "digest": digest,
        "mapping": mapping,
        "answers": answers,
    }


def resume_blind_assessment(
    run_dir: Path,
    *,
    profile: BATCH.RunProfile,
    timeout_seconds: int = 900,
    invoker: Invoker | None = None,
) -> dict[str, Any]:
    loaded = load_existing_run(run_dir)
    run_dir = loaded["run_dir"]
    answers: Mapping[str, str] = loaded["answers"]
    copied_images: Sequence[Path] = loaded["copied_images"]
    context: str = loaded["context"]
    mapping: Mapping[str, str] = loaded["mapping"]
    prompt_paths: Mapping[str, Path] = loaded["prompt_paths"]

    runtime_invoker = invoker or BATCH.CodexImageInvoker(ROOT, timeout_seconds)
    print("기존 A~D 분석을 재사용해 최종 블라인드 평가만 실행합니다...", flush=True)
    raw_assessment = runtime_invoker(
        BATCH.build_assessment_prompt(answers, context, len(copied_images)),
        run_dir,
        "chart-analysis-blind-assessment",
        BATCH.ASSESSMENT_SCHEMA_PATH,
        copied_images,
        profile,
    )
    assessment = BATCH.validate_assessment(raw_assessment, set(mapping))
    _write_json(run_dir / "assessment.json", assessment)

    blind_text = BATCH._render_blind_report(
        copied_images,
        run_dir,
        answers,
        assessment,
    )
    blind_path = run_dir / "blind-report.md"
    blind_path.write_text(blind_text, encoding="utf-8")
    report_text = BATCH._render_revealed_report(
        blind_text,
        mapping,
        prompt_paths,
        run_dir,
    )
    report_path = run_dir / "report.md"
    report_path.write_text(report_text, encoding="utf-8")

    resume_manifest = {
        "version": 1,
        "resumed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "bundle_sha256": loaded["digest"],
        "profile": {
            "model": profile.model,
            "reasoning_effort": profile.reasoning_effort,
            "web_search": False,
            "sandbox": "read-only",
        },
        "candidate_mapping": mapping,
        "reused_candidate_ids": list(answers),
        "assessment_path": "assessment.json",
        "blind_report_path": "blind-report.md",
        "report_path": "report.md",
    }
    _write_json(run_dir / "resume-assessment-manifest.json", resume_manifest)
    return {
        "run_dir": str(run_dir),
        "report_path": str(report_path),
        "assessment_path": str(run_dir / "assessment.json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="기존 chart-prompt-comparison 실행 폴더. 생략하면 가장 최근 실행을 사용합니다.",
    )
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=sorted(BATCH.REASONING_EFFORTS),
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--open-report", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        run_dir = args.run_dir or latest_run_dir()
        profile = BATCH.resolve_profile(args.model, args.reasoning_effort)
        result = resume_blind_assessment(
            run_dir,
            profile=profile,
            timeout_seconds=args.timeout_seconds,
        )
    except (BATCH.ChartPromptBatchError, BATCH.OS.ProblemSolvingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result["report_path"])
    if args.open_report:
        webbrowser.open(Path(result["report_path"]).as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
