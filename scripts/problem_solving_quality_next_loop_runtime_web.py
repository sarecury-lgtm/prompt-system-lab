#!/usr/bin/env python3
"""Launch the quality next-loop UI with durable candidate update merging enabled."""

from __future__ import annotations

import problem_solving_next_loop_runtime as candidate_runtime
import problem_solving_quality_next_loop_web as web


web.next_loop = candidate_runtime


if __name__ == "__main__":
    raise SystemExit(web.main())
