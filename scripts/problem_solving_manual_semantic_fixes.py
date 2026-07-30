#!/usr/bin/env python3
"""Keep manual-bridge audit output separate from the user-facing final output."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def apply(manual_module: Any) -> Any:
    """Patch the loaded manual bridge once without duplicating its orchestration."""

    if getattr(manual_module, "_manual_output_fix_applied", False):
        return manual_module

    original_public_state = manual_module.public_state
    original_finalize = manual_module.ManualBridge.finalize

    def public_state(state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        payload = original_public_state(state, run_dir)
        output_name = state.get("output_path") or "output.md"
        output_path = run_dir / output_name
        payload["output_markdown"] = (
            output_path.read_text(encoding="utf-8")
            if output_path.is_file()
            else ""
        )
        payload["session_kind"] = state.get("session_kind", "psos")
        route_payload = state.get("route_payload")
        route = (
            route_payload.get("route")
            if isinstance(route_payload, dict)
            and isinstance(route_payload.get("route"), dict)
            else {}
        )
        payload["selected_route"] = (
            state.get("selected_route") or route.get("selected_route")
        )
        return payload

    def finalize(
        self: Any,
        run_dir: Path,
        state: dict[str, Any],
        execution: dict[str, Any],
    ) -> None:
        original_finalize(self, run_dir, state, execution)
        output_path = run_dir / "output.md"
        output_path.write_text(
            str(execution.get("result_markdown", "")).strip() + "\n",
            encoding="utf-8",
        )
        state["output_path"] = output_path.name
        self.save(run_dir, state)

    manual_module.public_state = public_state
    manual_module.ManualBridge.finalize = finalize
    manual_module._manual_output_fix_applied = True
    return manual_module
