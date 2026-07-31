#!/usr/bin/env python3
"""Add Prompt Build Brief stages to the manual ChatGPT bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import problem_solving_manual as manual
import problem_solving_manual_deep as deep_manual
import problem_solving_prompt_build_brief as prompt_brief


class ManualPromptBuildBriefError(manual.ManualBridgeError):
    """Raised when a manual PROMPT brief handoff is invalid."""


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _relative(run_dir: Path, path: Path) -> str:
    return path.relative_to(run_dir).as_posix()


class ManualBridge(deep_manual.ManualBridge):
    """Manual bridge that normalizes PROMPT inputs before final generation."""

    def _brief_root(self, run_dir: Path, label: str) -> Path:
        root = run_dir / "prompt_build_brief" / label
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _prepare_prompt_brief(
        self,
        run_dir: Path,
        state: dict[str, Any],
        label: str,
        primary: dict[str, Any] | None,
    ) -> None:
        original_executor_input = self.execution_prompt(
            run_dir,
            state,
            "PROMPT",
            primary,
        )
        compiler = state.get("prompt_compiler")
        baseline = compiler.get("compiled") if isinstance(compiler, dict) else None
        if not isinstance(baseline, dict):
            raise ManualPromptBuildBriefError(
                "PROMPT Compiler baseline을 준비하지 못했습니다."
            )
        ledger = state["route_payload"]["goal_ledger"]
        compiler_prompt = prompt_brief.build_prompt_build_brief_prompt(
            state["request"],
            ledger,
            baseline,
            primary,
        )
        root = self._brief_root(run_dir, label)
        original_path = root / "original_executor_input.md"
        original_path.write_text(
            original_executor_input.rstrip() + "\n",
            encoding="utf-8",
        )
        baseline_path = root / "compiler_baseline.json"
        _write_json(baseline_path, baseline)
        primary_path: Path | None = None
        if primary is not None:
            primary_path = root / "primary_execution.json"
            _write_json(primary_path, primary)

        state.setdefault("prompt_build_brief", {"version": 1, "entries": {}})
        state["prompt_build_brief"]["entries"][label] = {
            "stage": label,
            "status": "awaiting_brief",
            "original_executor_input_path": _relative(run_dir, original_path),
            "compiler_baseline_path": _relative(run_dir, baseline_path),
            "primary_execution_path": (
                _relative(run_dir, primary_path) if primary_path else None
            ),
            "brief_path": None,
            "brief_markdown_path": None,
            "final_executor_prompt_path": None,
        }
        self.set_prompt(
            run_dir,
            state,
            f"{label}_prompt_brief",
            "PROMPT",
            label,
            manual.with_schema(
                compiler_prompt,
                prompt_brief.BRIEF_SCHEMA_PATH,
                f"prompt-brief:{label}",
            ),
            prompt_brief.BRIEF_SCHEMA_PATH,
        )

    def prepare_executor(
        self,
        run_dir: Path,
        state: dict[str, Any],
        route: str,
        label: str,
        primary: dict[str, Any] | None = None,
    ) -> None:
        if route != "PROMPT":
            super().prepare_executor(run_dir, state, route, label, primary)
            return
        self._prepare_prompt_brief(run_dir, state, label, primary)

    def _prepare_final_prompt_executor(
        self,
        run_dir: Path,
        state: dict[str, Any],
        label: str,
        brief: dict[str, Any],
    ) -> None:
        profile = manual.profile(state["search_enabled"])
        capabilities = manual.capabilities(state["search_enabled"])
        invocation = manual.problem_os.InvocationSpec(
            name=f"manual-{label}-prompt-final",
            phase="executor",
            route="PROMPT",
            profile=profile,
            schema_path=manual.problem_os.EXECUTION_SCHEMA_PATH,
        )
        base_prompt = prompt_brief.build_prompt_executor_from_brief(
            brief,
            invocation,
            capabilities,
            "",
        )
        wrapped = manual.with_schema(
            base_prompt,
            manual.problem_os.EXECUTION_SCHEMA_PATH,
            f"executor:{label}:PROMPT:brief",
        )
        self.set_prompt(
            run_dir,
            state,
            f"{label}_prompt_final",
            "PROMPT",
            label,
            wrapped,
            manual.problem_os.EXECUTION_SCHEMA_PATH,
        )
        stage = state["stage"]
        final_path = run_dir / stage["prompt_path"]
        entry = state["prompt_build_brief"]["entries"][label]
        entry["status"] = "brief_compiled"
        entry["final_executor_prompt_path"] = _relative(run_dir, final_path)

    def _accept_prompt_brief(
        self,
        run_dir: Path,
        state: dict[str, Any],
        response: str,
    ) -> dict[str, Any]:
        stage = state["stage"]
        label = stage["stage_label"]
        value, normalized = manual.parse_response(response)
        ledger = state["route_payload"]["goal_ledger"]
        try:
            brief = prompt_brief.validate_prompt_build_brief(value, ledger)
        except prompt_brief.PromptBuildBriefError as exc:
            raise ManualPromptBuildBriefError(str(exc)) from exc

        self.record(run_dir, state, response, normalized)
        root = self._brief_root(run_dir, label)
        brief_path = root / "brief.json"
        markdown_path = root / "brief.md"
        _write_json(brief_path, brief)
        markdown_path.write_text(
            prompt_brief.render_prompt_build_brief(brief),
            encoding="utf-8",
        )
        entry = state["prompt_build_brief"]["entries"][label]
        entry["brief_path"] = _relative(run_dir, brief_path)
        entry["brief_markdown_path"] = _relative(run_dir, markdown_path)
        self._prepare_final_prompt_executor(run_dir, state, label, brief)
        state["error"] = None
        self.save(run_dir, state)
        return manual.public_state(state, run_dir)

    def submit(self, run_id: str, response: str) -> dict[str, Any]:
        with self.lock:
            run_dir = self.run_dir(run_id)
            if not run_dir.is_dir():
                raise manual.ManualBridgeError("해당 run을 찾을 수 없습니다.")
            state = manual.read_state(run_dir)
            stage = state.get("stage") or {}
            if str(stage.get("phase", "")).endswith("_prompt_brief"):
                try:
                    return self._accept_prompt_brief(run_dir, state, response)
                except (manual.ManualBridgeError, prompt_brief.PromptBuildBriefError) as exc:
                    state["error"] = str(exc)
                    self.save(run_dir, state)
                    raise manual.ManualBridgeError(str(exc)) from exc
        return super().submit(run_id, response)

    def finalize(
        self,
        run_dir: Path,
        state: dict[str, Any],
        execution: dict[str, Any],
    ) -> None:
        record = state.get("prompt_build_brief")
        if isinstance(record, dict):
            entries = record.get("entries")
            if isinstance(entries, dict):
                for entry in entries.values():
                    if isinstance(entry, dict) and entry.get("status") == "brief_compiled":
                        entry["status"] = "completed"
        super().finalize(run_dir, state, execution)
        if not isinstance(record, dict):
            return
        route_path = run_dir / "route.json"
        route_record = json.loads(route_path.read_text(encoding="utf-8"))
        route_record["prompt_build_brief"] = record
        _write_json(route_path, route_record)
        _write_json(run_dir / "prompt_build_brief" / "record.json", record)

    def model_plan(
        self,
        state: dict[str, Any],
        routes: list[str],
    ) -> list[dict[str, Any]]:
        plan = super().model_plan(state, routes)
        expanded: list[dict[str, Any]] = []
        for item in plan:
            if item.get("route") != "PROMPT":
                expanded.append(item)
                continue
            brief_stage = {
                **item,
                "stage": f"{item['stage']}_prompt_brief",
                "web_search": False,
                "transport": "manual_chatgpt_bridge",
            }
            final_stage = {
                **item,
                "stage": f"{item['stage']}_prompt_final",
                "transport": "manual_chatgpt_bridge",
            }
            expanded.extend([brief_stage, final_stage])
        return expanded
