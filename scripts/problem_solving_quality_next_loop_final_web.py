#!/usr/bin/env python3
"""Launch PSOS with finalizing automatic Job Packets and optional advanced candidate loops."""

from __future__ import annotations

import problem_solving_quality_next_loop_job_packet as job_packet_support
import problem_solving_quality_next_loop_smart_web as smart


def build_static_addons() -> dict[str, list[str]]:
    addons = smart.build_static_addons()
    renderer_addons = addons.setdefault("renderer.js", [])
    insert_at = (
        renderer_addons.index("chatgpt-manual-fallback-v5.js")
        if "chatgpt-manual-fallback-v5.js" in renderer_addons
        else len(renderer_addons)
    )
    renderer_addons.insert(insert_at, "next-loop-job-packet.js")
    return addons


def main() -> int:
    smart.web.next_loop = smart.candidate_runtime
    job_packet_support.install(smart.web)
    smart.attachment_support.install(smart.web)
    smart.blind_handoff_support.install(smart.web)
    smart.manual_patch_support.install(smart.web)
    smart.manual_controller_support.install(smart.web)
    smart.web.STATIC_ADDONS = build_static_addons()
    return smart.web.main()


if __name__ == "__main__":
    raise SystemExit(main())
