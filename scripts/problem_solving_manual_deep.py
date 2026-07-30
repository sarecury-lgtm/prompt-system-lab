#!/usr/bin/env python3
"""Deep-research prompting and quality gates for the PSOS manual bridge."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import problem_solving_manual as manual
import problem_solving_manual_revision as revision_manual


URL_PATTERN = re.compile(r"https?://[^\s<>\]\[(){}\"']+")
PRICE_PATTERN = re.compile(r"(?:₩\s*)?\d[\d,]*(?:\.\d+)?\s*원")
COMMERCE_CURRENT_PATTERN = re.compile(
    r"현재|지금|오늘|온라인|판매|구매|구입|주문|재고|가격|배송|상품|제품|쇼핑"
)
COMMERCE_OBJECT_PATTERN = re.compile(
    r"상품|제품|판매처|판매자|스토어|쇼핑몰|온라인몰|구매|구입|주문|가격|재고"
)


def is_live_listing_request(state: dict[str, Any]) -> bool:
    """Return whether the research target is a currently purchasable listing."""

    ledger = (state.get("route_payload") or {}).get("goal_ledger") or {}
    text = "\n".join(
        [
            str(state.get("request", "")),
            str(ledger.get("parent_goal", "")),
            str(ledger.get("current_goal_hypothesis", "")),
            "\n".join(str(item) for item in ledger.get("fixed_constraints", [])),
            str(ledger.get("current_step", "")),
            str(ledger.get("completion_condition", "")),
        ]
    )
    return bool(
        COMMERCE_CURRENT_PATTERN.search(text)
        and COMMERCE_OBJECT_PATTERN.search(text)
    )


def listing_contract() -> str:
    return """
[현재 판매 상품 조사 계약]
이 요청의 조사 단위는 품종·카테고리·상품군이 아니라 현재 구매 가능한 개별 판매 상품이다.

조사 계획부터 다음 순서를 고정한다.
1. 실제 판매 페이지에서 후보를 넓게 수집한다.
2. 각 후보의 현재 가격·구성·판매자·주문 가능 상태를 직접 확인한다.
3. 그 뒤 공식 품종 자료, 생산자 설명, 최근 구매 후기로 사용자의 조건을 검증한다.
4. 최종 후보를 직접 비교하고 실패 위험과 미확인을 분리한다.

필수 조건:
- 가능하면 서로 다른 판매처를 포함해 개별 상품 후보를 8개 이상 탐색한다. 실제로 찾은 수가 적으면 부족한 수를 숨기지 않는다.
- 최종 비교 후보는 원칙적으로 3개 이상 제시한다. 조건을 충족하는 상품이 3개 미만이면 억지로 채우지 말고 이유를 쓴다.
- 최종 후보마다 정확한 상품명, 판매자 또는 판매처, 현재 가격, 구성·중량, 현재 판매 상태, 확인 시각, 직접 상품 URL을 본문에 표시한다.
- 직접 상품 페이지를 실제로 열어 가격과 주문 가능 상태를 확인하지 못한 후보는 '현재 구매 가능'이라고 단정하지 않는다.
- 검색 결과 요약문, 과거 판매 기록, '쿠팡 등', '팔도감 등' 같은 뭉뚱그린 표현은 직접 판매 페이지 확인을 대신할 수 없다.
- 품종 특성은 개별 상품을 검증하는 보조 근거다. 품종명이나 상품군만으로 최종 추천을 대체하지 않는다.
- 판매자 주장, 공식·독립 자료, 구매 후기, 조사자의 추론을 명시적으로 구분한다.
- 당도 수치가 상품 제목이나 광고에만 있으면 판매자 주장으로 표시한다. 현재 출고분 실측값처럼 쓰지 않는다.
- 각 최종 후보의 직접 URL을 원문 그대로 남긴다. 인용 번호나 출처명만 쓰고 URL을 생략하지 않는다.
- 직접 URL과 현재 판매 상태를 확인하지 못했다면 추천을 꾸미지 말고 확인 실패로 보고한다.

보고서 구조:
- 조사 기준 시각
- 핵심 결론
- 후보 수집 범위와 확인 방법
- 최종 후보별 상품 정보 및 직접 URL
- 확인 사실 / 판매자 주장 / 후기 / 추론
- 후보 직접 비교
- 제외 후보와 제외 이유
- 실패 위험과 남은 미확인
- 실제 사용한 출처 URL 목록
""".strip()


def deep_research_report_prompt(state: dict[str, Any], route: str) -> str:
    """Build a clean Deep Research prompt without manual-model metadata noise."""

    ledger = state["route_payload"]["goal_ledger"]
    contract = listing_contract() if is_live_listing_request(state) else """
[심층 리서치 출처 계약]
- 최종 결론을 지지하는 실제 출처를 본문에 연결한다.
- 확인 사실, 출처의 주장, 추론, 미확인을 구분한다.
- 인용 표지만 남기지 말고 사용한 출처 URL도 보고서 끝에 원문으로 정리한다.
""".strip()
    return f"""당신은 Personal Problem-Solving OS의 {route} 심층 리서치 실행기다.

아래 Goal Ledger의 상위 목적과 고정 조건을 바꾸지 말고 실제 조사를 수행한다.
이 단계에서는 execution JSON을 만들지 않는다. 완성된 Markdown 보고서만 반환한다.

[Goal Ledger]
{json.dumps(ledger, ensure_ascii=False, indent=2)}

[사용자 요청]
{state['request'].strip()}

[조사 계획 점검]
- 계획의 각 단계가 fixed_constraints의 어느 조건을 검증하는지 확인한다.
- 사용자가 요구한 결과의 단위를 먼저 고정한다. 개별 상품 요청을 품종·카테고리 일반론으로 넓히지 않는다.
- 최신 상태가 중요한 대상은 현재 페이지를 먼저 확인하고, 공식·1차 자료는 특성 검증에 사용한다.
- 계획이 일반 배경지식 설명 중심이면 실행 전에 실제 대상 수집·검증 중심으로 고친다.

{contract}

[공통 보고서 규칙]
- 라이브 웹 조사를 실제로 수행한다.
- 공식·1차 출처와 현재 대상 페이지를 우선하되, 서로 역할을 구분한다.
- 확인 사실·출처의 주장·후기·추론·미확인을 섞지 않는다.
- 최종 추천, 직접 비교, 제외 이유, 실패 위험, 남은 한계를 포함한다.
- 근거가 약하면 강한 결론으로 부풀리지 않는다.
- JSON, 코드 펜스, 조사 계획만 있는 미완성 답변은 반환하지 않는다.
"""


def _distinct_urls(report: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.findall(report):
        url = match.rstrip(".,;:")
        if url not in urls:
            urls.append(url)
    return urls


def _direct_urls(urls: list[str]) -> list[str]:
    direct = []
    for url in urls:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if parsed.netloc and path and path.lower() not in {"search", "products", "goods"}:
            direct.append(url)
    return direct


def validate_deep_report(raw: str, state: dict[str, Any]) -> str:
    """Reject category-level or source-free reports before normalization."""

    report = manual.validate_report(raw)
    urls = _distinct_urls(report)
    if len(urls) < 2:
        raise manual.ManualBridgeError(
            "심층 리서치 보고서에 실제 출처 URL이 부족합니다. 인용 표지만 말고 "
            "사용한 출처 URL을 원문으로 포함한 완성 보고서를 다시 붙여넣어 주세요."
        )

    if not is_live_listing_request(state):
        return report

    missing: list[str] = []
    direct_urls = _direct_urls(urls)
    if len(direct_urls) < 3:
        missing.append("서로 구분되는 직접 판매·상품 URL 3개 이상")
    if len(PRICE_PATTERN.findall(report)) < 2:
        missing.append("복수 후보의 현재 가격")
    if not re.search(r"판매\s*상태|구매\s*가능|주문\s*가능|구매\s*버튼|품절|재고|판매\s*중", report):
        missing.append("현재 판매 또는 주문 가능 상태")
    if not re.search(r"판매자|판매처|농원|과수원|스토어|몰", report):
        missing.append("판매자 또는 판매처")
    if not re.search(r"확인\s*(?:시각|일시|기준)|조사\s*기준|20\d{2}[년./-]\s*\d{1,2}", report):
        missing.append("조사·확인 시각")

    if missing:
        raise manual.ManualBridgeError(
            "이 보고서는 현재 판매 상품 조사로는 미완성입니다. 빠진 항목: "
            + ", ".join(missing)
            + ". 품종·상품군 설명으로 대체하지 말고 개별 상품 페이지를 확인한 보고서를 다시 제출해 주세요."
        )
    return report


class ManualBridge(revision_manual.ManualBridge):
    """Revision-capable bridge with strict Deep Research contracts."""

    def prepare_executor(
        self,
        run_dir,
        state: dict[str, Any],
        route: str,
        label: str,
        primary: dict[str, Any] | None = None,
    ) -> None:
        if route == "RESEARCH" and state.get("research_mode") == "deep":
            self.set_prompt(
                run_dir,
                state,
                f"{label}_deep_report",
                route,
                label,
                deep_research_report_prompt(state, route),
                None,
                response_kind="markdown",
            )
            return
        super().prepare_executor(run_dir, state, route, label, primary)

    def submit(self, run_id: str, response: str) -> dict[str, Any]:
        with self.lock:
            run_dir = self.run_dir(run_id)
            if not run_dir.is_dir():
                raise manual.ManualBridgeError("해당 run을 찾을 수 없습니다.")
            state = manual.read_state(run_dir)
            stage = state.get("stage") or {}
            if (
                state.get("state", "").startswith("awaiting_")
                and stage.get("response_kind") == "markdown"
            ):
                try:
                    validate_deep_report(response, state)
                except manual.ManualBridgeError as exc:
                    state["error"] = str(exc)
                    self.save(run_dir, state)
                    raise
            return super().submit(run_id, response)
