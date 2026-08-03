#!/usr/bin/env python3
"""Launch the candidate-aware PSOS UI with automatic workflow guidance."""

from __future__ import annotations

import problem_solving_quality_next_loop_runtime_web as runtime_web


web = runtime_web.web
web.STATIC_ADDONS.setdefault("renderer.js", []).append("next-loop-workflow.js")
web.STATIC_ADDONS.setdefault("styles.css", []).append("next-loop-workflow.css")


if __name__ == "__main__":
    raise SystemExit(web.main())
