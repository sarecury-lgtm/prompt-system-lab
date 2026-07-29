#!/usr/bin/env python3
"""Run the Personal Problem-Solving OS with a Codex subscription-backed engine."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-output.schema.json"
PROMPT_RUNTIME_PATH = ROOT / "scripts" / "prompt_runtime.py"

ROUTES = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT", "HYBRID"}
EXECUTION_STATUSES = {"completed", "partial", "blocked_by_capability", "handoff"}
LEDGER_FIELDS = {
    "parent_goal",
    "current_goal_hypothesis",
    "fixed_constraints",
    "current_position",
    "selected_route",
    "secondary_route",
    "route_reason",
    "current_step",
    "why_this_step_matters",
    "completion_condition",
    "important_uncertainties",
}


class ProblemSolvingError(Exception):
    """A recoverable problem-solving runtime failure."""


@dataclass(frozen=True)
class EngineCapabilities:
    ai_reasoning: bool
    web_search: bool
    workspace_read: bool
    workspace_write: bool
    detail: str = ""


class ProblemSolvingEngine(Protocol):
    def capabilities(self) -> EngineCapabilities:
        """Return capabilities that are available for this run."""

    def execute(self, prompt: str, run_dir: Path) -> dict[str, Any]:
        """Return one schema-conforming AI decision and execution result."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def make_run_id(now: dt.datetime | None = None) -> str:
    stamp = (now or utc_now()).strftime("%Y%m%dT%H%M%S%fZ")
    return f"psos-{stamp}"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_context(path: Path | None) -> tuple[str, str | None]:
    if path is None:
        return "", None
    try:
        resolved = path.expanduser().resolve(strict=True)
        text = resolved.read_text(encoding="utf-8")
    except Exception as exc:
        raise ProblemSolvingError(f"문맥 파일을 읽을 수 없습니다: {path}: {exc}") from exc
    if len(text) > 200_000:
        raise ProblemSolvingError("문맥 파일은 UTF-8 텍스트 200,000자 이하여야 합니다.")
    return text, str(resolved)


def find_codex() -> str:
    configured = os.environ.get("CODEX_BIN")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise ProblemSolvingError(f"CODEX_BIN이 존재하지 않습니다: {configured}")
    names = ("codex.cmd", "codex.exe", "codex") if os.name == "nt" else ("codex",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise ProblemSolvingError("Codex CLI를 찾을 수 없습니다. PATH 또는 CODEX_BIN을 확인하세요.")


def subprocess_command(executable: str, arguments: list[str]) -> list[str]:
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command_line = subprocess.list2cmdline([executable, *arguments])
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]
    return [executable, *arguments]


class CodexEngine:
    """Codex CLI adapter. Authentication comes from the user's Codex subscription."""

    def __init__(
        self,
        workspace: Path,
        *,
        allow_workspace_write: bool = False,
        enable_search: bool = True,
        timeout_seconds: int = 600,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.allow_workspace_write = allow_workspace_write
        self.enable_search = enable_search
        self.timeout_seconds = timeout_seconds
        self._executable: str | None = None
        self._capabilities: EngineCapabilities | None = None

    def capabilities(self) -> EngineCapabilities:
        if self._capabilities is not None:
            return self._capabilities
        try:
            self._executable = find_codex()
            completed = subprocess.run(
                subprocess_command(self._executable, ["--help"]),
                cwd=self.workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
            if completed.returncode != 0:
                raise ProblemSolvingError(
                    f"Codex CLI capability 확인 실패(exit {completed.returncode})"
                )
            search_supported = "--search" in (completed.stdout or "")
            self._capabilities = EngineCapabilities(
                ai_reasoning=True,
                web_search=self.enable_search and search_supported,
                workspace_read=True,
                workspace_write=self.allow_workspace_write,
                detail=(
                    "Codex CLI available; "
                    f"web_search={'enabled' if self.enable_search and search_supported else 'disabled'}; "
                    f"workspace_write={'enabled' if self.allow_workspace_write else 'disabled'}"
                ),
            )
        except (OSError, subprocess.SubprocessError, ProblemSolvingError) as exc:
            self._capabilities = EngineCapabilities(
                ai_reasoning=False,
                web_search=False,
                workspace_read=False,
                workspace_write=False,
                detail=str(exc),
            )
        return self._capabilities

    def execute(self, prompt: str, run_dir: Path) -> dict[str, Any]:
        capabilities = self.capabilities()
        if not capabilities.ai_reasoning or self._executable is None:
            raise ProblemSolvingError(capabilities.detail or "Codex CLI를 실행할 수 없습니다.")
        request_path = run_dir / "engine-request.md"
        output_path = run_dir / "engine-output.json"
        log_path = run_dir / "engine.log"
        request_path.write_text(prompt, encoding="utf-8")

        arguments: list[str] = []
        if capabilities.web_search:
            arguments.append("--search")
        arguments.extend(
            [
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--sandbox",
                "workspace-write" if capabilities.workspace_write else "read-only",
                "--cd",
                str(self.workspace),
                "--output-schema",
                str(SCHEMA_PATH),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
                "-",
            ]
        )
        try:
            completed = subprocess.run(
                subprocess_command(self._executable, arguments),
                input=prompt,
                cwd=self.workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ProblemSolvingError(f"Codex CLI 실행 실패: {exc}") from exc
        log_path.write_text(completed.stdout or "", encoding="utf-8")
        if completed.returncode != 0:
            raise ProblemSolvingError(
                f"Codex CLI가 exit {completed.returncode}로 실패했습니다. 로그: {log_path}"
            )
        if not output_path.is_file():
            raise ProblemSolvingError("Codex CLI가 구조화된 결과 파일을 만들지 않았습니다.")
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProblemSolvingError(f"Codex CLI 결과 JSON을 읽을 수 없습니다: {exc}") from exc


def build_engine_prompt(
    request: str,
    context: str,
    context_path: str | None,
    capabilities: EngineCapabilities,
) -> str:
    capability_json = json.dumps(asdict(capabilities), ensure_ascii=False, indent=2)
    context_block = (
        f"\n\n[선택적 문맥 파일: {context_path}]\n{context.strip()}"
        if context_path
        else "\n\n[선택적 문맥]\n없음"
    )
    return f"""당신은 Personal Problem-Solving OS의 AI 판단·실행 엔진이다.

사용자 요청의 상위 목적과 고정 조건을 보존하고, 가장 작은 충분 경로를 하나 선택한 뒤
현재 capability 안에서 실제 결과까지 만든다. 출력은 제공된 JSON Schema를 정확히 따른다.

[경로]
- DIRECT: 현재 지식과 제공 문맥으로 실제 답변/초안/분석을 완성한다.
- RESEARCH: 최신성·실재성·출처가 중요하며 실제 웹 검색이 필요하다.
- REUSE: 기존 로컬 자산, 도구, 템플릿 또는 오픈소스를 실제로 확인하고 적용 판단을 남긴다.
- PROMPT: 다른 AI나 별도 환경에서 반복 사용할 지침이 최종 산출물이다.
- CODE: 반복·재현성 때문에 코드가 적합하다. 쓰기 권한이 없으면 result_markdown에 완성 코드나
  실행 가능한 handoff를 주고 파일을 수정했다고 주장하지 않는다.
- PROJECT: 여러 단계와 상태 유지가 정말 필요할 때만 고르고 가장 가까운 완료 가능한 단계 하나를 수행한다.
- HYBRID: 주 경로 하나(primary_route)와 보조 경로 하나(secondary_route)만 허용한다.

[중요 규칙]
1. Python 키워드 규칙을 대신 수행하는 의미 판단 단계다. 요청 표현을 다른 비슷한 목표로 바꾸지 않는다.
2. 단순 요청을 CODE/PROJECT/HYBRID로 키우지 않는다.
3. 검색 capability가 없으면 RESEARCH를 수행했다고 꾸미지 말고 blocked_by_capability와 handoff를 쓴다.
4. 실제로 확인한 자산만 evidence에 기록한다. 이름만 추천하지 않는다.
5. 실제 도구 실행, 생성된 결과, 제안을 execution.status와 artifacts.action으로 구분한다.
6. PROMPT를 고르면 구체적 목표·제약·사용 환경을 ledger에 보존한다. 최종 프롬프트 조립은
   외곽 실행기가 기존 Prompt Compiler에 맡기므로 result_markdown에는 간단한 요구 요약만 둔다.
7. 내부 추론 과정은 노출하지 않는다. route_reason과 결과에 필요한 짧은 근거만 쓴다.
8. 웹 검색이 켜져 있어도 RESEARCH/REUSE에 필요하지 않으면 사용하지 않는다.
9. 사용하지 않은 capability나 실행하지 않은 명령을 capabilities_used/evidence에 넣지 않는다.
10. 단일 경로에서는 primary_route와 secondary_route를 모두 null로 둔다. HYBRID에서만 둘을 채운다.

[현재 capability]
{capability_json}

[사용자 요청]
{request.strip()}{context_block}
"""


def validate_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ProblemSolvingError(f"{field}는 비어 있지 않은 문자열 배열이어야 합니다.")


def validate_engine_output(payload: Any, capabilities: EngineCapabilities) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"goal_ledger", "route", "execution"}:
        raise ProblemSolvingError("AI 결과 최상위 필드가 스키마와 일치하지 않습니다.")
    ledger = payload["goal_ledger"]
    route = payload["route"]
    execution = payload["execution"]
    if not isinstance(ledger, dict) or set(ledger) != LEDGER_FIELDS:
        raise ProblemSolvingError("Goal Ledger 필드가 스키마와 일치하지 않습니다.")
    if not isinstance(route, dict) or set(route) != {
        "selected_route",
        "primary_route",
        "secondary_route",
        "route_reason",
    }:
        raise ProblemSolvingError("route 필드가 스키마와 일치하지 않습니다.")
    expected_execution_fields = {
        "status",
        "summary",
        "result_markdown",
        "capabilities_used",
        "needed_capability",
        "handoff",
        "artifacts",
        "evidence",
        "limitations",
    }
    if not isinstance(execution, dict) or set(execution) != expected_execution_fields:
        raise ProblemSolvingError("execution 필드가 스키마와 일치하지 않습니다.")

    selected = route["selected_route"]
    if selected not in ROUTES:
        raise ProblemSolvingError(f"지원하지 않는 경로입니다: {selected}")
    primary = route["primary_route"]
    secondary = route["secondary_route"]
    if selected == "HYBRID":
        if primary not in ROUTES - {"HYBRID"} or secondary not in ROUTES - {"HYBRID"}:
            raise ProblemSolvingError("HYBRID는 서로 다른 주/보조 경로가 각각 하나 필요합니다.")
        if primary == secondary:
            raise ProblemSolvingError("HYBRID 주 경로와 보조 경로는 달라야 합니다.")
    else:
        if primary == selected:
            route["primary_route"] = None
            primary = None
        if primary is not None or secondary is not None:
            raise ProblemSolvingError("단일 경로에는 다른 primary/secondary route를 둘 수 없습니다.")
    if ledger["selected_route"] != selected or ledger["secondary_route"] != secondary:
        raise ProblemSolvingError("Goal Ledger와 route 선택이 일치하지 않습니다.")
    ledger["route_reason"] = route["route_reason"]

    for field in (
        "parent_goal",
        "current_goal_hypothesis",
        "current_position",
        "route_reason",
        "current_step",
        "why_this_step_matters",
        "completion_condition",
    ):
        if not isinstance(ledger[field], str) or not ledger[field].strip():
            raise ProblemSolvingError(f"Goal Ledger {field}가 비어 있습니다.")
    validate_string_list(ledger["fixed_constraints"], "fixed_constraints")
    if len(ledger["important_uncertainties"]) > 3:
        raise ProblemSolvingError("important_uncertainties는 최대 3개입니다.")
    if ledger["important_uncertainties"]:
        validate_string_list(ledger["important_uncertainties"], "important_uncertainties")

    if execution["status"] not in EXECUTION_STATUSES:
        raise ProblemSolvingError("지원하지 않는 execution.status입니다.")
    for field in ("summary", "result_markdown"):
        if not isinstance(execution[field], str) or not execution[field].strip():
            raise ProblemSolvingError(f"execution.{field}가 비어 있습니다.")
    for field in ("capabilities_used", "limitations"):
        if not isinstance(execution[field], list) or not all(
            isinstance(item, str) and item.strip() for item in execution[field]
        ):
            raise ProblemSolvingError(f"execution.{field}가 문자열 배열이 아닙니다.")
    if not isinstance(execution["artifacts"], list) or not isinstance(
        execution["evidence"], list
    ):
        raise ProblemSolvingError("artifacts/evidence는 배열이어야 합니다.")
    for artifact in execution["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != {
            "path",
            "action",
            "verification",
        }:
            raise ProblemSolvingError("artifact 필드가 스키마와 일치하지 않습니다.")
        if (
            artifact["action"] in {"created", "modified"}
            and not capabilities.workspace_write
        ):
            raise ProblemSolvingError(
                "쓰기 capability 없이 파일 생성/수정을 주장한 AI 결과를 거부했습니다."
            )
    for evidence in execution["evidence"]:
        if not isinstance(evidence, dict) or set(evidence) != {
            "source",
            "finding",
            "kind",
        }:
            raise ProblemSolvingError("evidence 필드가 스키마와 일치하지 않습니다.")

    requested_routes = {selected}
    if selected == "HYBRID":
        requested_routes = {primary, secondary}
    if "RESEARCH" in requested_routes and not capabilities.web_search:
        execution["status"] = "blocked_by_capability"
        execution["needed_capability"] = "live web search"
        execution["handoff"] = (
            execution["handoff"]
            or "웹 검색 가능한 Codex 환경에서 같은 요청을 --search로 다시 실행하세요."
        )
        execution["result_markdown"] = (
            "현재 실행 환경에는 라이브 웹 검색 capability가 없어 최신 사실을 조사하지 않았습니다.\n\n"
            + execution["handoff"]
        )
        if "live web search가 없어 실제 조사를 수행하지 않음" not in execution["limitations"]:
            execution["limitations"].append("live web search가 없어 실제 조사를 수행하지 않음")
        execution["evidence"] = []
    return payload


def load_prompt_runtime() -> Any:
    spec = importlib.util.spec_from_file_location("prompt_runtime", PROMPT_RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise ProblemSolvingError("기존 Prompt Compiler 실행기를 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_prompt_compiler(
    payload: dict[str, Any],
    request: str,
    context_path: Path | None,
    run_dir: Path,
) -> dict[str, Any]:
    runtime = load_prompt_runtime()
    context_paths = [context_path] if context_path is not None else []
    if payload["route"]["selected_route"] == "HYBRID":
        hybrid_context = run_dir / "prompt-compiler-context.md"
        hybrid_context.write_text(
            "# Primary route result\n\n"
            + payload["execution"]["result_markdown"].strip()
            + "\n",
            encoding="utf-8",
        )
        context_paths.append(hybrid_context)
    try:
        compiled = runtime.create_prompt(
            request,
            context_paths,
            tools_allowed=False,
        )
    except Exception as exc:
        raise ProblemSolvingError(f"기존 Prompt Compiler 실행 실패: {exc}") from exc
    execution = payload["execution"]
    compiler_markdown = (
        "### 생성된 프롬프트\n\n"
        f"{compiled['final_prompt']}\n\n"
        "### Prompt Compiler 기록\n\n"
        f"- 모드: `{compiled['selected_mode']}`\n"
        f"- fallback: `{'yes' if compiled['fallback'] else 'no'}`\n"
        f"- 선택 이유: {compiled['selection_reason']}"
    )
    if payload["route"]["selected_route"] == "HYBRID":
        execution["summary"] = (
            f"{execution['summary']} 기존 Prompt Compiler로 실행 프롬프트도 생성했습니다."
        )
        execution["result_markdown"] = (
            f"{execution['result_markdown'].strip()}\n\n{compiler_markdown}"
        )
        execution["limitations"] = [
            item
            for item in execution["limitations"]
            if "Prompt Compiler" not in item and "프롬프트 본문 조립" not in item
        ]
    else:
        execution["status"] = "completed"
        execution["summary"] = "기존 Prompt Compiler로 재사용 가능한 실행 프롬프트를 생성했습니다."
        execution["result_markdown"] = compiler_markdown
        execution["limitations"] = (
            [compiled["fallback_reason"]]
            if compiled["fallback"] and compiled["fallback_reason"]
            else []
        )
    if "prompt_compiler" not in execution["capabilities_used"]:
        execution["capabilities_used"].append("prompt_compiler")
    execution["needed_capability"] = None
    execution["handoff"] = None
    execution["artifacts"].append(
        {
            "path": "result.md",
            "action": "generated_in_result",
            "verification": "기존 scripts/prompt_runtime.py create_prompt 호출 성공",
        }
    )
    payload["prompt_compiler"] = {
        "selected_mode": compiled["selected_mode"],
        "selection_reason": compiled["selection_reason"],
        "used_patterns": compiled["used_patterns"],
        "used_active_sources": compiled["used_active_sources"],
        "fallback": compiled["fallback"],
        "fallback_reason": compiled["fallback_reason"],
    }
    return payload


def blocked_payload(request: str, detail: str) -> dict[str, Any]:
    return {
        "goal_ledger": {
            "parent_goal": request.strip(),
            "current_goal_hypothesis": request.strip(),
            "fixed_constraints": ["사용자 요청의 목적과 조건을 보존한다."],
            "current_position": "AI 판단 엔진 capability 확인",
            "selected_route": "",
            "secondary_route": None,
            "route_reason": "의미 판단 엔진을 실행할 수 없어 경로를 추정하지 않음",
            "current_step": "실행 가능한 Codex CLI 연결",
            "why_this_step_matters": "목적 추론과 경로 선택을 규칙 기반으로 가장하지 않기 위해 필요함",
            "completion_condition": "Codex CLI가 구독 인증으로 실행됨",
            "important_uncertainties": ["가장 작은 충분 해결 경로"],
        },
        "route": {
            "selected_route": None,
            "primary_route": None,
            "secondary_route": None,
            "route_reason": "blocked before AI routing",
            "status": "blocked_by_capability",
            "fallback": None,
        },
        "execution": {
            "status": "blocked_by_capability",
            "summary": "AI 판단 엔진을 사용할 수 없어 실행을 중단했습니다.",
            "result_markdown": (
                "Codex CLI를 실행할 수 없어 목표 추론·경로 선택·결과 생성을 수행하지 않았습니다."
            ),
            "capabilities_used": [],
            "needed_capability": "ChatGPT 구독으로 인증된 Codex CLI",
            "handoff": (
                "`codex login status`로 구독 인증을 확인한 뒤 같은 명령을 다시 실행하세요."
            ),
            "artifacts": [],
            "evidence": [],
            "limitations": [detail],
        },
    }


def result_markdown(payload: dict[str, Any]) -> str:
    ledger = payload["goal_ledger"]
    route = payload["route"]
    execution = payload["execution"]
    route_label = route.get("selected_route") or "미선택"
    if route_label == "HYBRID":
        route_label = (
            f"HYBRID ({route.get('primary_route')} + {route.get('secondary_route')})"
        )
    limitations = execution.get("limitations") or []
    if execution.get("status") == "blocked_by_capability" and execution.get("handoff"):
        limitations = [*limitations, execution["handoff"]]
    limitation_text = (
        "\n".join(f"- {item}" for item in dict.fromkeys(limitations))
        if limitations
        else "- 없음"
    )
    return (
        f"현재 목표: {ledger['current_goal_hypothesis']}\n"
        f"선택한 해결 방식: {route_label}\n"
        f"선택 이유: {route.get('route_reason', ledger['route_reason'])}\n\n"
        f"결과:\n\n{execution['result_markdown'].strip()}\n\n"
        f"남은 핵심 한계:\n{limitation_text}\n"
    )


def run_request(
    request: str,
    *,
    context_path: Path | None = None,
    output_root: Path = RUNS_DIR,
    engine: ProblemSolvingEngine,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if not request or not request.strip():
        raise ProblemSolvingError("사용자 요청은 비어 있을 수 없습니다.")
    context, resolved_context = read_context(context_path)
    chosen_run_id = run_id or make_run_id()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", chosen_run_id):
        raise ProblemSolvingError("run-id는 영문자, 숫자, 점, 밑줄, 하이픈만 허용합니다.")
    run_dir = output_root.expanduser().resolve() / chosen_run_id
    if run_dir.exists():
        raise ProblemSolvingError(f"이미 존재하는 run-id입니다: {chosen_run_id}")
    run_dir.mkdir(parents=True)
    (run_dir / "request.txt").write_text(request.strip() + "\n", encoding="utf-8")

    started_at = utc_now().isoformat()
    capabilities = engine.capabilities()
    if not capabilities.ai_reasoning:
        payload = blocked_payload(request, capabilities.detail)
    else:
        try:
            prompt = build_engine_prompt(
                request, context, resolved_context, capabilities
            )
            payload = validate_engine_output(engine.execute(prompt, run_dir), capabilities)
            selected = payload["route"]["selected_route"]
            primary = payload["route"]["primary_route"]
            routes = {selected} if selected != "HYBRID" else {primary, payload["route"]["secondary_route"]}
            if "PROMPT" in routes:
                payload = apply_prompt_compiler(
                    payload, request, context_path, run_dir
                )
        except ProblemSolvingError as exc:
            payload = blocked_payload(request, str(exc))

    payload["run"] = {
        "run_id": chosen_run_id,
        "started_at": started_at,
        "finished_at": utc_now().isoformat(),
        "context_file": resolved_context,
        "capabilities": asdict(capabilities),
    }
    ledger = payload["goal_ledger"]
    route_record = {
        **payload["route"],
        "execution_status": payload["execution"]["status"],
        "capabilities_used": payload["execution"]["capabilities_used"],
        "needed_capability": payload["execution"]["needed_capability"],
        "handoff": payload["execution"]["handoff"],
        "artifacts": payload["execution"]["artifacts"],
        "evidence": payload["execution"]["evidence"],
        "limitations": payload["execution"]["limitations"],
        "run": payload["run"],
    }
    if "prompt_compiler" in payload:
        route_record["prompt_compiler"] = payload["prompt_compiler"]
    write_json(run_dir / "goal_ledger.json", ledger)
    write_json(run_dir / "route.json", route_record)
    (run_dir / "result.md").write_text(result_markdown(payload), encoding="utf-8")
    return run_dir, payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="평범한 문장으로 쓴 사용자 요청")
    parser.add_argument("--context-file", type=Path, help="선택적 UTF-8 문맥 파일")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT,
        help="AI 엔진이 읽거나 명시적 허용 시 수정할 작업 공간",
    )
    parser.add_argument(
        "--allow-workspace-write",
        action="store_true",
        help="CODE/PROJECT 실행에서 Codex CLI의 workspace-write를 명시적으로 허용",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="라이브 웹 검색 capability를 끔(테스트 또는 제한 환경용)",
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR, help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    engine = CodexEngine(
        args.workspace,
        allow_workspace_write=args.allow_workspace_write,
        enable_search=not args.no_search,
    )
    try:
        run_dir, payload = run_request(
            args.request,
            context_path=args.context_file,
            output_root=args.runs_dir,
            engine=engine,
            run_id=args.run_id,
        )
    except ProblemSolvingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print((run_dir / "result.md").read_text(encoding="utf-8").rstrip())
    print(f"\n실행 기록: {run_dir}")
    return 2 if payload["execution"]["status"] == "blocked_by_capability" else 0


if __name__ == "__main__":
    raise SystemExit(main())
