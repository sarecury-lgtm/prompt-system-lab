#!/usr/bin/env python3
"""Schema-validated manual ChatGPT handoff runtime for PSOS."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as problem_os

MAX_REQUEST_CHARS = 10_000
MAX_RESPONSE_CHARS = 1_000_000
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
RESEARCH_MODES = {"none", "standard", "deep"}


class ManualBridgeError(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_research_mode(
    search_enabled: bool = False,
    research_mode: str | None = None,
) -> str:
    if research_mode is None:
        if not isinstance(search_enabled, bool):
            raise ManualBridgeError("웹 검색 설정이 올바르지 않습니다.")
        return "standard" if search_enabled else "none"
    if not isinstance(research_mode, str):
        raise ManualBridgeError("리서치 방식이 올바르지 않습니다.")
    mode = research_mode.strip().lower()
    if mode not in RESEARCH_MODES:
        raise ManualBridgeError("리서치 방식은 none, standard, deep 중 하나여야 합니다.")
    return mode


def capabilities(search: bool) -> problem_os.EngineCapabilities:
    return problem_os.EngineCapabilities(
        ai_reasoning=True,
        web_search=search,
        workspace_read=False,
        workspace_write=False,
        detail="Manual ChatGPT transfer; no direct local read or write capability.",
    )


def profile(search: bool) -> problem_os.ModelProfile:
    return problem_os.ModelProfile("chatgpt-manual", "none", search, "read-only")


def with_schema(prompt: str, schema_path: Path, phase: str) -> str:
    try:
        schema = schema_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ManualBridgeError(f"출력 스키마를 읽을 수 없습니다: {exc}") from exc
    return f"""{prompt.rstrip()}

[수동 브리지 신뢰 규칙]
- 로컬 저장소를 직접 읽거나 수정했다고 주장하지 않는다.
- 제공받지 않은 로컬 파일 내용은 확인한 사실로 쓰지 않는다.
- 실제로 웹 검색하지 않았다면 web evidence를 만들지 않는다.
- 파일 변경 결과는 created/modified가 아니라 proposed 또는 generated_in_result로 기록한다.

[반환 계약: {phase}]
아래 JSON Schema를 만족하는 JSON 객체 하나만 반환한다. 코드 펜스나 설명문을 붙이지 않는다.

{schema}
"""


def deep_research_report_prompt(base_prompt: str) -> str:
    return f"""{base_prompt.rstrip()}

[현재 단계: 심층 리서치 보고서 작성]
이 단계에서는 execution JSON을 만들지 않는다.
ChatGPT의 Deep research 기능을 켠 뒤 실제 조사를 수행한다.
조사 계획을 먼저 점검하고, 사용자의 고정 조건이 빠졌다면 계획에서 바로잡는다.
공식·1차 출처와 현재 판매 페이지를 우선하며, 확인 사실·판매자 주장·추론·미확인을 구분한다.
출처 링크와 근거를 포함한 완성된 Markdown 보고서만 반환한다.
보고서에는 최종 추천, 직접 비교, 제외 이유, 실패 위험, 남은 한계를 포함한다.
JSON, 코드 펜스, '다음 단계에서 하겠다'는 식의 미완성 답변은 반환하지 않는다.
"""


def deep_research_normalizer_prompt(
    base_prompt: str,
    report: str,
    schema_path: Path,
    phase: str,
) -> str:
    try:
        schema = schema_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ManualBridgeError(f"출력 스키마를 읽을 수 없습니다: {exc}") from exc
    return f"""당신은 Personal Problem-Solving OS의 심층 리서치 결과 정규화기다.

아래 심층 리서치 보고서를 새로 조사하지 말고 PSOS execution 형식으로 정규화한다.
보고서에 없는 사실을 추가하거나 출처를 꾸미지 않는다.
보고서의 핵심 결과는 result_markdown에 읽기 좋은 Markdown으로 보존한다.
실제 보고서에서 확인 가능한 출처만 evidence에 옮긴다.
심층 리서치 보고서 자체는 이미 작성됐으므로 조사 계획이나 작업 예고를 결과로 쓰지 않는다.

[원래 실행기 지시문]
{base_prompt.rstrip()}

[심층 리서치 보고서]
{report.strip()}

[수동 브리지 신뢰 규칙]
- 로컬 저장소를 직접 읽거나 수정했다고 주장하지 않는다.
- 제공받지 않은 로컬 파일 내용은 확인한 사실로 쓰지 않는다.
- 보고서에 없는 web evidence를 만들지 않는다.
- 파일 변경 결과는 created/modified가 아니라 proposed 또는 generated_in_result로 기록한다.

[반환 계약: {phase}]
아래 JSON Schema를 만족하는 JSON 객체 하나만 반환한다. 코드 펜스나 설명문을 붙이지 않는다.

{schema}
"""


def parse_response(raw: str) -> tuple[dict[str, Any], str]:
    text = raw.strip()
    if not text:
        raise ManualBridgeError("ChatGPT 응답이 비어 있습니다.")
    if len(text) > MAX_RESPONSE_CHARS:
        raise ManualBridgeError("ChatGPT 응답이 허용 크기를 초과했습니다.")
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    candidates = [fenced.group(1).strip(), text] if fenced else [text]
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            if start < 0:
                continue
            try:
                value, end = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if candidate[start + end :].strip().strip("`"):
                continue
        if not isinstance(value, dict):
            raise ManualBridgeError("최상위 응답은 JSON 객체여야 합니다.")
        return value, json.dumps(value, ensure_ascii=False, indent=2)
    raise ManualBridgeError("응답에서 유효한 JSON 객체를 찾지 못했습니다.")


def validate_report(raw: str) -> str:
    report = raw.strip()
    if not report:
        raise ManualBridgeError("심층 리서치 보고서가 비어 있습니다.")
    if len(report) > MAX_RESPONSE_CHARS:
        raise ManualBridgeError("심층 리서치 보고서가 허용 크기를 초과했습니다.")
    if len(report) < 80:
        raise ManualBridgeError(
            "심층 리서치 보고서가 너무 짧습니다. 완성된 보고서 전체를 붙여넣어 주세요."
        )
    return report


def state_path(run_dir: Path) -> Path:
    return run_dir / "manual-handoff.json"


def read_state(run_dir: Path) -> dict[str, Any]:
    try:
        value = json.loads(state_path(run_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualBridgeError(f"수동 인계 상태를 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ManualBridgeError("지원하지 않는 수동 인계 상태입니다.")
    return value


def public_state(state: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    stage = state.get("stage") or {}
    prompt_path = run_dir / stage.get("prompt_path", "")
    result_path = run_dir / "result.md"
    return {
        "run_id": state["run_id"],
        "state": state["state"],
        "request": state["request"],
        "search_enabled": state["search_enabled"],
        "research_mode": state.get(
            "research_mode",
            "standard" if state.get("search_enabled") else "none",
        ),
        "parent_run_id": state.get("parent_run_id"),
        "revision_feedback": state.get("revision_feedback"),
        "phase": stage.get("phase"),
        "route": stage.get("route"),
        "stage_label": stage.get("stage_label"),
        "response_kind": stage.get("response_kind", "json"),
        "prompt": (
            prompt_path.read_text(encoding="utf-8")
            if prompt_path.is_file()
            else ""
        ),
        "result_markdown": (
            result_path.read_text(encoding="utf-8")
            if result_path.is_file()
            else ""
        ),
        "error": state.get("error"),
        "updated_at": state["updated_at"],
    }


class ManualBridge:
    def __init__(
        self,
        runs_dir: Path = problem_os.RUNS_DIR,
        model_policy_path: Path = problem_os.DEFAULT_MODEL_POLICY_PATH,
    ):
        self.runs_dir = runs_dir.expanduser().resolve()
        self.policy_path = model_policy_path.expanduser().resolve()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def run_dir(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
            raise ManualBridgeError("올바르지 않은 run-id입니다.")
        path = (self.runs_dir / run_id).resolve()
        try:
            path.relative_to(self.runs_dir)
        except ValueError as exc:
            raise ManualBridgeError("run-id가 runs 디렉터리를 벗어납니다.") from exc
        return path

    def save(self, run_dir: Path, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json(state_path(run_dir), state)

    def set_prompt(
        self,
        run_dir: Path,
        state: dict[str, Any],
        phase: str,
        route: str | None,
        label: str,
        prompt: str,
        schema: Path | None,
        *,
        response_kind: str = "json",
    ) -> None:
        filename = f"manual-{phase}-{(route or 'router').lower()}-request.md"
        (run_dir / filename).write_text(prompt, encoding="utf-8")
        state["stage"] = {
            "phase": phase,
            "route": route,
            "stage_label": label,
            "prompt_path": filename,
            "schema_path": str(schema) if schema is not None else None,
            "prompt_sha256": sha256_text(prompt),
            "response_kind": response_kind,
        }
        state["state"] = f"awaiting_{phase}"

    def _create_run(
        self,
        request: str,
        research_mode: str,
        *,
        router_context: str = "",
        parent_run_id: str | None = None,
        revision_feedback: str | None = None,
    ) -> dict[str, Any]:
        run_id = problem_os.make_run_id()
        run_dir = self.run_dir(run_id)
        if run_dir.exists():
            raise ManualBridgeError(f"이미 존재하는 run-id입니다: {run_id}")
        run_dir.mkdir(parents=True)
        (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
        policy = problem_os.load_model_policy(self.policy_path)
        now = utc_now()
        search_enabled = research_mode != "none"
        context_path: str | None = None
        if router_context:
            path = run_dir / "revision-context.md"
            path.write_text(router_context, encoding="utf-8")
            context_path = str(path)
        state = {
            "version": 1,
            "run_id": run_id,
            "request": request,
            "original_request": request,
            "search_enabled": search_enabled,
            "research_mode": research_mode,
            "parent_run_id": parent_run_id,
            "revision_feedback": revision_feedback,
            "state": "created",
            "created_at": now,
            "updated_at": now,
            "route_payload": None,
            "primary_execution": None,
            "prompt_compiler": None,
            "deep_research_reports": {},
            "stage": None,
            "history": [],
            "error": None,
            "model_policy": problem_os.public_model_policy(policy),
        }
        if parent_run_id is not None:
            write_json(
                run_dir / "revision.json",
                {
                    "parent_run_id": parent_run_id,
                    "feedback": revision_feedback,
                    "research_mode": research_mode,
                    "created_at": now,
                },
            )
        prompt = problem_os.build_router_prompt(
            request,
            router_context,
            context_path,
            capabilities(search_enabled),
        )
        self.set_prompt(
            run_dir,
            state,
            "router",
            None,
            "router",
            with_schema(prompt, problem_os.ROUTE_SCHEMA_PATH, "router"),
            problem_os.ROUTE_SCHEMA_PATH,
        )
        self.save(run_dir, state)
        return public_state(state, run_dir)

    def start(
        self,
        request: str,
        search_enabled: bool = False,
        research_mode: str | None = None,
    ) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise ManualBridgeError("요청을 입력해 주세요.")
        if len(request) > MAX_REQUEST_CHARS:
            raise ManualBridgeError("요청은 10,000자 이하여야 합니다.")
        mode = normalize_research_mode(search_enabled, research_mode)
        with self.lock:
            return self._create_run(request, mode)

    def revise(
        self,
        parent_run_id: str,
        feedback: str,
        research_mode: str | None = None,
    ) -> dict[str, Any]:
        feedback = feedback.strip()
        if not feedback:
            raise ManualBridgeError("무엇이 아쉬웠는지 또는 어떻게 바꿀지 적어 주세요.")
        if len(feedback) > MAX_REQUEST_CHARS:
            raise ManualBridgeError("수정 요청은 10,000자 이하여야 합니다.")
        with self.lock:
            parent_dir = self.run_dir(parent_run_id)
            if not parent_dir.is_dir():
                raise ManualBridgeError("수정할 원본 run을 찾을 수 없습니다.")
            parent = read_state(parent_dir)
            if parent.get("state") != "completed":
                raise ManualBridgeError("완료된 결과만 수정할 수 있습니다.")
            inherited_mode = parent.get(
                "research_mode",
                "standard" if parent.get("search_enabled") else "none",
            )
            mode = normalize_research_mode(
                parent.get("search_enabled", False),
                research_mode if research_mode is not None else inherited_mode,
            )
            request = parent.get("original_request") or parent["request"]
            try:
                ledger = (parent_dir / "goal_ledger.json").read_text(encoding="utf-8")
            except OSError:
                ledger = "(직전 Goal Ledger를 읽을 수 없음)"
            try:
                result = (parent_dir / "result.md").read_text(encoding="utf-8")
            except OSError:
                result = "(직전 결과를 읽을 수 없음)"
            router_context = f"""# 완료 결과 수정

이 실행은 기존 결과를 덮어쓰지 않는 revision run이다.

## 원본 run
{parent_run_id}

## 직전 Goal Ledger
{ledger[:60_000]}

## 직전 결과
{result[:100_000]}

## 사용자의 정정 및 불만
{feedback}

## 수정 원칙
- 원래 상위 목적은 보존한다.
- 사용자의 이번 정정을 직전 해석보다 우선한다.
- 직전 결과를 그대로 반복하지 않는다.
- 무엇이 바뀌었는지 Goal Ledger의 현재 목표, 고정 조건, 불확실성에 반영한다.
- 최신 정보가 다시 필요하면 필요한 범위만 재조사한다.
"""
            return self._create_run(
                request,
                mode,
                router_context=router_context,
                parent_run_id=parent_run_id,
                revision_feedback=feedback,
            )

    def get(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            run_dir = self.run_dir(run_id)
            if not run_dir.is_dir():
                raise ManualBridgeError("해당 run을 찾을 수 없습니다.")
            return public_state(read_state(run_dir), run_dir)

    def active(self) -> dict[str, Any] | None:
        with self.lock:
            pending = []
            for run_dir in self.runs_dir.iterdir():
                if not state_path(run_dir).is_file():
                    continue
                try:
                    state = read_state(run_dir)
                except ManualBridgeError:
                    continue
                if state.get("state", "").startswith("awaiting_"):
                    pending.append((state["updated_at"], run_dir, state))
            if not pending:
                return None
            _, run_dir, state = max(pending, key=lambda item: item[0])
            return public_state(state, run_dir)

    def execution_prompt(
        self,
        run_dir: Path,
        state: dict[str, Any],
        route: str,
        primary: dict[str, Any] | None = None,
    ) -> str:
        baseline = None
        if route == "PROMPT":
            baseline, context = problem_os.prepare_prompt_compiler_baseline(
                state["request"],
                None,
                run_dir,
                primary,
            )
            state["prompt_compiler"] = {
                "compiled": baseline,
                "context_path": str(context),
            }
        return problem_os.build_execution_prompt(
            route,
            state["request"],
            state["route_payload"]["goal_ledger"],
            "",
            None,
            capabilities(state["search_enabled"]),
            profile(state["search_enabled"]),
            primary,
            baseline,
        )

    def prepare_executor(
        self,
        run_dir: Path,
        state: dict[str, Any],
        route: str,
        label: str,
        primary: dict[str, Any] | None = None,
    ) -> None:
        base_prompt = self.execution_prompt(run_dir, state, route, primary)
        if route == "RESEARCH" and state.get("research_mode") == "deep":
            self.set_prompt(
                run_dir,
                state,
                f"{label}_deep_report",
                route,
                label,
                deep_research_report_prompt(base_prompt),
                None,
                response_kind="markdown",
            )
            return
        self.set_prompt(
            run_dir,
            state,
            label,
            route,
            label,
            with_schema(
                base_prompt,
                problem_os.EXECUTION_SCHEMA_PATH,
                f"executor:{label}:{route}",
            ),
            problem_os.EXECUTION_SCHEMA_PATH,
        )

    def prepare_deep_normalizer(
        self,
        run_dir: Path,
        state: dict[str, Any],
        route: str,
        label: str,
        report: str,
        primary: dict[str, Any] | None = None,
    ) -> None:
        base_prompt = self.execution_prompt(run_dir, state, route, primary)
        prompt = deep_research_normalizer_prompt(
            base_prompt,
            report,
            problem_os.EXECUTION_SCHEMA_PATH,
            f"executor:{label}:{route}:deep-normalize",
        )
        self.set_prompt(
            run_dir,
            state,
            label,
            route,
            label,
            prompt,
            problem_os.EXECUTION_SCHEMA_PATH,
        )

    def record(
        self,
        run_dir: Path,
        state: dict[str, Any],
        raw: str,
        normalized: str,
    ) -> None:
        stage = state["stage"]
        kind = stage.get("response_kind", "json")
        extension = "md" if kind == "markdown" else "json"
        stem = (
            f"manual-{stage['phase']}-"
            f"{(stage.get('route') or 'router').lower()}-output"
        )
        (run_dir / f"{stem}.{extension}").write_text(
            normalized + ("\n" if not normalized.endswith("\n") else ""),
            encoding="utf-8",
        )
        (run_dir / f"{stem}.raw.txt").write_text(raw, encoding="utf-8")
        state["history"].append(
            {
                "phase": stage["phase"],
                "route": stage.get("route"),
                "stage_label": stage["stage_label"],
                "response_kind": kind,
                "prompt_path": stage["prompt_path"],
                "prompt_sha256": stage["prompt_sha256"],
                "response_path": f"{stem}.{extension}",
                "raw_response_path": f"{stem}.raw.txt",
                "response_sha256": sha256_text(normalized),
                "submitted_at": utc_now(),
                "transport": "user_returned_chatgpt_response",
            }
        )

    def model_plan(
        self,
        state: dict[str, Any],
        routes: list[str],
    ) -> list[dict[str, Any]]:
        manual_profile = profile(state["search_enabled"])
        plan: list[dict[str, Any]] = [
            {
                "stage": "router",
                **asdict(manual_profile),
                "transport": "manual_chatgpt_bridge",
            }
        ]
        for index, route in enumerate(routes):
            label = "primary" if index == 0 else "secondary"
            if route == "RESEARCH" and state.get("research_mode") == "deep":
                plan.append(
                    {
                        "stage": f"{label}_deep_research",
                        "route": route,
                        "model": "chatgpt-deep-research",
                        "reasoning_effort": "managed",
                        "web_search": True,
                        "sandbox": "read-only",
                        "transport": "manual_chatgpt_bridge",
                    }
                )
                plan.append(
                    {
                        "stage": f"{label}_normalize",
                        "route": route,
                        **asdict(manual_profile),
                        "transport": "manual_chatgpt_bridge",
                    }
                )
            else:
                plan.append(
                    {
                        "stage": label,
                        "route": route,
                        **asdict(manual_profile),
                        "transport": "manual_chatgpt_bridge",
                    }
                )
        return plan

    def finalize(
        self,
        run_dir: Path,
        state: dict[str, Any],
        execution: dict[str, Any],
    ) -> None:
        execution["capabilities_used"] = list(
            dict.fromkeys(
                [
                    *execution["capabilities_used"],
                    "manual_transfer:user_returned",
                ]
            )
        )
        limit = (
            "수동 ChatGPT 브리지는 브라우저 내부 도구 호출을 독립 receipt로 "
            "검증하지 못하며 반환 JSON의 구조와 명시 근거만 검증합니다."
        )
        execution["limitations"] = list(
            dict.fromkeys([*execution["limitations"], limit])
        )
        route_payload = state["route_payload"]
        payload = {
            "goal_ledger": route_payload["goal_ledger"],
            "route": route_payload["route"],
            "execution": execution,
        }
        compiler = state.get("prompt_compiler")
        if isinstance(compiler, dict):
            payload = problem_os.attach_prompt_compiler_record(
                payload,
                compiler["compiled"],
                Path(compiler["context_path"]),
            )
        chosen = payload["route"]["selected_route"]
        routes = (
            [
                payload["route"]["primary_route"],
                payload["route"]["secondary_route"],
            ]
            if chosen == "HYBRID"
            else [chosen]
        )
        finished = utc_now()
        run = {
            "run_id": state["run_id"],
            "parent_run_id": state.get("parent_run_id"),
            "revision_feedback": state.get("revision_feedback"),
            "research_mode": state.get("research_mode", "none"),
            "started_at": state["created_at"],
            "finished_at": finished,
            "context_file": (
                str(run_dir / "revision-context.md")
                if (run_dir / "revision-context.md").is_file()
                else None
            ),
            "capabilities": asdict(capabilities(state["search_enabled"])),
            "model_policy": state["model_policy"],
            "model_plan": self.model_plan(state, routes),
            "orchestration_trace": [
                {
                    "phase": item["phase"],
                    "route": item["route"],
                    "stage_label": item["stage_label"],
                    "response_kind": item.get("response_kind", "json"),
                    "outcome": "accepted_manual_submission",
                    "response_sha256": item["response_sha256"],
                }
                for item in state["history"]
            ],
            "engine_trace": [
                {
                    "engine": "manual_chatgpt_bridge",
                    "history_file": str(state_path(run_dir)),
                    "deep_research_reports": state.get(
                        "deep_research_reports",
                        {},
                    ),
                }
            ],
        }
        payload["run"] = run
        route_record = {
            **payload["route"],
            "execution_status": execution["status"],
            "capabilities_used": execution["capabilities_used"],
            "needed_capability": execution["needed_capability"],
            "handoff": execution["handoff"],
            "artifacts": execution["artifacts"],
            "evidence": execution["evidence"],
            "limitations": execution["limitations"],
            "run": run,
            "manual_bridge": {
                "version": 1,
                "history_file": "manual-handoff.json",
                "independent_browser_tool_receipts": False,
                "research_mode": state.get("research_mode", "none"),
                "parent_run_id": state.get("parent_run_id"),
                "deep_research_reports": state.get(
                    "deep_research_reports",
                    {},
                ),
            },
        }
        if "prompt_compiler" in payload:
            route_record["prompt_compiler"] = payload["prompt_compiler"]
        write_json(run_dir / "goal_ledger.json", payload["goal_ledger"])
        write_json(run_dir / "route.json", route_record)
        (run_dir / "result.md").write_text(
            problem_os.result_markdown(payload),
            encoding="utf-8",
        )
        state.update(
            {
                "state": "completed",
                "stage": None,
                "error": None,
                "finished_at": finished,
            }
        )
        self.save(run_dir, state)

    def submit(self, run_id: str, response: str) -> dict[str, Any]:
        with self.lock:
            run_dir = self.run_dir(run_id)
            if not run_dir.is_dir():
                raise ManualBridgeError("해당 run을 찾을 수 없습니다.")
            state = read_state(run_dir)
            if state["state"] == "completed":
                return public_state(state, run_dir)
            if not state["state"].startswith("awaiting_"):
                raise ManualBridgeError("현재 응답을 받을 단계가 아닙니다.")
            stage = state["stage"]
            try:
                if stage["phase"] == "router":
                    value, normalized = parse_response(response)
                    state["route_payload"] = problem_os.validate_route_output(value)
                    self.record(run_dir, state, response, normalized)
                    write_json(
                        run_dir / "goal_ledger.json",
                        state["route_payload"]["goal_ledger"],
                    )
                    selected = state["route_payload"]["route"]["selected_route"]
                    route = (
                        state["route_payload"]["route"]["primary_route"]
                        if selected == "HYBRID"
                        else selected
                    )
                    self.prepare_executor(run_dir, state, route, "primary")
                elif stage.get("response_kind") == "markdown":
                    report = validate_report(response)
                    self.record(run_dir, state, response, report)
                    label = stage["stage_label"]
                    report_path = (
                        f"manual-{stage['phase']}-"
                        f"{stage['route'].lower()}-output.md"
                    )
                    state.setdefault("deep_research_reports", {})[
                        label
                    ] = report_path
                    primary = (
                        state.get("primary_execution")
                        if label == "secondary"
                        else None
                    )
                    self.prepare_deep_normalizer(
                        run_dir,
                        state,
                        stage["route"],
                        label,
                        report,
                        primary,
                    )
                else:
                    value, normalized = parse_response(response)
                    route = stage["route"]
                    execution = problem_os.validate_execution_output(
                        value,
                        route,
                        profile(state["search_enabled"]),
                        capabilities(state["search_enabled"]),
                    )
                    if route == "REUSE" and execution["status"] == "completed":
                        raise ManualBridgeError(
                            "수동 브리지는 로컬 자산을 직접 확인할 수 없어 "
                            "REUSE 완료를 검증할 수 없습니다. handoff 또는 "
                            "blocked_by_capability로 반환하세요."
                        )
                    self.record(run_dir, state, response, normalized)
                    selected = state["route_payload"]["route"]["selected_route"]
                    if (
                        selected == "HYBRID"
                        and stage["stage_label"] == "primary"
                    ):
                        state["primary_execution"] = execution
                        if execution["status"] == "blocked_by_capability":
                            self.finalize(run_dir, state, execution)
                        else:
                            self.prepare_executor(
                                run_dir,
                                state,
                                state["route_payload"]["route"][
                                    "secondary_route"
                                ],
                                "secondary",
                                execution,
                            )
                    elif selected == "HYBRID":
                        route_data = state["route_payload"]["route"]
                        self.finalize(
                            run_dir,
                            state,
                            problem_os.merge_executions(
                                route_data["primary_route"],
                                state["primary_execution"],
                                route_data["secondary_route"],
                                execution,
                            ),
                        )
                    else:
                        self.finalize(run_dir, state, execution)
            except (problem_os.ProblemSolvingError, ManualBridgeError) as exc:
                state["error"] = str(exc)
                self.save(run_dir, state)
                raise ManualBridgeError(str(exc)) from exc
            if state["state"] != "completed":
                state["error"] = None
                self.save(run_dir, state)
            return public_state(state, run_dir)
