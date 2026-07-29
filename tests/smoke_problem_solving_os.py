"""Deterministic flow smoke for all supported MVP route shapes."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "problem_solving_os", ROOT / "scripts" / "problem_solving_os.py"
)
OS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = OS
SPEC.loader.exec_module(OS)


CASES = [
    ("direct", "캐시가 무엇인지 설명해 줘.", "DIRECT", None, None),
    ("research", "오늘 판매 중인 노트북 가격을 조사해 줘.", "RESEARCH", None, None),
    ("reuse", "기존 회의록 템플릿을 먼저 찾아 적용해 줘.", "REUSE", None, None),
    ("prompt", "다른 AI에서 반복 사용할 검수 지침을 만들어 줘.", "PROMPT", None, None),
    ("code", "여러 CSV 파일을 반복 합치는 자동화를 만들어 줘.", "CODE", None, None),
    (
        "hybrid",
        "최신 정책을 조사한 뒤 다른 AI가 반복 사용할 프롬프트를 만들어 줘.",
        "HYBRID",
        "RESEARCH",
        "PROMPT",
    ),
]


def result(route, primary, secondary):
    reason = "fixture route"
    evidence = []
    if route in {"RESEARCH", "REUSE"} or primary == "RESEARCH":
        evidence = [
            {
                "source": "smoke fixture",
                "finding": "flow evidence",
                "kind": "provided_context",
            }
        ]
    return {
        "goal_ledger": {
            "parent_goal": "사용 가능한 결과",
            "current_goal_hypothesis": "요청을 그대로 수행",
            "fixed_constraints": ["요청 범위 보존"],
            "current_position": "smoke",
            "selected_route": route,
            "secondary_route": secondary,
            "route_reason": reason,
            "current_step": "결과 생성",
            "why_this_step_matters": "실행 흐름 연결 확인",
            "completion_condition": "산출물 저장",
            "important_uncertainties": [],
        },
        "route": {
            "selected_route": route,
            "primary_route": primary,
            "secondary_route": secondary,
            "route_reason": reason,
        },
        "execution": {
            "status": "completed",
            "summary": "smoke result",
            "result_markdown": "경로별 실행 결과",
            "capabilities_used": ["fixture"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": evidence,
            "limitations": [],
        },
    }


class SequencedEngine:
    def __init__(self, payload):
        self.payload = payload

    def capabilities(self):
        return OS.EngineCapabilities(True, True, True, False, "smoke")

    def execute(self, prompt, run_dir):
        return json.loads(json.dumps(self.payload))


def main() -> int:
    prompt_runtime = OS.load_prompt_runtime()
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        for run_id, request, route, primary, secondary in CASES:
            engine = SequencedEngine(result(route, primary, secondary))
            run_dir, payload = OS.run_request(
                request,
                output_root=output,
                engine=engine,
                run_id=run_id,
            )
            actual = payload["route"]["selected_route"]
            assert actual == route, (run_id, actual, route)
            assert all(
                (run_dir / name).is_file()
                for name in ("request.txt", "goal_ledger.json", "route.json", "result.md")
            )
            if route == "PROMPT" or secondary == "PROMPT":
                assert "prompt_compiler" in payload
                assert prompt_runtime is not None
            print(f"PASS {run_id}: {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
