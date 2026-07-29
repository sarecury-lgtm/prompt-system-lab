#!/usr/bin/env python3
"""Run the Personal Problem-Solving OS with route-specific Codex models."""

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
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
ROUTE_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-route.schema.json"
EXECUTION_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-os-execution.schema.json"
DEFAULT_MODEL_POLICY_PATH = ROOT / "problem-solving-project" / "model-policy.json"
PROMPT_RUNTIME_PATH = ROOT / "scripts" / "prompt_runtime.py"

ROUTES = {"DIRECT", "RESEARCH", "REUSE", "PROMPT", "CODE", "PROJECT", "HYBRID"}
SINGLE_ROUTES = ROUTES - {"HYBRID"}
EXECUTION_STATUSES = {"completed", "partial", "blocked_by_capability", "handoff"}
REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max", "ultra"}
SANDBOXES = {"read-only", "workspace-write"}
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
EXECUTION_FIELDS = {
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


class ProblemSolvingError(Exception):
    """A recoverable problem-solving runtime failure."""


@dataclass(frozen=True)
class EngineCapabilities:
    ai_reasoning: bool
    web_search: bool
    workspace_read: bool
    workspace_write: bool
    detail: str = ""


@dataclass(frozen=True)
class ModelProfile:
    model: str
    reasoning_effort: str
    web_search: bool
    sandbox: str


@dataclass(frozen=True)
class InvocationSpec:
    name: str
    phase: str
    route: str | None
    profile: ModelProfile
    schema_path: Path


class ProblemSolvingEngine(Protocol):
    def capabilities(self) -> EngineCapabilities:
        """Return capabilities that are available for this run."""

    def execute(
        self,
        prompt: str,
        run_dir: Path,
        invocation: InvocationSpec,
    ) -> dict[str, Any]:
        """Execute one explicitly configured model stage."""

    def trace(self) -> list[dict[str, Any]]:
        """Return a serializable trace of model invocations."""


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


def parse_model_profile(value: Any, label: str) -> ModelProfile:
    expected = {"model", "reasoning_effort", "web_search", "sandbox"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ProblemSolvingError(f"{label} 모델 프로필 필드가 올바르지 않습니다.")
    if not isinstance(value["model"], str) or not value["model"].strip():
        raise ProblemSolvingError(f"{label}.model이 비어 있습니다.")
    if value["reasoning_effort"] not in REASONING_EFFORTS:
        raise ProblemSolvingError(f"{label}.reasoning_effort가 지원되지 않습니다.")
    if not isinstance(value["web_search"], bool):
        raise ProblemSolvingError(f"{label}.web_search는 boolean이어야 합니다.")
    if value["sandbox"] not in SANDBOXES:
        raise ProblemSolvingError(f"{label}.sandbox가 지원되지 않습니다.")
    return ModelProfile(**value)


def load_model_policy(path: Path = DEFAULT_MODEL_POLICY_PATH) -> dict[str, Any]:
    try:
        resolved = path.expanduser().resolve(strict=True)
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProblemSolvingError(f"모델 정책을 읽을 수 없습니다: {path}: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "version",
        "router",
        "router_fallback",
        "routes",
    }:
        raise ProblemSolvingError("모델 정책 최상위 필드가 올바르지 않습니다.")
    if raw["version"] != 1:
        raise ProblemSolvingError("지원하지 않는 모델 정책 버전입니다.")
    if not isinstance(raw["routes"], dict) or set(raw["routes"]) != SINGLE_ROUTES:
        raise ProblemSolvingError("모델 정책은 모든 단일 경로를 정확히 한 번 정의해야 합니다.")
    routes: dict[str, dict[str, ModelProfile | None]] = {}
    for route, value in raw["routes"].items():
        if not isinstance(value, dict) or set(value) != {"primary", "fallback"}:
            raise ProblemSolvingError(f"{route} 모델 정책 필드가 올바르지 않습니다.")
        fallback = (
            parse_model_profile(value["fallback"], f"routes.{route}.fallback")
            if value["fallback"] is not None
            else None
        )
        routes[route] = {
            "primary": parse_model_profile(
                value["primary"], f"routes.{route}.primary"
            ),
            "fallback": fallback,
        }
    return {
        "version": 1,
        "path": str(resolved),
        "router": parse_model_profile(raw["router"], "router"),
        "router_fallback": parse_model_profile(
            raw["router_fallback"], "router_fallback"
        ),
        "routes": routes,
    }


def public_model_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": policy["version"],
        "path": policy["path"],
        "router": asdict(policy["router"]),
        "router_fallback": asdict(policy["router_fallback"]),
        "routes": {
            route: {
                "primary": asdict(value["primary"]),
                "fallback": (
                    asdict(value["fallback"]) if value["fallback"] is not None else None
                ),
            }
            for route, value in policy["routes"].items()
        },
    }


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
    """Codex CLI adapter using explicit model, effort, tools, and sandbox per stage."""

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
        self._trace: list[dict[str, Any]] = []

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
                    f"workspace_write={'requested' if self.allow_workspace_write else 'disabled'}"
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

    def execute(
        self,
        prompt: str,
        run_dir: Path,
        invocation: InvocationSpec,
    ) -> dict[str, Any]:
        capabilities = self.capabilities()
        if not capabilities.ai_reasoning or self._executable is None:
            raise ProblemSolvingError(capabilities.detail or "Codex CLI를 실행할 수 없습니다.")
        if invocation.profile.web_search and not capabilities.web_search:
            raise ProblemSolvingError("선택한 실행 단계에 필요한 라이브 웹 검색이 없습니다.")

        effective_sandbox = invocation.profile.sandbox
        if effective_sandbox == "workspace-write" and not capabilities.workspace_write:
            effective_sandbox = "read-only"
        request_path = run_dir / f"{invocation.name}-request.md"
        output_path = run_dir / f"{invocation.name}-output.json"
        log_path = run_dir / f"{invocation.name}.log"
        request_path.write_text(prompt, encoding="utf-8")

        record = {
            "name": invocation.name,
            "phase": invocation.phase,
            "route": invocation.route,
            "model": invocation.profile.model,
            "reasoning_effort": invocation.profile.reasoning_effort,
            "web_search": invocation.profile.web_search,
            "requested_sandbox": invocation.profile.sandbox,
            "effective_sandbox": effective_sandbox,
            "schema": str(invocation.schema_path),
            "status": "running",
            "output": str(output_path),
            "log": str(log_path),
        }
        self._trace.append(record)

        arguments: list[str] = []
        if invocation.profile.web_search:
            arguments.append("--search")
        arguments.extend(
            [
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "-m",
                invocation.profile.model,
                "-c",
                f"model_reasoning_effort={invocation.profile.reasoning_effort}",
                "--sandbox",
                effective_sandbox,
                "--cd",
                str(self.workspace),
                "--output-schema",
                str(invocation.schema_path),
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
            record["status"] = "failed_to_start"
            record["error"] = str(exc)
            raise ProblemSolvingError(f"Codex CLI 실행 실패: {exc}") from exc
        log_path.write_text(completed.stdout or "", encoding="utf-8")
        record["exit_code"] = completed.returncode
        if completed.returncode != 0:
            record["status"] = "failed"
            raise ProblemSolvingError(
                f"{invocation.name} Codex CLI가 exit {completed.returncode}로 실패했습니다."
            )
        if not output_path.is_file():
            record["status"] = "missing_output"
            raise ProblemSolvingError(
                f"{invocation.name} Codex CLI가 구조화 결과를 만들지 않았습니다."
            )
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            record["status"] = "invalid_json"
            record["error"] = str(exc)
            raise ProblemSolvingError(
                f"{invocation.name} 결과 JSON을 읽을 수 없습니다: {exc}"
            ) from exc
        record["status"] = "completed"
        return payload

    def trace(self) -> list[dict[str, Any]]:
        return json.loads(json.dumps(self._trace))


def context_block(context: str, context_path: str | None) -> str:
    if context_path:
        return f"\n\n[선택적 문맥 파일: {context_path}]\n{context.strip()}"
    return "\n\n[선택적 문맥]\n없음"


def build_router_prompt(
    request: str,
    context: str,
    context_path: str | None,
    capabilities: EngineCapabilities,
) -> str:
    capability_json = json.dumps(asdict(capabilities), ensure_ascii=False, indent=2)
    return f"""당신은 Personal Problem-Solving OS의 라우터다.

사용자 요청의 상위 목적과 고정 조건을 보존하고 Goal Ledger를 작성한 뒤, 가장 작은 충분
해결 경로만 선택한다. 이 단계에서는 답변·검색·프롬프트·코드 결과를 만들지 않는다.

[경로]
- DIRECT: 현재 지식과 제공 문맥으로 바로 답할 수 있음
- RESEARCH: 최신성·실재성·공식 출처가 결과를 바꿈
- REUSE: 승인된 범위의 기존 자산·도구·템플릿을 실제로 확인해야 함
- PROMPT: 다른 AI나 별도 환경에서 반복 사용할 지침 자체가 산출물
- CODE: 반복·재현성·대량 처리 때문에 코드가 적합
- PROJECT: 여러 단계·파일·상태 유지가 정말 필요
- HYBRID: 주 경로 하나와 보조 경로 하나가 모두 필요

[선택 규칙]
1. 단순 요청을 CODE/PROJECT/HYBRID로 키우지 않는다.
2. RESEARCH 후 PROMPT처럼 두 경로가 실제로 필요할 때만 HYBRID를 쓴다.
3. 단일 경로에서는 primary_route와 secondary_route를 모두 null로 둔다.
4. HYBRID에서만 서로 다른 primary_route와 secondary_route를 하나씩 쓴다.
5. capability 부족은 경로를 왜곡하지 않는다. 필요한 경로를 고르면 외곽 실행기가 차단한다.
6. 내부 추론은 노출하지 않고 짧은 route_reason만 기록한다.
7. fixed_constraints에는 사용자 요청에서 나온 조건만 넣는다. "라우터는 결과를 만들지 않는다" 같은
   파이프라인 내부 규칙을 사용자 제약으로 기록하지 않는다.
8. current_step과 completion_condition은 선택된 경로가 만들 실제 사용자 결과를 설명한다.
   라우팅 완료나 외곽 실행기로 전달하는 것을 완료 조건으로 쓰지 않는다.

[현재 capability]
{capability_json}

[사용자 요청]
{request.strip()}{context_block(context, context_path)}
"""


ROUTE_EXECUTION_RULES = {
    "DIRECT": (
        "현재 지식과 제공 문맥으로 실제 답변·분석·초안을 완성한다. 불필요한 검색이나 "
        "프로젝트화를 하지 않는다."
    ),
    "RESEARCH": (
        "라이브 웹 검색으로 필요한 최신 사실을 조사한다. 공식·1차 출처를 우선하고, "
        "확인 사실·추론·미확인을 구분하며 evidence에 실제 출처를 기록한다. "
        "HYBRID의 주 경로라면 조사 결과만 만들고 후속 프롬프트까지 미리 작성하지 않는다."
    ),
    "REUSE": (
        "승인된 작업공간에서 기존 자산을 실제로 읽고 어떤 실패를 막는지 확인한다. "
        "이름만 추천하지 말고 evidence에 확인 위치와 발견 내용을 남긴다."
    ),
    "PROMPT": (
        "기존 Prompt Compiler baseline을 출발점으로 삼아 다른 AI가 반복 실행할 최종 프롬프트 하나를 "
        "완성한다. baseline을 바꿀 때는 목적·제약·출력 계약을 보존하고, 주 경로의 조사 내용을 "
        "프롬프트 밖에서 다시 장황하게 반복하지 않는다. 검증된 주 경로 결과를 다시 검색하지 않은 "
        "사실은 한계가 아니며, limitations에는 최종 프롬프트에 실제로 남은 한계만 쓴다."
    ),
    "CODE": (
        "가장 작은 안전한 코드 변경과 검증을 수행한다. 쓰기가 실제로 허용되지 않으면 "
        "파일을 바꿨다고 주장하지 말고 완성 코드 또는 실행 가능한 handoff를 제공한다."
    ),
    "PROJECT": (
        "상태 유지가 필요한 이유를 보존하면서 가장 가까운 완료 가능한 단계 하나만 수행한다. "
        "계획을 크게 확장하지 않는다."
    ),
}


def build_execution_prompt(
    route: str,
    request: str,
    ledger: dict[str, Any],
    context: str,
    context_path: str | None,
    capabilities: EngineCapabilities,
    profile: ModelProfile,
    primary_execution: dict[str, Any] | None = None,
    prompt_compiler_baseline: dict[str, Any] | None = None,
) -> str:
    effective_capabilities = asdict(capabilities)
    effective_capabilities["workspace_write"] = (
        capabilities.workspace_write and profile.sandbox == "workspace-write"
    )
    primary_block = ""
    if primary_execution is not None:
        primary_block = (
            "\n\n[주 경로의 실제 결과]\n"
            + json.dumps(primary_execution, ensure_ascii=False, indent=2)
        )
    compiler_block = ""
    if prompt_compiler_baseline is not None:
        compiler_block = (
            "\n\n[기존 Prompt Compiler baseline]\n"
            + json.dumps(prompt_compiler_baseline, ensure_ascii=False, indent=2)
        )
    return f"""당신은 Personal Problem-Solving OS의 {route} 실행기다.

라우터가 고정한 목표와 조건을 바꾸지 말고 현재 단계의 실제 결과를 만든다.

[이 경로의 행동]
{ROUTE_EXECUTION_RULES[route]}

[공통 규칙]
1. 실행한 도구, 생성한 결과, 제안을 execution.status와 artifacts.action으로 구분한다.
2. 확인하지 않은 사실·자산·명령 결과를 evidence에 넣지 않는다.
3. capability가 없으면 성공을 꾸미지 말고 blocked_by_capability와 바로 실행 가능한 handoff를 쓴다.
4. 내부 추론 과정은 노출하지 않는다.
5. 사용자에게 바로 쓸 수 있는 결과를 result_markdown에 넣는다.
6. 완료 상태에서는 경로 선택이나 다음 작업을 설명하지 말고 요청된 최종 내용 자체를 쓴다.
   "외곽 실행 단계에서 작성하면 된다"처럼 일을 미루는 문장은 결과가 아니다.

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[현재 실행 프로필]
{json.dumps(asdict(profile), ensure_ascii=False, indent=2)}

[현재 capability]
{json.dumps(effective_capabilities, ensure_ascii=False, indent=2)}

[사용자 요청]
{request.strip()}{context_block(context, context_path)}{primary_block}{compiler_block}
"""


def validate_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ProblemSolvingError(f"{field}는 비어 있지 않은 문자열 배열이어야 합니다.")


def validate_route_output(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"goal_ledger", "route"}:
        raise ProblemSolvingError("라우터 결과 최상위 필드가 스키마와 일치하지 않습니다.")
    ledger = payload["goal_ledger"]
    route = payload["route"]
    if not isinstance(ledger, dict) or set(ledger) != LEDGER_FIELDS:
        raise ProblemSolvingError("Goal Ledger 필드가 스키마와 일치하지 않습니다.")
    if not isinstance(route, dict) or set(route) != {
        "selected_route",
        "primary_route",
        "secondary_route",
        "route_reason",
    }:
        raise ProblemSolvingError("route 필드가 스키마와 일치하지 않습니다.")

    selected = route["selected_route"]
    if selected not in ROUTES:
        raise ProblemSolvingError(f"지원하지 않는 경로입니다: {selected}")
    primary = route["primary_route"]
    secondary = route["secondary_route"]
    if selected == "HYBRID":
        if primary not in SINGLE_ROUTES or secondary not in SINGLE_ROUTES:
            raise ProblemSolvingError("HYBRID는 주/보조 경로가 각각 하나 필요합니다.")
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
    pipeline_markers = (
        "이 단계에서는",
        "라우팅 완료",
        "외곽 실행",
        "실행기로 전달",
        "다음 단계로 전달",
        "결과를 만들지",
    )
    user_constraints = " ".join(ledger["fixed_constraints"])
    completion_contract = " ".join(
        [ledger["current_step"], ledger["completion_condition"]]
    )
    if any(marker in user_constraints for marker in pipeline_markers):
        raise ProblemSolvingError("라우터 내부 규칙이 사용자 고정 조건을 오염시켰습니다.")
    if any(marker in completion_contract for marker in pipeline_markers):
        raise ProblemSolvingError("라우팅 완료를 사용자 결과 완료 조건으로 바꿨습니다.")
    return payload


def validate_execution_output(
    payload: Any,
    route: str,
    profile: ModelProfile,
    capabilities: EngineCapabilities,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"execution"}:
        raise ProblemSolvingError("실행기 결과 최상위 필드가 스키마와 일치하지 않습니다.")
    execution = payload["execution"]
    if not isinstance(execution, dict) or set(execution) != EXECUTION_FIELDS:
        raise ProblemSolvingError("execution 필드가 스키마와 일치하지 않습니다.")
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

    write_effective = capabilities.workspace_write and profile.sandbox == "workspace-write"
    for artifact in execution["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != {
            "path",
            "action",
            "verification",
        }:
            raise ProblemSolvingError("artifact 필드가 스키마와 일치하지 않습니다.")
        if artifact["action"] in {"created", "modified"} and not write_effective:
            raise ProblemSolvingError(
                "쓰기 capability 없이 파일 생성/수정을 주장한 실행 결과를 거부했습니다."
            )
    for evidence in execution["evidence"]:
        if not isinstance(evidence, dict) or set(evidence) != {
            "source",
            "finding",
            "kind",
        }:
            raise ProblemSolvingError("evidence 필드가 스키마와 일치하지 않습니다.")
    if route == "RESEARCH" and execution["status"] == "completed":
        if not any(item["kind"] == "web" for item in execution["evidence"]):
            raise ProblemSolvingError("완료된 RESEARCH 결과에 실제 웹 근거가 없습니다.")
    if route == "REUSE" and execution["status"] == "completed":
        if not execution["evidence"]:
            raise ProblemSolvingError("완료된 REUSE 결과에 실제 자산 확인 근거가 없습니다.")
    if route == "DIRECT" and execution["status"] == "completed":
        meta_markers = (
            "외곽 실행",
            "다음 단계에서",
            "작성하면 됩니다",
            "제공하면 됩니다",
            "경로가 적절",
        )
        if any(marker in execution["result_markdown"] for marker in meta_markers):
            raise ProblemSolvingError("DIRECT 실행기가 실제 답 대신 다음 작업 안내를 반환했습니다.")

    for item in (
        f"model:{profile.model}",
        f"reasoning:{profile.reasoning_effort}",
    ):
        if item not in execution["capabilities_used"]:
            execution["capabilities_used"].append(item)
    return execution


def blocked_execution(
    result: str,
    *,
    needed_capability: str,
    handoff: str,
    limitation: str,
) -> dict[str, Any]:
    return {
        "status": "blocked_by_capability",
        "summary": result,
        "result_markdown": result,
        "capabilities_used": [],
        "needed_capability": needed_capability,
        "handoff": handoff,
        "artifacts": [],
        "evidence": [],
        "limitations": [limitation],
    }


def blocked_payload(request: str, detail: str) -> dict[str, Any]:
    execution = blocked_execution(
        "Codex CLI를 실행할 수 없어 목표 추론·경로 선택·결과 생성을 수행하지 않았습니다.",
        needed_capability="ChatGPT 구독으로 인증된 Codex CLI",
        handoff="`codex login status`로 구독 인증을 확인한 뒤 같은 명령을 다시 실행하세요.",
        limitation=detail,
    )
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
        "execution": execution,
    }


def invoke_router(
    engine: ProblemSolvingEngine,
    prompt: str,
    run_dir: Path,
    policy: dict[str, Any],
    orchestration_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    attempts = [
        ("router", policy["router"]),
        ("router-fallback", policy["router_fallback"]),
    ]
    errors: list[str] = []
    for name, profile in attempts:
        invocation = InvocationSpec(
            name=name,
            phase="router",
            route=None,
            profile=profile,
            schema_path=ROUTE_SCHEMA_PATH,
        )
        try:
            result = validate_route_output(engine.execute(prompt, run_dir, invocation))
            orchestration_trace.append(
                {
                    "name": name,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "accepted",
                }
            )
            return result
        except ProblemSolvingError as exc:
            errors.append(f"{name}: {exc}")
            orchestration_trace.append(
                {
                    "name": name,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "rejected",
                    "error": str(exc),
                }
            )
    raise ProblemSolvingError("라우터와 fallback이 모두 실패했습니다: " + "; ".join(errors))


def execute_route(
    route: str,
    engine: ProblemSolvingEngine,
    policy: dict[str, Any],
    capabilities: EngineCapabilities,
    run_dir: Path,
    request: str,
    ledger: dict[str, Any],
    context: str,
    context_path: str | None,
    orchestration_trace: list[dict[str, Any]],
    primary_execution: dict[str, Any] | None = None,
    prompt_compiler_baseline: dict[str, Any] | None = None,
    stage_label: str = "primary",
) -> dict[str, Any]:
    route_policy = policy["routes"][route]
    primary_profile = route_policy["primary"]
    if primary_profile.web_search and not capabilities.web_search:
        orchestration_trace.append(
            {
                "name": f"{stage_label}-{route.lower()}",
                "model": primary_profile.model,
                "reasoning_effort": primary_profile.reasoning_effort,
                "outcome": "blocked_before_model",
                "error": "live web search unavailable",
            }
        )
        return blocked_execution(
            "현재 실행 환경에는 라이브 웹 검색 capability가 없어 최신 사실을 조사하지 않았습니다.",
            needed_capability="live web search",
            handoff="웹 검색 가능한 Codex 환경에서 같은 요청을 다시 실행하세요.",
            limitation="live web search가 없어 실제 조사를 수행하지 않음",
        )

    attempts: list[tuple[str, ModelProfile]] = [
        (f"{stage_label}-{route.lower()}", primary_profile)
    ]
    if route_policy["fallback"] is not None:
        attempts.append((f"{stage_label}-{route.lower()}-fallback", route_policy["fallback"]))
    errors: list[str] = []
    for name, profile in attempts:
        invocation = InvocationSpec(
            name=name,
            phase="executor",
            route=route,
            profile=profile,
            schema_path=EXECUTION_SCHEMA_PATH,
        )
        prompt = build_execution_prompt(
            route,
            request,
            ledger,
            context,
            context_path,
            capabilities,
            profile,
            primary_execution,
            prompt_compiler_baseline,
        )
        try:
            payload = engine.execute(prompt, run_dir, invocation)
            execution = validate_execution_output(
                payload, route, profile, capabilities
            )
            orchestration_trace.append(
                {
                    "name": name,
                    "route": route,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "accepted",
                    "execution_status": execution["status"],
                }
            )
            return execution
        except ProblemSolvingError as exc:
            errors.append(f"{name}: {exc}")
            orchestration_trace.append(
                {
                    "name": name,
                    "route": route,
                    "model": profile.model,
                    "reasoning_effort": profile.reasoning_effort,
                    "outcome": "rejected",
                    "error": str(exc),
                }
            )
    return blocked_execution(
        f"{route} 실행 모델이 유효한 결과를 만들지 못했습니다.",
        needed_capability=f"{route} 실행 모델",
        handoff="실행 로그와 모델 접근성을 확인한 뒤 같은 run을 다시 실행하세요.",
        limitation="; ".join(errors),
    )


def merge_executions(
    primary_route: str,
    primary: dict[str, Any],
    secondary_route: str,
    secondary: dict[str, Any],
) -> dict[str, Any]:
    status = secondary["status"]
    if primary["status"] == "blocked_by_capability":
        status = "blocked_by_capability"
    elif primary["status"] != "completed" and status == "completed":
        status = "partial"
    if secondary["status"] == "completed":
        result = secondary["result_markdown"].strip()
        summary = secondary["summary"]
        limitations = secondary["limitations"]
    else:
        result = (
            f"### {primary_route} 결과\n\n{primary['result_markdown'].strip()}\n\n"
            f"### {secondary_route} 결과\n\n{secondary['result_markdown'].strip()}"
        )
        summary = f"{primary['summary']} {secondary['summary']}"
        limitations = list(
            dict.fromkeys([*primary["limitations"], *secondary["limitations"]])
        )
    return {
        "status": status,
        "summary": summary,
        "result_markdown": result,
        "capabilities_used": list(
            dict.fromkeys(
                [*primary["capabilities_used"], *secondary["capabilities_used"]]
            )
        ),
        "needed_capability": (
            secondary["needed_capability"] or primary["needed_capability"]
        ),
        "handoff": secondary["handoff"] or primary["handoff"],
        "artifacts": [*primary["artifacts"], *secondary["artifacts"]],
        "evidence": [*primary["evidence"], *secondary["evidence"]],
        "limitations": limitations,
    }


def load_prompt_runtime() -> Any:
    spec = importlib.util.spec_from_file_location("prompt_runtime", PROMPT_RUNTIME_PATH)
    if spec is None or spec.loader is None:
        raise ProblemSolvingError("기존 Prompt Compiler 실행기를 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_prompt_compiler_baseline(
    request: str,
    context_path: Path | None,
    run_dir: Path,
    primary_execution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    runtime = load_prompt_runtime()
    compiler_context = run_dir / "prompt-compiler-context.md"
    upstream_result = (
        primary_execution["result_markdown"].strip()
        if primary_execution is not None
        else "상위 경로 결과 없음"
    )
    compiler_context.write_text(
        "# Upstream route result\n\n" + upstream_result + "\n",
        encoding="utf-8",
    )
    context_paths = [context_path] if context_path is not None else []
    context_paths.append(compiler_context)
    try:
        compiled = runtime.create_prompt(
            request,
            context_paths,
            tools_allowed=False,
        )
    except Exception as exc:
        raise ProblemSolvingError(f"기존 Prompt Compiler 실행 실패: {exc}") from exc
    return compiled, compiler_context


def attach_prompt_compiler_record(
    payload: dict[str, Any],
    compiled: dict[str, Any],
    compiler_context: Path,
) -> dict[str, Any]:
    execution = payload["execution"]
    if "prompt_compiler" not in execution["capabilities_used"]:
        execution["capabilities_used"].append("prompt_compiler")
    execution["artifacts"].append(
        {
            "path": str(compiler_context),
            "action": "inspected",
            "verification": "기존 scripts/prompt_runtime.py create_prompt 호출 후 PROMPT 실행기에 전달",
        }
    )
    payload["prompt_compiler"] = {
        "selected_mode": compiled["selected_mode"],
        "selection_reason": compiled["selection_reason"],
        "used_patterns": compiled["used_patterns"],
        "used_active_sources": compiled["used_active_sources"],
        "fallback": compiled["fallback"],
        "fallback_reason": compiled["fallback_reason"],
        "context_file": str(compiler_context),
        "application": "baseline_before_prompt_model",
    }
    return payload


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


def selected_model_plan(
    route: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    plan = [{"stage": "router", **asdict(policy["router"])}]
    selected = route.get("selected_route")
    if selected == "HYBRID":
        selected_routes = [route["primary_route"], route["secondary_route"]]
    elif selected in SINGLE_ROUTES:
        selected_routes = [selected]
    else:
        selected_routes = []
    for index, item in enumerate(selected_routes):
        plan.append(
            {
                "stage": "primary" if index == 0 else "secondary",
                "route": item,
                **asdict(policy["routes"][item]["primary"]),
            }
        )
    return plan


def run_request(
    request: str,
    *,
    context_path: Path | None = None,
    output_root: Path = RUNS_DIR,
    engine: ProblemSolvingEngine,
    model_policy: dict[str, Any] | None = None,
    model_policy_path: Path = DEFAULT_MODEL_POLICY_PATH,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    if not request or not request.strip():
        raise ProblemSolvingError("사용자 요청은 비어 있을 수 없습니다.")
    policy = model_policy or load_model_policy(model_policy_path)
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
    orchestration_trace: list[dict[str, Any]] = []
    if not capabilities.ai_reasoning:
        payload = blocked_payload(request, capabilities.detail)
    else:
        try:
            router_prompt = build_router_prompt(
                request, context, resolved_context, capabilities
            )
            payload = invoke_router(
                engine, router_prompt, run_dir, policy, orchestration_trace
            )
            selected = payload["route"]["selected_route"]
            compiled_prompt: dict[str, Any] | None = None
            compiler_context: Path | None = None
            if selected == "HYBRID":
                primary_route = payload["route"]["primary_route"]
                secondary_route = payload["route"]["secondary_route"]
                if primary_route == "PROMPT":
                    compiled_prompt, compiler_context = (
                        prepare_prompt_compiler_baseline(
                            request, context_path, run_dir
                        )
                    )
                primary_execution = execute_route(
                    primary_route,
                    engine,
                    policy,
                    capabilities,
                    run_dir,
                    request,
                    payload["goal_ledger"],
                    context,
                    resolved_context,
                    orchestration_trace,
                    prompt_compiler_baseline=compiled_prompt,
                    stage_label="primary",
                )
                if primary_execution["status"] == "blocked_by_capability":
                    execution = primary_execution
                else:
                    if secondary_route == "PROMPT":
                        compiled_prompt, compiler_context = (
                            prepare_prompt_compiler_baseline(
                                request,
                                context_path,
                                run_dir,
                                primary_execution,
                            )
                        )
                    secondary_execution = execute_route(
                        secondary_route,
                        engine,
                        policy,
                        capabilities,
                        run_dir,
                        request,
                        payload["goal_ledger"],
                        context,
                        resolved_context,
                        orchestration_trace,
                        primary_execution=primary_execution,
                        prompt_compiler_baseline=(
                            compiled_prompt if secondary_route == "PROMPT" else None
                        ),
                        stage_label="secondary",
                    )
                    execution = merge_executions(
                        primary_route,
                        primary_execution,
                        secondary_route,
                        secondary_execution,
                    )
            else:
                if selected == "PROMPT":
                    compiled_prompt, compiler_context = (
                        prepare_prompt_compiler_baseline(
                            request, context_path, run_dir
                        )
                    )
                execution = execute_route(
                    selected,
                    engine,
                    policy,
                    capabilities,
                    run_dir,
                    request,
                    payload["goal_ledger"],
                    context,
                    resolved_context,
                    orchestration_trace,
                    prompt_compiler_baseline=compiled_prompt,
                )
            payload["execution"] = execution
            if (
                compiled_prompt is not None
                and compiler_context is not None
                and payload["execution"]["status"] != "blocked_by_capability"
            ):
                payload = attach_prompt_compiler_record(
                    payload, compiled_prompt, compiler_context
                )
        except ProblemSolvingError as exc:
            payload = blocked_payload(request, str(exc))

    run_record = {
        "run_id": chosen_run_id,
        "started_at": started_at,
        "finished_at": utc_now().isoformat(),
        "context_file": resolved_context,
        "capabilities": asdict(capabilities),
        "model_policy": public_model_policy(policy),
        "model_plan": selected_model_plan(payload["route"], policy),
        "orchestration_trace": orchestration_trace,
        "engine_trace": engine.trace(),
    }
    payload["run"] = run_record
    route_record = {
        **payload["route"],
        "execution_status": payload["execution"]["status"],
        "capabilities_used": payload["execution"]["capabilities_used"],
        "needed_capability": payload["execution"]["needed_capability"],
        "handoff": payload["execution"]["handoff"],
        "artifacts": payload["execution"]["artifacts"],
        "evidence": payload["execution"]["evidence"],
        "limitations": payload["execution"]["limitations"],
        "run": run_record,
    }
    if "prompt_compiler" in payload:
        route_record["prompt_compiler"] = payload["prompt_compiler"]
    write_json(run_dir / "goal_ledger.json", payload["goal_ledger"])
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
        help="CODE/PROJECT 실행에서 workspace-write를 명시적으로 요청",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="라이브 웹 검색 capability를 끔(테스트 또는 제한 환경용)",
    )
    parser.add_argument(
        "--model-policy",
        type=Path,
        default=DEFAULT_MODEL_POLICY_PATH,
        help="경로별 모델·reasoning·도구 정책 JSON",
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
            model_policy_path=args.model_policy,
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
