#!/usr/bin/env python3
"""Launch the candidate-aware PSOS UI with automatic and manual ChatGPT paths."""

from __future__ import annotations

import problem_solving_next_loop_runtime as candidate_runtime
import problem_solving_quality_next_loop_web as web


def build_static_addons() -> dict[str, list[str]]:
    addons = {name: list(values) for name, values in web.STATIC_ADDONS.items()}
    addons.setdefault("app.js", []).append("next-loop-details.js")
    addons.setdefault("styles.css", []).append("next-loop-details.css")
    addons.setdefault("renderer.js", []).append("next-loop-workflow.js")
    addons.setdefault("renderer.js", []).append("chatgpt-manual-fallback.js")
    addons.setdefault("styles.css", []).append("next-loop-workflow.css")
    addons.setdefault("styles.css", []).append("chatgpt-manual-fallback.css")
    return addons


def main() -> int:
    web.next_loop = candidate_runtime
    web.STATIC_ADDONS = build_static_addons()
    return web.main()


if __name__ == "__main__":
    raise SystemExit(main())
