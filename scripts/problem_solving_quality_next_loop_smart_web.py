#!/usr/bin/env python3
"""Launch the candidate-aware PSOS UI with automatic and manual ChatGPT paths."""

from __future__ import annotations

import problem_solving_next_loop_replacement_runtime as candidate_runtime
import problem_solving_quality_next_loop_web as web
import problem_solving_web_attachments as attachment_support


def build_static_addons() -> dict[str, list[str]]:
    addons = {name: list(values) for name, values in web.STATIC_ADDONS.items()}

    app_addons = addons.setdefault("app.js", [])
    insert_at = app_addons.index("next-loop.js") if "next-loop.js" in app_addons else len(app_addons)
    app_addons.insert(insert_at, "next-loop-attachments.js")
    app_addons.append("next-loop-details.js")

    addons.setdefault("styles.css", []).append("next-loop-details.css")
    addons.setdefault("styles.css", []).append("next-loop-attachments.css")
    addons.setdefault("renderer.js", []).append("next-loop-workflow.js")
    addons.setdefault("renderer.js", []).append("chatgpt-manual-fallback-v4.js")
    addons.setdefault("styles.css", []).append("next-loop-workflow.css")
    addons.setdefault("styles.css", []).append("chatgpt-manual-fallback-v4.css")
    return addons


def main() -> int:
    web.next_loop = candidate_runtime
    attachment_support.install(web)
    web.STATIC_ADDONS = build_static_addons()
    return web.main()


if __name__ == "__main__":
    raise SystemExit(main())
