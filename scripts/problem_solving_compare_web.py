#!/usr/bin/env python3
"""Serve PSOS prompt comparison with one-call AI design and manual four-stage flow."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as problem_os
import problem_solving_prompt_renderer as prompt_renderer
import problem_solving_web as base_web


ROOT = SCRIPT_DIR.parent
DESIGN_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-integrated-prompt-design.schema.json"


def build_integrated_design_prompt(request: str) -> str:
    """Ask one model call to produce both the ledger and the prompt brief."""

    return f"""당신은 Personal Problem-Solving OS의 통합 프롬프트 설계기다.

사용자의 요청을 한 번만 분석해 다음 두 논리 단계를 함께 수행한다.

1. 재사용 가능한 프롬프트 제작에 필요한 Goal Ledger를 작성한다.
2. 그 Goal Ledger를 기준으로 Prompt Build Brief를 작성한다.

이 단계에서는 최종 프롬프트 본문을 작성하지 않는다. JSON 이외의 설명도 출력하지 않는다.

[Goal Ledger 규칙]
1. 사용자가 궁극적으로 얻으려는 결과를 parent_goal에 쓴다.
2. current_goal_hypothesis는 최종 프롬프트가 다른 AI에게 실제로 수행시킬 작업으로 쓴다. “프롬프트를 만든다”를 작업 목표로 남기지 않는다.
3. fixed_constraints에는 사용자가 명시했거나 결과를 실질적으로 바꾸는 조건만 둔다.
4. 이 화면은 프롬프트 제작 전용이므로 selected_route는 반드시 PROMPT, secondary_route는 null로 둔다.
5. completion_condition은 사용자가 최종 프롬프트를 바로 실행해 원하는 결과를 얻었는지 판별할 수 있게 쓴다.
6. important_uncertainties는 결과를 실제로 바꿀 수 있는 것만 최대 3개로 둔다.

[Prompt Build Brief 규칙]
1. goal은 Goal Ledger의 목적을 실제 수행 작업으로 구체화한다.
2. core_procedure는 범용 문구가 아니라 해당 도메인에서 판단과 결과를 좌우하는 구체적인 처리 순서로 작성한다.
3. supporting_inputs에는 절차 수행에 필요한 자료, 입력 형태, 분석 요소, 도구만 둔다.
4. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
5. output_contract의 첫 항목은 Goal Ledger의 completion_condition과 정확히 같아야 한다.
6. 나머지 output_contract에는 사용자가 실제로 비교·판단·행동하는 데 필요한 산출물만 둔다.
7. defaults_and_exceptions에는 누락 정보 처리처럼 결과가 달라지는 기본값만 둔다.
8. exclusions에는 목표 밖의 작업만 둔다.
9. 같은 의미를 여러 필드에 반복하지 않는다.
10. core_procedure를 “요청 파악 → 작업 수행 → 결과 제시” 같은 범용 절차로 끝내지 않는다.

[사용자 요청]
{request.strip()}
"""


def _validate_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}이 비어 있습니다.")
    return value.strip()


def _validate_string_list(value: Any, label: str, maximum: int | None = None) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label}은 문자열 배열이어야 합니다.")
    result: list[str] = []
    for item in value:
        cleaned = _validate_string(item, label)
        if cleaned in result:
            raise ValueError(f"{label}에 중복 값이 있습니다.")
        result.append(cleaned)
    if maximum is not None and len(result) > maximum:
        raise ValueError(f"{label}은 {maximum}개 이하여야 합니다.")
    return result


def validate_integrated_design(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"goal_ledger", "prompt_build_brief"}:
        raise ValueError("통합 설계 결과의 최상위 필드가 올바르지 않습니다.")

    raw_ledger = value["goal_ledger"]
    if not isinstance(raw_ledger, dict) or set(raw_ledger) != problem_os.LEDGER_FIELDS:
        raise ValueError("Goal Ledger 필드가 올바르지 않습니다.")
    ledger = dict(raw_ledger)
    for field in (
        "parent_goal",
        "current_goal_hypothesis",
        "current_position",
        "route_reason",
        "current_step",
        "why_this_step_matters",
        "completion_condition",
    ):
        ledger[field] = _validate_string(ledger[field], f"Goal Ledger.{field}")
    ledger["fixed_constraints"] = _validate_string_list(
        ledger["fixed_constraints"],
        "Goal Ledger.fixed_constraints",
    )
    ledger["important_uncertainties"] = _validate_string_list(
        ledger["important_uncertainties"],
        "Goal Ledger.important_uncertainties",
        maximum=3,
    )
    if ledger["selected_route"] != "PROMPT" or ledger["secondary_route"] is not None:
        raise ValueError("통합 설계의 경로는 PROMPT 단일 경로여야 합니다.")

    raw_brief = value["prompt_build_brief"]
    try:
        brief = prompt_renderer.BRIEF.validate_prompt_build_brief(raw_brief, ledger)
    except prompt_renderer.BRIEF.PromptBuildBriefError as exc:
        raise ValueError(str(exc)) from exc
    if not brief["core_procedure"]:
        raise ValueError("Prompt Build Brief의 핵심 작업 절차가 비어 있습니다.")
    return ledger, brief


def design_prompt_request(
    payload: dict[str, Any],
    *,
    engine: Any | None = None,
) -> dict[str, Any]:
    """Use exactly one Codex call, then render the final prompt locally."""

    request = base_web._required_text(payload, "request", "요청")
    model_policy = problem_os.load_model_policy()
    profile = model_policy["routes"]["PROMPT"]["primary"]
    invocation = problem_os.InvocationSpec(
        name="integrated-prompt-design",
        phase="prompt-design",
        route="PROMPT",
        profile=profile,
        schema_path=DESIGN_SCHEMA_PATH,
    )
    active_engine = engine or problem_os.CodexEngine(
        ROOT,
        allow_workspace_write=False,
        enable_search=False,
    )
    with tempfile.TemporaryDirectory(prefix="psos-integrated-design-") as temp_dir:
        raw = active_engine.execute(
            build_integrated_design_prompt(request),
            Path(temp_dir),
            invocation,
        )
    ledger, brief = validate_integrated_design(raw)
    try:
        rendered = prompt_renderer.render_prompt(
            brief,
            ledger,
            prompt_renderer.load_policy(),
        )
    except (
        prompt_renderer.PromptRendererError,
        prompt_renderer.BRIEF.PromptBuildBriefError,
    ) as exc:
        raise ValueError(str(exc)) from exc

    trace = active_engine.trace() if callable(getattr(active_engine, "trace", None)) else []
    model = trace[-1].get("model") if trace else profile.model
    return {
        "run_id": None,
        "route": "PROMPT · AI 1회",
        "execution_status": "completed",
        "result_markdown": rendered,
        "goal_ledger": ledger,
        "prompt_build_brief": brief,
        "model_call_count": 1,
        "artifacts": [
            {
                "path": "configs/psos-goal-aware-assistant-policy.md",
                "action": "read",
            },
            {
                "path": "scripts/problem_solving_prompt_renderer.py",
                "action": "used",
            },
        ],
        "evidence": [
            {
                "source": "integrated_prompt_design",
                "finding": f"{model}을 한 번 호출해 Goal Ledger와 Prompt Build Brief를 함께 만들고 로컬 렌더러로 조립했습니다.",
            }
        ],
        "limitations": [
            "한 번의 모델 호출에서 두 논리 단계를 함께 수행하므로 수동 단계별 검토와 결과가 달라질 수 있습니다."
        ],
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


class ComparisonRequestHandler(base_web.PsosRequestHandler):
    server_version = "PSOSCompareWeb/1"

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/design-prompt":
            try:
                self.send_json(design_prompt_request(self.read_json_body()))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc).strip() or exc.__class__.__name__},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        super().do_POST()


class ComparisonHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        jobs: base_web.JobManager,
        approvals: base_web.ApprovalManager | None = None,
        web_dir: Path = base_web.WEB_DIR,
    ) -> None:
        super().__init__(server_address, ComparisonRequestHandler)
        self.jobs = jobs
        self.approvals = approvals or base_web.ApprovalManager(jobs)
        self.web_dir = web_dir

    def server_close(self) -> None:
        self.jobs.shutdown()
        super().server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open-browser",
        choices=("default", "chrome"),
        help="서버 시작 후 선택한 브라우저로 화면을 엽니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        print("안전을 위해 로컬 호스트에만 바인딩할 수 있습니다.", file=sys.stderr)
        return 1
    jobs = base_web.JobManager()
    server = ComparisonHTTPServer((args.host, args.port), jobs=jobs)
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"
    print(f"PSOS 비교 화면: {url}")
    print("종료: Ctrl+C")
    if args.open_browser:
        threading.Timer(0.3, base_web.open_browser, args=(url, args.open_browser)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPSOS 비교 화면을 종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
