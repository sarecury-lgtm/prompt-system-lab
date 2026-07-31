#!/usr/bin/env python3
"""Serve PSOS prompt comparison without invoking Codex for integrated design."""

from __future__ import annotations

import argparse
import json
import re
import sys
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
COMPARE_SCRIPT_NAME = "compare-no-codex.js"
INTEGRATED_FIELDS = {"goal_ledger", "prompt_build_brief", "final_prompt"}
MIN_FINAL_PROMPT_LENGTH = 100


def build_integrated_design_prompt(request: str) -> str:
    """Build one external-AI instruction that also performs the final edit."""

    return f"""당신은 Personal Problem-Solving OS의 통합 프롬프트 설계기이자 최종 편집기다.

사용자의 요청을 한 번만 분석해 다음 세 논리 단계를 내부에서 순서대로 수행한다.

1. 재사용 가능한 프롬프트 제작에 필요한 Goal Ledger를 작성한다.
2. 그 Goal Ledger를 기준으로 Prompt Build Brief를 작성한다.
3. 두 설계 결과를 바탕으로 실제 실행에 바로 쓸 최종 프롬프트를 작성한다.

설명이나 마크다운 코드블록 없이 아래 구조의 JSON 객체 하나만 출력한다.

[Goal Ledger 규칙]
1. 사용자가 궁극적으로 얻으려는 결과를 parent_goal에 쓴다.
2. current_goal_hypothesis는 최종 프롬프트가 다른 AI에게 실제로 수행시킬 작업으로 쓴다. “프롬프트를 만든다”를 작업 목표로 남기지 않는다.
3. fixed_constraints에는 사용자가 명시했거나 결과를 실질적으로 바꾸는 조건만 둔다.
4. 이 요청은 프롬프트 제작 전용이므로 selected_route는 반드시 PROMPT, secondary_route는 null로 둔다.
5. completion_condition은 사용자가 최종 프롬프트를 실행해 원하는 결과를 얻었는지 판별할 수 있게 쓴다.
6. important_uncertainties는 결과를 실제로 바꿀 수 있는 것만 최대 3개로 둔다.

[Prompt Build Brief 규칙]
1. goal은 Goal Ledger의 목적을 실제 수행 작업으로 구체화한다.
2. core_procedure는 범용 문구가 아니라 해당 도메인에서 판단과 결과를 좌우하는 구체적인 처리 순서로 작성한다.
3. core_procedure는 서로 다른 판단 단계를 합치지 말고 필요한 만큼 작성하되 12개를 넘기지 않는다.
4. supporting_inputs에는 절차 수행에 필요한 자료, 입력 형태, 분석 요소, 도구만 둔다.
5. fixed_constraints는 Goal Ledger의 fixed_constraints를 문구와 순서까지 정확히 복사한다.
6. output_contract의 첫 항목은 Goal Ledger의 completion_condition과 정확히 같아야 한다.
7. 나머지 output_contract에는 사용자가 실제로 비교·판단·행동하는 데 필요한 산출물만 둔다.
8. defaults_and_exceptions에는 누락 정보 처리처럼 결과가 달라지는 기본값만 둔다.
9. exclusions에는 목표 밖의 작업만 둔다.
10. 같은 의미를 여러 필드에 반복하지 않는다.
11. core_procedure를 “요청 파악 → 작업 수행 → 결과 제시” 같은 범용 절차로 끝내지 않는다.

[최종 프롬프트 편집 규칙]
1. final_prompt에는 다른 AI에 복사해 바로 실행할 프롬프트 본문만 쓴다.
2. Goal Ledger와 Prompt Build Brief는 내부 설계 자료로만 사용하고, 그 이름·필드·라우팅·설계 계약·PSOS 생성 과정은 final_prompt에 노출하지 않는다.
3. Brief의 필드를 순서대로 기계적으로 펼치지 말고 역할, 입력, 핵심 절차, 예외·제한, 출력 형식처럼 실제 실행에 필요한 구조로 다시 편집한다.
4. 같은 의미의 규칙은 합치고, 범용 운영 원칙은 도메인 작업의 판단이나 결과를 실제로 바꿀 때만 남긴다.
5. core_procedure의 도메인 판단 단계, fixed_constraints, completion_condition과 필요한 output_contract는 빠뜨리지 않는다.
6. 최종 프롬프트가 다시 “프롬프트를 만들어라”고 요구하지 않게 하고 사용자가 원한 실제 작업을 직접 수행하게 한다.
7. 길이를 늘리는 것보다 실행의 명확성, 도메인 집중도, 중복 제거와 출력 일관성을 우선한다.
8. final_prompt는 마크다운 제목과 목록을 사용할 수 있지만 JSON 안의 하나의 문자열 값으로 반환한다.

[출력 JSON 구조]
{{
  "goal_ledger": {{
    "parent_goal": "...",
    "current_goal_hypothesis": "...",
    "fixed_constraints": [],
    "current_position": "...",
    "selected_route": "PROMPT",
    "secondary_route": null,
    "route_reason": "...",
    "current_step": "...",
    "why_this_step_matters": "...",
    "completion_condition": "...",
    "important_uncertainties": []
  }},
  "prompt_build_brief": {{
    "version": 1,
    "goal": "...",
    "core_procedure": [],
    "supporting_inputs": [],
    "fixed_constraints": [],
    "output_contract": [],
    "defaults_and_exceptions": [],
    "exclusions": [],
    "upstream_context": []
  }},
  "final_prompt": "다른 AI에 그대로 복사해 실행할 최종 프롬프트 본문"
}}

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


def parse_integrated_design(value: Any) -> dict[str, Any]:
    """Accept a JSON object or pasted JSON text, including fenced output."""

    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ChatGPT가 반환한 통합 JSON을 붙여 넣어 주세요.")

    text = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"통합 JSON을 읽을 수 없습니다: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("통합 설계 결과는 JSON 객체여야 합니다.")
    return decoded


def validate_integrated_design(
    value: Any,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if not isinstance(value, dict) or set(value) != INTEGRATED_FIELDS:
        raise ValueError(
            "통합 결과에는 goal_ledger, prompt_build_brief, final_prompt가 정확히 있어야 합니다."
        )

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

    final_prompt = _validate_string(value["final_prompt"], "final_prompt")
    if len(final_prompt) < MIN_FINAL_PROMPT_LENGTH:
        raise ValueError(
            f"final_prompt가 너무 짧습니다. 실제 실행용 프롬프트를 {MIN_FINAL_PROMPT_LENGTH}자 이상 작성해야 합니다."
        )
    return ledger, brief, final_prompt


def design_prompt_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one pasted AI result and extract its AI-edited final prompt."""

    request = base_web._required_text(payload, "request", "요청")
    raw_design = parse_integrated_design(payload.get("integrated_design"))
    ledger, brief, final_prompt = validate_integrated_design(raw_design)

    return {
        "run_id": None,
        "route": "PROMPT · AI 왕복 1회 · CODEX 0회",
        "execution_status": "completed",
        "result_markdown": final_prompt,
        "source_request": request,
        "goal_ledger": ledger,
        "prompt_build_brief": brief,
        "model_call_count": 0,
        "codex_call_count": 0,
        "external_ai_round_trip_count": 1,
        "artifacts": [
            {
                "path": "schemas/problem-solving-integrated-prompt-design.schema.json",
                "action": "validated",
            },
            {
                "path": "final_prompt",
                "action": "extracted_from_user_supplied_ai_result",
            },
        ],
        "evidence": [
            {
                "source": "user_supplied_integrated_design",
                "finding": "사용자가 한 번의 외부 AI 왕복으로 받은 Goal Ledger, Prompt Build Brief와 AI가 최종 편집한 final_prompt를 검증했습니다. 서버는 Codex나 다른 모델을 호출하거나 최종 문장을 다시 조립하지 않았습니다.",
            }
        ],
        "limitations": [
            "한 번의 AI 응답에서 설계와 최종 편집을 함께 수행하므로 수동 단계별 결과와 품질 차이가 날 수 있습니다."
        ],
        "workspace_receipt": None,
        "workspace_rollback": None,
    }


class ComparisonRequestHandler(base_web.PsosRequestHandler):
    server_version = "PSOSCompareWeb/3"

    def _send_compare_index(self) -> None:
        try:
            html = (self.app.web_dir / "index.html").read_text(encoding="utf-8")
            marker = '<script src="/renderer.js" defer></script>'
            injected = marker + f'\n    <script src="/{COMPARE_SCRIPT_NAME}" defer></script>'
            if marker not in html:
                raise OSError("renderer script marker is missing")
            content = html.replace(marker, injected, 1).encode("utf-8")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'",
        )
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_compare_index()
            return
        if path == f"/{COMPARE_SCRIPT_NAME}":
            self.send_static(COMPARE_SCRIPT_NAME, "text/javascript; charset=utf-8")
            return
        super().do_GET()

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
    print("통합 비교 모드: ChatGPT가 최종 편집 · Codex 호출 없음")
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
