#!/usr/bin/env python3
"""Launch the candidate-aware PSOS UI with automatic and manual ChatGPT paths."""

from __future__ import annotations

import problem_solving_manual_controller_web as manual_controller_support
import problem_solving_manual_patch_web as manual_patch_support
import problem_solving_next_loop_replacement_runtime as candidate_runtime
import problem_solving_quality_next_loop_web as web
import problem_solving_web_attachments as attachment_support


def build_static_addons() -> dict[str, list[str]]:
    addons = {name: list(values) for name, values in web.STATIC_ADDONS.items()}

    app_addons = addons.setdefault("app.js", [])
    insert_at = app_addons.index("next-loop.js") if "next-loop.js" in app_addons else len(app_addons)
    app_addons.insert(insert_at, "next-loop-attachments.js")
    app_addons.append("next-loop-details.js")

    style_addons = addons.setdefault("styles.css", [])
    style_addons.append("next-loop-details.css")
    style_addons.append("next-loop-attachments.css")

    renderer_addons = addons.setdefault("renderer.js", [])
    renderer_addons.append("next-loop-workflow.js")
    renderer_addons.append("psos-manual-protocol.js")
    renderer_addons.append("psos-manual-route-policy.js")
    renderer_addons.append("chatgpt-manual-fallback-v5.js")
    renderer_addons.append("chatgpt-manual-focus-v1.js")
    renderer_addons.append("psos-manual-controller-v1.js")
    renderer_addons.append("psos-manual-request-switch-v1.js")
    renderer_addons.append("psos-manual-verification-v1.js")
    renderer_addons.append("psos-manual-refinement-v1.js")
    renderer_addons.append("psos-result-refinement-v1.js")
    renderer_addons.append("chatgpt-manual-patch-v1.js")

    style_addons.append("next-loop-workflow.css")
    style_addons.append("chatgpt-manual-fallback-v5.css")
    style_addons.append("chatgpt-manual-focus-v1.css")
    style_addons.append("psos-manual-controller-v1.css")
    style_addons.append("psos-manual-request-switch-v1.css")
    style_addons.append("psos-manual-verification-v1.css")
    style_addons.append("psos-manual-refinement-v1.css")
    style_addons.append("chatgpt-manual-patch-v1.css")
    return addons


def main() -> int:
    web.next_loop = candidate_runtime
    attachment_support.install(web)
    manual_patch_support.install(web)
    manual_controller_support.install(web)
    web.STATIC_ADDONS = build_static_addons()
    return web.main()


if __name__ == "__main__":
    raise SystemExit(main())
