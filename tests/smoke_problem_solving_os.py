"""Deterministic route and model-orchestration smoke for the MVP."""

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


def route_payload(route, primary, secondary):
    reason = "fixture route"
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
    }


def execution_payload(route):
    evidence = []
    if route == "RESEARCH":
        evidence = [
            {
                "source": "https://example.test/official",
                "finding": "최신 사실 확인",
                "kind": "web",
            }
        ]
    elif route == "REUSE":
        evidence = [
            {
                "source": "template.md",
                "finding": "기존 자산 확인",
                "kind": "local",
            }
        ]
    return {
        "execution": {
            "status": "completed",
            "summary": f"{route} smoke result",
            "result_markdown": f"{route} 경로별 실행 결과",
            "capabilities_used": ["fixture"],
            "needed_capability": None,
            "handoff": None,
            "artifacts": [],
            "evidence": evidence,
            "limitations": [],
        }
    }


class SequencedEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def capabilities(self):
        return OS.EngineCapabilities(True, True, True, False, "smoke")

    def execute(self, prompt, run_dir, invocation):
        self.calls.append(invocation)
        return json.loads(json.dumps(self.responses.pop(0)))

    def trace(self):
        return [
            {
                "name": item.name,
                "model": item.profile.model,
                "reasoning_effort": item.profile.reasoning_effort,
            }
            for item in self.calls
        ]


def main() -> int:
    policy = OS.load_model_policy()
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        for run_id, request, route, primary, secondary in CASES:
            route_sequence = [route] if route != "HYBRID" else [primary, secondary]
            responses = [
                route_payload(route, primary, secondary),
                *(execution_payload(item) for item in route_sequence),
            ]
            engine = SequencedEngine(responses)
            run_dir, payload = OS.run_request(
                request,
                output_root=output,
                engine=engine,
                model_policy=policy,
                run_id=run_id,
            )
            assert payload["route"]["selected_route"] == route
            assert all(
                (run_dir / name).is_file()
                for name in ("request.txt", "goal_ledger.json", "route.json", "result.md")
            )
            if route == "PROMPT" or secondary == "PROMPT":
                assert "prompt_compiler" in payload
            models = " -> ".join(item.profile.model for item in engine.calls)
            print(f"PASS {run_id}: {route} | {models}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
