#!/usr/bin/env python3
"""Probe source ecosystems cheaply before committing to a research path."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_os as OS


# [CLAUDE_CONTEXT]
# Purpose: Test whether a tiny source-ecosystem probe can choose a faster research
# path before the main PSOS spends tokens collecting or evaluating candidates.
# Key decisions: one low-reasoning web call only; the model reports observations,
# while deterministic code scores and selects the path. This is not wired into UI.

ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "source-scout-experiments"
SCHEMA_PATH = ROOT / "schemas" / "problem-solving-source-scout.schema.json"
MAX_REQUEST_CHARS = 10_000
SOURCE_FAMILIES = {"COMMUNITY", "MARKETPLACE", "PRIMARY", "REUSE_INDEX", "BROAD_WEB"}
STRATEGIES = {
    "COMMUNITY_REUSE",
    "COMMUNITY_THEN_VERIFY",
    "MARKET_SCAN",
    "PRIMARY_SOURCE",
    "REUSE_EXISTING",
    "BROAD_RESEARCH",
    "MULTI_SOURCE_RESEARCH",
    "NO_EXTERNAL_RESEARCH",
}

SPECIFICITY_SCORE = {"none": 0, "vague": 1, "concrete": 3}
RECENCY_SCORE = {"stale": 0, "unknown": 1, "current": 2}
ACTIONABILITY_SCORE = {"none": 0, "lead": 2, "decision_ready": 4}
ACCESS_SCORE = {"open": 0, "partial": -1, "blocked": -4}


class SourceScoutError(ValueError):
    """Raised when a source scout result violates the bounded contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceScoutError(f"{label}이 비어 있습니다.")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise SourceScoutError(f"{label}이 문자열 배열이 아닙니다.")
    return [item.strip() for item in value]


def validate_probe(payload: Any, *, max_searches: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"source_scout"}:
        raise SourceScoutError("source_scout 최상위 형식이 올바르지 않습니다.")
    value = payload["source_scout"]
    fields = {
        "request_summary",
        "external_research_needed",
        "searches_used",
        "probes",
        "scouting_limitations",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise SourceScoutError("source_scout 필드가 올바르지 않습니다.")
    _text(value["request_summary"], "request_summary")
    if not isinstance(value["external_research_needed"], bool):
        raise SourceScoutError("external_research_needed는 boolean이어야 합니다.")
    searches_used = value["searches_used"]
    if not isinstance(searches_used, int) or isinstance(searches_used, bool):
        raise SourceScoutError("searches_used는 정수여야 합니다.")
    if not 0 <= searches_used <= max_searches:
        raise SourceScoutError(f"정찰 검색은 최대 {max_searches}회입니다.")
    probes = value["probes"]
    if not isinstance(probes, list):
        raise SourceScoutError("probes가 배열이 아닙니다.")
    if value["external_research_needed"] and not 2 <= len(probes) <= 4:
        raise SourceScoutError("외부 정찰은 서로 다른 정보원 2~4개를 비교해야 합니다.")
    if not value["external_research_needed"] and probes:
        raise SourceScoutError("외부 조사가 불필요하면 probes는 비어 있어야 합니다.")

    query_count = 0
    validated_probes: list[dict[str, Any]] = []
    expected = {
        "family",
        "queries",
        "concrete_leads",
        "repeated_specificity",
        "recency",
        "actionability",
        "access",
        "verification_need",
        "signal_summary",
    }
    for probe in probes:
        if not isinstance(probe, dict) or set(probe) != expected:
            raise SourceScoutError("probe 항목 형식이 올바르지 않습니다.")
        family = probe["family"]
        if family not in SOURCE_FAMILIES:
            raise SourceScoutError("정보원 family가 올바르지 않습니다.")
        queries = _string_list(probe["queries"], f"{family}.queries")
        if len(queries) > 2:
            raise SourceScoutError("정보원 묶음별 검색어는 최대 2개입니다.")
        query_count += len(queries)
        leads = probe["concrete_leads"]
        if not isinstance(leads, list) or len(leads) > 3:
            raise SourceScoutError("구체적인 단서는 정보원별 최대 3개입니다.")
        for lead in leads:
            if not isinstance(lead, dict) or set(lead) != {"name", "url", "why_actionable"}:
                raise SourceScoutError("concrete_lead 형식이 올바르지 않습니다.")
            for key in ("name", "url", "why_actionable"):
                _text(lead[key], f"lead.{key}")
        if probe["repeated_specificity"] not in SPECIFICITY_SCORE:
            raise SourceScoutError("repeated_specificity 값이 올바르지 않습니다.")
        if probe["recency"] not in RECENCY_SCORE:
            raise SourceScoutError("recency 값이 올바르지 않습니다.")
        if probe["actionability"] not in ACTIONABILITY_SCORE:
            raise SourceScoutError("actionability 값이 올바르지 않습니다.")
        if probe["access"] not in ACCESS_SCORE:
            raise SourceScoutError("access 값이 올바르지 않습니다.")
        if probe["verification_need"] not in {"none", "current_state", "primary_check"}:
            raise SourceScoutError("verification_need 값이 올바르지 않습니다.")
        _text(probe["signal_summary"], f"{family}.signal_summary")
        validated_probes.append(probe)
    if query_count != searches_used:
        raise SourceScoutError("searches_used와 기록된 검색어 수가 일치하지 않습니다.")

    # A single search can surface a second ecosystem, and models may split sites
    # such as GitHub and Product Hunt into separate records of the same family.
    # Preserve that evidence but collapse it before deterministic scoring.
    merged: dict[str, dict[str, Any]] = {}
    verification_rank = {"none": 0, "primary_check": 1, "current_state": 2}
    for probe in validated_probes:
        family = probe["family"]
        if family not in merged:
            merged[family] = {
                **probe,
                "queries": list(probe["queries"]),
                "concrete_leads": list(probe["concrete_leads"]),
                "signal_summary": probe["signal_summary"],
            }
            continue
        target = merged[family]
        target["queries"].extend(probe["queries"])
        known_urls = {lead["url"] for lead in target["concrete_leads"]}
        for lead in probe["concrete_leads"]:
            if lead["url"] not in known_urls and len(target["concrete_leads"]) < 3:
                target["concrete_leads"].append(lead)
                known_urls.add(lead["url"])
        target["repeated_specificity"] = max(
            (target["repeated_specificity"], probe["repeated_specificity"]),
            key=SPECIFICITY_SCORE.__getitem__,
        )
        target["recency"] = max(
            (target["recency"], probe["recency"]),
            key=RECENCY_SCORE.__getitem__,
        )
        target["actionability"] = max(
            (target["actionability"], probe["actionability"]),
            key=ACTIONABILITY_SCORE.__getitem__,
        )
        target["access"] = max(
            (target["access"], probe["access"]),
            key=ACCESS_SCORE.__getitem__,
        )
        target["verification_need"] = max(
            (target["verification_need"], probe["verification_need"]),
            key=verification_rank.__getitem__,
        )
        if probe["signal_summary"] not in target["signal_summary"]:
            target["signal_summary"] += " " + probe["signal_summary"]
    value["probes"] = list(merged.values())
    if value["external_research_needed"] and not 2 <= len(value["probes"]) <= 4:
        raise SourceScoutError("병합 후 서로 다른 정보원 family가 2~4개여야 합니다.")
    value["scouting_limitations"] = _string_list(
        value["scouting_limitations"], "scouting_limitations"
    )
    return value


def probe_score(probe: Mapping[str, Any]) -> int:
    return (
        SPECIFICITY_SCORE[probe["repeated_specificity"]]
        + RECENCY_SCORE[probe["recency"]]
        + ACTIONABILITY_SCORE[probe["actionability"]]
        + ACCESS_SCORE[probe["access"]]
        + min(len(probe["concrete_leads"]), 2)
        + (1 if probe["verification_need"] == "none" else 0)
    )


def _best_secondary(
    primary: Mapping[str, Any],
    probes: list[Mapping[str, Any]],
) -> str | None:
    need = primary["verification_need"]
    if need == "none":
        return None
    preferred = "MARKETPLACE" if need == "current_state" else "PRIMARY"
    usable = [
        probe
        for probe in probes
        if probe["family"] != primary["family"] and probe["access"] != "blocked"
    ]
    preferred_probe = next((probe for probe in usable if probe["family"] == preferred), None)
    if preferred_probe is not None:
        return str(preferred_probe["family"])
    if not usable:
        return None
    return str(max(usable, key=probe_score)["family"])


def select_strategy(scout: Mapping[str, Any]) -> dict[str, Any]:
    if not scout["external_research_needed"]:
        return {
            "strategy": "NO_EXTERNAL_RESEARCH",
            "primary_source_family": None,
            "secondary_source_family": None,
            "scores": {},
            "selection_reason": "외부 정보가 결과를 바꾸지 않는 요청으로 정찰되었습니다.",
            "next_action": "웹 조사를 생략하고 요청 자체와 제공 자료로 해결합니다.",
        }
    probes = scout["probes"]
    scores = {probe["family"]: probe_score(probe) for probe in probes}
    primary = max(probes, key=lambda probe: scores[probe["family"]])
    family = primary["family"]
    top_score = scores[family]
    secondary = _best_secondary(primary, probes)

    if top_score < 5:
        strategy = "MULTI_SOURCE_RESEARCH"
        secondary = None
        next_action = "뚜렷한 정보원 승자가 없으므로 작은 다중 출처 조사부터 수행합니다."
    elif family == "COMMUNITY":
        if primary["verification_need"] == "none":
            strategy = "COMMUNITY_REUSE"
            next_action = "반복되는 구체적 경험과 반례를 재사용해 바로 후보를 압축합니다."
        else:
            strategy = "COMMUNITY_THEN_VERIFY"
            next_action = "커뮤니티에서 후보를 얻고 필요한 현재 상태만 보조 출처에서 검증합니다."
    elif family == "MARKETPLACE":
        strategy = "MARKET_SCAN"
        next_action = "판매 중인 옵션·가격·중량을 구조화한 뒤 가격 이상치와 후보를 비교합니다."
    elif family == "PRIMARY":
        strategy = "PRIMARY_SOURCE"
        next_action = "공식 원문이나 1차 자료를 기준으로 필요한 사실만 확인합니다."
    elif family == "REUSE_INDEX":
        strategy = "REUSE_EXISTING"
        next_action = "이미 존재하는 제품·프로젝트·데이터를 먼저 재사용 가능성 기준으로 검토합니다."
    else:
        strategy = "BROAD_RESEARCH"
        next_action = "특정 정보원에 답이 압축되지 않아 일반 웹에서 범위를 넓힌 뒤 다시 좁힙니다."
    if strategy not in STRATEGIES:
        raise AssertionError("unknown source strategy")
    return {
        "strategy": strategy,
        "primary_source_family": family,
        "secondary_source_family": secondary,
        "scores": scores,
        "selection_reason": (
            f"{family}가 정보 밀도 점수 {top_score}로 가장 높았습니다. "
            f"{primary['signal_summary']}"
        ),
        "next_action": next_action,
    }


def scout_prompt(request: str, *, context: str, max_searches: int) -> str:
    return f"""본격 조사나 최종 답변을 하지 말고, 이 요청의 답이 가장 압축되어 있는 정보원만 정찰하세요.

[사용자 원문]
{request}

[관련 맥락]
{context or "(제공되지 않음)"}

가능한 정보원 family:
- COMMUNITY: 전문 커뮤니티, 핫딜 게시판, 실제 사용자 집단지성
- MARKETPLACE: 쇼핑몰, 거래 목록, 현재 가격·재고 데이터
- PRIMARY: 공식 문서, 정부·기관·제조사 원문, 연구 원문
- REUSE_INDEX: 기존 제품, GitHub, 앱·서비스 디렉터리, 공개 데이터베이스
- BROAD_WEB: 특정 생태계에 모이지 않은 일반 웹 자료

규칙:
- 최대 {max_searches}회의 웹 검색만 사용합니다.
- 서로 다른 정보원 2~4개를 실제로 찔러보고 비교합니다.
- 같은 family의 여러 사이트는 하나의 probe로 합칩니다. family를 중복해 반환하지 않습니다.
- 다른 검색에서 우연히 발견한 정보원은 queries=[]로 기록해도 됩니다.
- 최종 해결책이나 추천문을 쓰지 않습니다.
- 각 정보원에서 구체적인 상품명·프로젝트·원문·사례가 실제로 나오는지만 봅니다.
- 같은 검색 결과를 여러 정보원으로 중복 계산하지 않습니다.
- 막힌 사이트는 우회하느라 시간을 쓰지 말고 partial 또는 blocked로 기록합니다.
- concrete_leads는 정보원별 최대 3개입니다.
- 외부 조사가 결과를 바꾸지 않는 요청이면 검색하지 말고 external_research_needed=false, searches_used=0, probes=[]로 반환합니다.
- searches_used는 queries에 기록한 실제 검색어 수의 합과 같아야 합니다.
"""


def _reported_tokens(log_path: Path) -> int | None:
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"tokens used\s*\r?\n([\d,]+)", text)
    if not matches:
        return None
    return int(matches[-1].replace(",", ""))


def _result_markdown(state: Mapping[str, Any]) -> str:
    scout = state["source_scout"]
    decision = state["decision"]
    lines = [
        "# 정보원 정찰 결과",
        "",
        f"- 선택 경로: **{decision['strategy']}**",
        f"- 주력 정보원: {decision['primary_source_family'] or '없음'}",
        f"- 보조 정보원: {decision['secondary_source_family'] or '없음'}",
        f"- 정찰 검색: {scout['searches_used']}회",
        f"- 다음 행동: {decision['next_action']}",
        "",
        decision["selection_reason"],
    ]
    if scout["probes"]:
        lines.extend(["", "| 정보원 | 점수 | 신호 |", "|---|---:|---|"])
        for probe in scout["probes"]:
            lines.append(
                f"| {probe['family']} | {decision['scores'][probe['family']]} | "
                f"{probe['signal_summary'].replace('|', '/')} |"
            )
    if scout["scouting_limitations"]:
        lines.extend(["", "## 한계", ""])
        lines.extend(f"- {item}" for item in scout["scouting_limitations"])
    return "\n".join(lines).rstrip() + "\n"


def run_source_scout(
    request: str,
    *,
    engine: OS.ProblemSolvingEngine,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    run_id: str | None = None,
    context: str = "",
    max_searches: int = 4,
    policy: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    cleaned = request.strip()
    if not cleaned or len(cleaned) > MAX_REQUEST_CHARS:
        raise SourceScoutError("요청은 1~10,000자여야 합니다.")
    if max_searches not in range(2, 7):
        raise SourceScoutError("최대 검색 횟수는 2~6이어야 합니다.")
    chosen_run_id = run_id or f"scout-{OS.make_run_id().removeprefix('psos-')}"
    if re.fullmatch(r"[A-Za-z0-9._-]+", chosen_run_id) is None:
        raise SourceScoutError("run ID 형식이 올바르지 않습니다.")
    run_dir = output_root.expanduser().resolve() / chosen_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.txt").write_text(cleaned + "\n", encoding="utf-8")
    if context.strip():
        (run_dir / "context.txt").write_text(context.strip() + "\n", encoding="utf-8")

    capabilities = engine.capabilities()
    if not capabilities.ai_reasoning or not capabilities.web_search:
        raise SourceScoutError(capabilities.detail or "AI 웹 정찰 capability가 없습니다.")
    model_policy = policy or OS.load_model_policy()
    profile = replace(
        model_policy["routes"]["RESEARCH"]["primary"],
        reasoning_effort="low",
        sandbox="read-only",
    )
    invocation = OS.InvocationSpec(
        name="source-scout",
        phase="source-scout",
        route="RESEARCH",
        profile=profile,
        schema_path=SCHEMA_PATH,
    )
    started = time.monotonic()
    raw = engine.execute(
        scout_prompt(cleaned, context=context.strip(), max_searches=max_searches),
        run_dir,
        invocation,
    )
    elapsed = round(time.monotonic() - started, 3)
    scout = validate_probe(raw, max_searches=max_searches)
    decision = select_strategy(scout)
    state = {
        "version": 1,
        "run_id": chosen_run_id,
        "request": cleaned,
        "context": context.strip(),
        "source_scout": scout,
        "decision": decision,
        "elapsed_seconds": elapsed,
        "reported_tokens": _reported_tokens(run_dir / "source-scout.log"),
        "engine_trace": engine.trace(),
    }
    OS.write_json(run_dir / "source-scout-state.json", state)
    (run_dir / "result.md").write_text(_result_markdown(state), encoding="utf-8")
    return run_dir, state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--request-file", type=Path)
    parser.add_argument("--context-file", type=Path)
    parser.add_argument("--max-searches", type=int, choices=range(2, 7), default=4)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    request = (
        args.request
        if args.request is not None
        else args.request_file.expanduser().read_text(encoding="utf-8")
    )
    context = (
        args.context_file.expanduser().read_text(encoding="utf-8")
        if args.context_file is not None
        else ""
    )
    engine = OS.CodexEngine(ROOT, enable_search=True)
    try:
        run_dir, state = run_source_scout(
            request,
            engine=engine,
            output_root=args.output_root,
            run_id=args.run_id,
            context=context,
            max_searches=args.max_searches,
        )
        print(f"정보원 정찰 run: {run_dir}")
        print(f"선택 경로: {state['decision']['strategy']}")
        print(f"검색: {state['source_scout']['searches_used']}회")
        print(f"토큰: {state['reported_tokens'] if state['reported_tokens'] is not None else '측정 불가'}")
        return 0
    except (SourceScoutError, OS.ProblemSolvingError, OSError, json.JSONDecodeError) as exc:
        print(f"정보원 정찰 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
