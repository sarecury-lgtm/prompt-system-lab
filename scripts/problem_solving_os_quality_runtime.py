#!/usr/bin/env python3
"""Run PSOS with corrected routing, Result Contract enforcement, and evidence review."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_os_contract_runtime.py"
EVIDENCE_RUNTIME_PATH = ROOT / "scripts" / "problem_solving_evidence_bundle.py"
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


def _persist_bundle_record(
    run_dir: Path,
    payload: dict[str, Any],
    record: dict[str, Any] | None,
) -> None:
    if record is None:
        return
    if isinstance(payload.get("run"), dict):
        payload["run"]["evidence_bundle"] = record
    route_path = run_dir / "route.json"
    route_record = json.loads(route_path.read_text(encoding="utf-8"))
    route_record["evidence_bundle"] = record
    if isinstance(route_record.get("run"), dict):
        route_record["run"]["evidence_bundle"] = record
    OS.write_json(route_path, route_record)


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
    run_dir, payload = CONTRACT_RUNTIME.run_request(
        request,
        context_path=context_path,
        output_root=output_root,
        engine=engine,
        model_policy=model_policy,
        model_policy_path=model_policy_path,
        run_id=run_id,
    )
    QUALITY_FIXES.set_workspace_root(EVIDENCE, engine)
    record = EVIDENCE.attach_evidence_bundle(run_dir, payload)
    _persist_bundle_record(run_dir, payload, record)
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

    print((run_dir / "result.md").read_text(encoding="utf-8").rstrip())
    if "evidence_bundle" in payload:
        print(f"\n근거 검토: {run_dir / payload['evidence_bundle']['review_markdown']}")
    print(f"\n실행 기록: {run_dir}")
    return 2 if payload["execution"]["status"] == "blocked_by_capability" else 0


if __name__ == "__main__":
    raise SystemExit(main())
