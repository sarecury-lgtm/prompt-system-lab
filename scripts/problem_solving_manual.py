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


class ManualBridgeError(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        "phase": stage.get("phase"),
        "route": stage.get("route"),
        "stage_label": stage.get("stage_label"),
        "prompt": prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else "",
        "result_markdown": result_path.read_text(encoding="utf-8") if result_path.is_file() else "",
        "error": state.get("error"),
        "updated_at": state["updated_at"],
    }


class ManualBridge:
    def __init__(self, runs_dir: Path = problem_os.RUNS_DIR, model_policy_path: Path = problem_os.DEFAULT_MODEL_POLICY_PATH):
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

    def set_prompt(self, run_dir: Path, state: dict[str, Any], phase: str, route: str | None, label: str, prompt: str, schema: Path) -> None:
        filename = f"manual-{label}-{(route or 'router').lower()}-request.md"
        (run_dir / filename).write_text(prompt, encoding="utf-8")
        state["stage"] = {
            "phase": phase,
            "route": route,
            "stage_label": label,
            "prompt_path": filename,
            "schema_path": str(schema),
            "prompt_sha256": sha256_text(prompt),
        }
        state["state"] = f"awaiting_{phase}"

    def start(self, request: str, search_enabled: bool = False) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise ManualBridgeError("요청을 입력해 주세요.")
        if len(request) > MAX_REQUEST_CHARS:
            raise ManualBridgeError("요청은 10,000자 이하여야 합니다.")
        if not isinstance(search_enabled, bool):
            raise ManualBridgeError("웹 검색 설정이 올바르지 않습니다.")
        with self.lock:
            run_id = problem_os.make_run_id()
            run_dir = self.run_dir(run_id)
            if run_dir.exists():
                raise ManualBridgeError(f"이미 존재하는 run-id입니다: {run_id}")
            run_dir.mkdir(parents=True)
            (run_dir / "request.txt").write_text(request + "\n", encoding="utf-8")
            policy = problem_os.load_model_policy(self.policy_path)
            now = utc_now()
            state = {
                "version": 1,
                "run_id": run_id,
                "request": request,
                "search_enabled": search_enabled,
                "state": "created",
                "created_at": now,
                "updated_at": now,
                "route_payload": None,
                "primary_execution": None,
                "prompt_compiler": None,
                "stage": None,
                "history": [],
                "error": None,
                "model_policy": problem_os.public_model_policy(policy),
            }
            prompt = problem_os.build_router_prompt(request, "", None, capabilities(search_enabled))
            self.set_prompt(run_dir, state, "router", None, "router", with_schema(prompt, problem_os.ROUTE_SCHEMA_PATH, "router"), problem_os.ROUTE_SCHEMA_PATH)
            self.save(run_dir, state)
            return public_state(state, run_dir)

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

    def prepare_executor(self, run_dir: Path, state: dict[str, Any], route: str, label: str, primary: dict[str, Any] | None = None) -> None:
        baseline = None
        if route == "PROMPT":
            baseline, context = problem_os.prepare_prompt_compiler_baseline(state["request"], None, run_dir, primary)
            state["prompt_compiler"] = {"compiled": baseline, "context_path": str(context)}
        prompt = problem_os.build_execution_prompt(
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
        self.set_prompt(run_dir, state, label, route, label, with_schema(prompt, problem_os.EXECUTION_SCHEMA_PATH, f"executor:{label}:{route}"), problem_os.EXECUTION_SCHEMA_PATH)

    def record(self, run_dir: Path, state: dict[str, Any], raw: str, normalized: str) -> None:
        stage = state["stage"]
        stem = f"manual-{stage['stage_label']}-{(stage.get('route') or 'router').lower()}-output"
        (run_dir / f"{stem}.json").write_text(normalized + "\n", encoding="utf-8")
        (run_dir / f"{stem}.raw.txt").write_text(raw, encoding="utf-8")
        state["history"].append({
            "phase": stage["phase"],
            "route": stage.get("route"),
            "stage_label": stage["stage_label"],
            "prompt_path": stage["prompt_path"],
            "prompt_sha256": stage["prompt_sha256"],
            "response_path": f"{stem}.json",
            "raw_response_path": f"{stem}.raw.txt",
            "response_sha256": sha256_text(normalized),
            "submitted_at": utc_now(),
            "transport": "user_returned_chatgpt_response",
        })

    def finalize(self, run_dir: Path, state: dict[str, Any], execution: dict[str, Any]) -> None:
        execution["capabilities_used"] = list(dict.fromkeys([*execution["capabilities_used"], "manual_transfer:user_returned"]))
        limit = "수동 ChatGPT 브리지는 브라우저 내부 도구 호출을 독립 receipt로 검증하지 못하며 반환 JSON의 구조와 명시 근거만 검증합니다."
        execution["limitations"] = list(dict.fromkeys([*execution["limitations"], limit]))
        route_payload = state["route_payload"]
        payload = {"goal_ledger": route_payload["goal_ledger"], "route": route_payload["route"], "execution": execution}
        compiler = state.get("prompt_compiler")
        if isinstance(compiler, dict):
            payload = problem_os.attach_prompt_compiler_record(payload, compiler["compiled"], Path(compiler["context_path"]))
        chosen = payload["route"]["selected_route"]
        routes = [payload["route"]["primary_route"], payload["route"]["secondary_route"]] if chosen == "HYBRID" else [chosen]
        manual_profile = profile(state["search_enabled"])
        finished = utc_now()
        run = {
            "run_id": state["run_id"],
            "started_at": state["created_at"],
            "finished_at": finished,
            "context_file": None,
            "capabilities": asdict(capabilities(state["search_enabled"])),
            "model_policy": state["model_policy"],
            "model_plan": [
                {"stage": "router", **asdict(manual_profile), "transport": "manual_chatgpt_bridge"},
                *[{"stage": "primary" if i == 0 else "secondary", "route": route, **asdict(manual_profile), "transport": "manual_chatgpt_bridge"} for i, route in enumerate(routes)],
            ],
            "orchestration_trace": [{"phase": item["phase"], "route": item["route"], "stage_label": item["stage_label"], "outcome": "accepted_manual_submission", "response_sha256": item["response_sha256"]} for item in state["history"]],
            "engine_trace": [{"engine": "manual_chatgpt_bridge", "history_file": str(state_path(run_dir))}],
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
            "manual_bridge": {"version": 1, "history_file": "manual-handoff.json", "independent_browser_tool_receipts": False},
        }
        if "prompt_compiler" in payload:
            route_record["prompt_compiler"] = payload["prompt_compiler"]
        write_json(run_dir / "goal_ledger.json", payload["goal_ledger"])
        write_json(run_dir / "route.json", route_record)
        (run_dir / "result.md").write_text(problem_os.result_markdown(payload), encoding="utf-8")
        state.update({"state": "completed", "stage": None, "error": None, "finished_at": finished})
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
            value, normalized = parse_response(response)
            stage = state["stage"]
            try:
                if stage["phase"] == "router":
                    state["route_payload"] = problem_os.validate_route_output(value)
                    self.record(run_dir, state, response, normalized)
                    write_json(run_dir / "goal_ledger.json", state["route_payload"]["goal_ledger"])
                    selected = state["route_payload"]["route"]["selected_route"]
                    route = state["route_payload"]["route"]["primary_route"] if selected == "HYBRID" else selected
                    self.prepare_executor(run_dir, state, route, "primary")
                else:
                    route = stage["route"]
                    execution = problem_os.validate_execution_output(value, route, profile(state["search_enabled"]), capabilities(state["search_enabled"]))
                    if route == "REUSE" and execution["status"] == "completed":
                        raise ManualBridgeError("수동 브리지는 로컬 자산을 직접 확인할 수 없어 REUSE 완료를 검증할 수 없습니다. handoff 또는 blocked_by_capability로 반환하세요.")
                    self.record(run_dir, state, response, normalized)
                    selected = state["route_payload"]["route"]["selected_route"]
                    if selected == "HYBRID" and stage["stage_label"] == "primary":
                        state["primary_execution"] = execution
                        if execution["status"] == "blocked_by_capability":
                            self.finalize(run_dir, state, execution)
                        else:
                            self.prepare_executor(run_dir, state, state["route_payload"]["route"]["secondary_route"], "secondary", execution)
                    elif selected == "HYBRID":
                        route_data = state["route_payload"]["route"]
                        self.finalize(run_dir, state, problem_os.merge_executions(route_data["primary_route"], state["primary_execution"], route_data["secondary_route"], execution))
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
