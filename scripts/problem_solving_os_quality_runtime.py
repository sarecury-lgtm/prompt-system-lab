#!/usr/bin/env python3
"""Run PSOS with corrected routing, Result Contract enforcement, evidence review, and PROMPT diagnostics."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os_contract_runtime.py"
EVIDENCE_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_evidence_bundle.py"
PROMPT_BRIEF_PATH = ROOT / "scripts" / "problem_solving_prompt_build_brief.py"
PROMPT_BRIEF_TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_brief_trace.py"
PROMPT_TRACE_PATH = ROOT / "scripts" / "problem_solving_prompt_trace.py"
PROMPT_CAUSAL_AUDIT_PATH = ROOT / "scripts" / "problem_solving_prompt_causal_audit.py"
PROMPT_ABLATION_PATH = ROOT / "scripts" / "problem_solving_prompt_ablation.py"
CORE_FIXES_PATH = ROOT / "scripts" / "problem_solving_core_semantic_fixes.py"
QUALITY_FIXES_PATH = ROOT / "scripts" / "problem_solving_quality_semantic_fixes.py"


def _load_local_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACT_RUNTIME = _load_local_module(
    "psos_contract_quality_runtime",
    CONTRACT_RUNTIME_PATH,
)
EVIDENCE = _load_local_module(
    "psos_evidence_bundle_runtime",
    EVIDENCE_RUNTIME_PATH,
)
PROMPT_BRIEF = _load_local_module(
    "psos_prompt_build_brief_runtime",
    PROMPT_BRIEF_PATH,
)
PROMPT_BRIEF_TRACE = _load_local_module(
    "psos_prompt_build_brief_trace_runtime",
    PROMPT_BRIEF_TRACE_PATH,
)
PROMPT_TRACE = _load_local_module(
    "psos_prompt_generation_trace",
    PROMPT_TRACE_PATH,
)
PROMPT_CAUSAL_AUDIT = _load_local_module(
    "psos_prompt_generation_causal_audit",
    PROMPT_CAUSAL_AUDIT_PATH,
)
PROMPT_ABLATION = _load_local_module(
    "psos_prompt_generation_ablation",
    PROMPT_ABLATION_PATH,
)
CORE_FIXES = _load_local_module(
    "psos_core_semantic_fixes",
    CORE_FIXES_PATH,
)
QUALITY_FIXES = _load_local_module(
    "psos_quality_semantic_fixes",
    QUALITY_FIXES_PATH,
)
OS = CONTRACT_RUNTIME.OS
CORE_FIXES.apply(OS)
QUALITY_FIXES.apply(CONTRACT_RUNTIME, EVIDENCE)


def _persist_quality_record(
    run_dir: Path,
    payload: dict[str, Any],
    key: str,
    record: dict[str, Any] | None,
) -> None:
    if record is None:
        return
    payload[key] = record
    if isinstance(payload.get("run"), dict):
        payload["run"][key] = record
    route_path = run_dir / "route.json"
    route_record = json.loads(route_path.read_text(encoding="utf-8"))
    route_record[key] = record
    if isinstance(route_record.get("run"), dict):
        route_record["run"][key] = record
    OS.write_json(route_path, route_record)


def _attach_user_output(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist the actual user-facing output separately from the PSOS audit view."""

    text = str(payload["execution"].get("result_markdown", "")).strip()
    output_path = run_dir / "output.md"
    output_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
    record = {
        "version": 1,
        "path": output_path.name,
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "kind": "user_output",
    }
    _persist_quality_record(run_dir, payload, "output", record)
    return record


def _brief_entry(payload: dict[str, Any]) -> dict[str, Any] | None:
    record = payload.get("prompt_build_brief")
    if not isinstance(record, dict) or record.get("status") != "applied":
        return None
    entries = record.get("entries")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        return None
    return entries[0]


def _attach_prompt_trace(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        if _brief_entry(payload) is not None:
            record = PROMPT_BRIEF_TRACE.attach_prompt_brief_trace(run_dir, payload)
        else:
            record = PROMPT_TRACE.attach_prompt_generation_trace(run_dir, payload)
    except (
        PROMPT_TRACE.PromptTraceError,
        PROMPT_BRIEF_TRACE.PromptBriefTraceError,
    ) as exc:
        record = {
            "version": 1,
            "status": "unavailable",
            "error": str(exc),
            "error_path": "prompt_generation_trace_error.json",
        }
        OS.write_json(run_dir / record["error_path"], record)
    _persist_quality_record(run_dir, payload, "prompt_generation_trace", record)
    return record


def _attach_prompt_causal_audit(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    brief = _brief_entry(payload)
    if brief is not None:
        audit = {
            "version": 2,
            "status": "intervention_applied",
            "previous_cause": "원문·Goal Ledger·Compiler baseline의 압축 없는 병렬 합류",
            "intervention": "Prompt Build Brief 단일 입력 계약",
            "legacy_executor_input": brief["original_executor_input_path"],
            "brief": brief["brief_path"],
            "new_executor_contract": "원문·전체 Ledger·baseline을 최종 Executor에 직접 전달하지 않음",
            "remaining_question": "실제 입력에 적용했을 때 판단 품질이 개선되는지 비교 필요",
        }
        json_path = run_dir / "prompt_generation_causal_audit.json"
        OS.write_json(json_path, audit)
        markdown_path = run_dir / "prompt_generation_causal_audit.md"
        markdown_path.write_text(
            "# PROMPT 생성 인과 감사 · Brief 개입 후\n\n"
            "- 이전 원인: 원문·Goal Ledger·Compiler baseline의 압축 없는 병렬 합류\n"
            "- 적용한 개입: Prompt Build Brief 단일 입력 계약\n"
            f"- 이전 Executor 입력: `{brief['original_executor_input_path']}`\n"
            f"- 통합 Brief: `{brief['brief_path']}`\n"
            "- 남은 검증: 생성된 프롬프트를 실제 입력에 적용해 판단 품질 비교\n",
            encoding="utf-8",
        )
        record = {
            "version": 2,
            "status": "intervention_applied",
            "json_path": json_path.name,
            "markdown_path": markdown_path.name,
        }
    else:
        try:
            record = PROMPT_CAUSAL_AUDIT.attach_prompt_generation_causal_audit(
                run_dir,
                payload,
            )
        except (
            PROMPT_CAUSAL_AUDIT.PromptCausalAuditError,
            PROMPT_CAUSAL_AUDIT.TRACE.PromptTraceError,
        ) as exc:
            record = {
                "version": 1,
                "status": "unavailable",
                "error": str(exc),
                "error_path": "prompt_generation_causal_audit_error.json",
            }
            OS.write_json(run_dir / record["error_path"], record)
    _persist_quality_record(
        run_dir,
        payload,
        "prompt_generation_causal_audit",
        record,
    )
    return record


def _attach_prompt_ablation(
    run_dir: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    brief = _brief_entry(payload)
    if brief is not None:
        output_dir = run_dir / "prompt_ablation"
        output_dir.mkdir(exist_ok=True)
        manifest = {
            "version": 2,
            "status": "superseded_by_prompt_build_brief",
            "legacy_executor_input": brief["original_executor_input_path"],
            "current_brief": brief["brief_path"],
            "current_executor_input_contract": "single_prompt_build_brief",
            "boundary": (
                "이 run에서는 진단 결과를 반영한 Brief 경로가 이미 실행됐습니다. "
                "이전 방식과의 실제 품질 비교는 저장된 legacy 입력과 현재 결과를 별도 실행해 수행합니다."
            ),
        }
        manifest_path = output_dir / "manifest.json"
        OS.write_json(manifest_path, manifest)
        record = {
            "version": 2,
            "status": manifest["status"],
            "directory": output_dir.relative_to(run_dir).as_posix(),
            "manifest_path": manifest_path.relative_to(run_dir).as_posix(),
            "legacy_executor_input": brief["original_executor_input_path"],
            "current_brief": brief["brief_path"],
        }
    else:
        try:
            record = PROMPT_ABLATION.attach_prompt_ablation_variants(
                run_dir,
                payload,
            )
        except (
            PROMPT_ABLATION.PromptAblationError,
            PROMPT_ABLATION.TRACE.PromptTraceError,
        ) as exc:
            record = {
                "version": 1,
                "status": "unavailable",
                "error": str(exc),
                "error_path": "prompt_ablation_error.json",
            }
            OS.write_json(run_dir / record["error_path"], record)
    _persist_quality_record(run_dir, payload, "prompt_ablation", record)
    return record


def run_request(
    request: str,
    *,
    context_path: Path | None = None,
    output_root: Path = OS.RUNS_DIR,
    engine: Any,
    model_policy: dict[str, Any] | None = None,
    model_policy_path: Path = OS.DEFAULT_MODEL_POLICY_PATH,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    prompt_brief_engine = PROMPT_BRIEF.PromptBuildBriefEngine(
        engine,
        request=request,
        os_module=OS,
    )
    run_dir, payload = CONTRACT_RUNTIME.run_request(
        request,
        context_path=context_path,
        output_root=output_root,
        engine=prompt_brief_engine,
        model_policy=model_policy,
        model_policy_path=model_policy_path,
        run_id=run_id,
    )
    _persist_quality_record(
        run_dir,
        payload,
        "prompt_build_brief",
        prompt_brief_engine.record(),
    )
    _attach_user_output(run_dir, payload)
    QUALITY_FIXES.set_workspace_root(EVIDENCE, engine)
    evidence_record = EVIDENCE.attach_evidence_bundle(run_dir, payload)
    _persist_quality_record(run_dir, payload, "evidence_bundle", evidence_record)
    _attach_prompt_trace(run_dir, payload)
    _attach_prompt_causal_audit(run_dir, payload)
    _attach_prompt_ablation(run_dir, payload)
    return run_dir, payload


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = OS.build_parser().parse_args(argv)
    if args.allow_workspace_write and not args.write_scope:
        print(
            "ERROR: --allow-workspace-write에는 --write-scope가 하나 이상 필요합니다.",
            file=sys.stderr,
        )
        return 1
    if args.write_scope and not args.allow_workspace_write:
        print(
            "ERROR: --write-scope는 --allow-workspace-write와 함께 사용해야 합니다.",
            file=sys.stderr,
        )
        return 1

    allowed_write_paths: list[str] | None = None
    write_approval: dict[str, Any] | None = None
    if args.allow_workspace_write:
        try:
            allowed_write_paths, write_approval = OS.build_cli_write_approval(
                args.workspace,
                args.request,
                args.write_scope,
            )
        except OS.ProblemSolvingError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    engine = OS.CodexEngine(
        args.workspace,
        allow_workspace_write=args.allow_workspace_write,
        allowed_write_paths=allowed_write_paths,
        write_approval=write_approval,
        enable_search=not args.no_search,
    )
    try:
        run_dir, payload = run_request(
            args.request,
            context_path=args.context_file,
            output_root=args.runs_dir,
            engine=engine,
            model_policy_path=args.model_policy,
            run_id=args.run_id,
        )
    except (OS.ProblemSolvingError, EVIDENCE.EvidenceBundleError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print((run_dir / "output.md").read_text(encoding="utf-8").rstrip())
    if "evidence_bundle" in payload:
        print(f"\n근거 검토: {run_dir / payload['evidence_bundle']['review_markdown']}")
    prompt_brief = payload.get("prompt_build_brief")
    if isinstance(prompt_brief, dict):
        entries = prompt_brief.get("entries") or []
        if entries:
            print(f"\nPrompt Build Brief: {run_dir / entries[0]['markdown_path']}")
    prompt_trace = payload.get("prompt_generation_trace")
    if isinstance(prompt_trace, dict) and prompt_trace.get("markdown_path"):
        print(f"\nPROMPT 생성 진단: {run_dir / prompt_trace['markdown_path']}")
    causal_audit = payload.get("prompt_generation_causal_audit")
    if isinstance(causal_audit, dict) and causal_audit.get("markdown_path"):
        print(f"\nPROMPT 인과 감사: {run_dir / causal_audit['markdown_path']}")
    ablation = payload.get("prompt_ablation")
    if isinstance(ablation, dict) and ablation.get("manifest_path"):
        print(f"\nPROMPT 비교 입력: {run_dir / ablation['manifest_path']}")
    print(f"\n실행 기록: {run_dir}")
    return 2 if payload["execution"]["status"] == "blocked_by_capability" else 0


if __name__ == "__main__":
    raise SystemExit(main())
