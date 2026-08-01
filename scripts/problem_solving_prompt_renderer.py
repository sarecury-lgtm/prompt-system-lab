#!/usr/bin/env python3
"""Render a reusable PSOS prompt from a validated Prompt Build Brief without Codex."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_prompt_build_brief as BRIEF  # noqa: E402


DEFAULT_POLICY_PATH = ROOT / "configs" / "psos-goal-aware-assistant-policy.md"
CORE_PROCEDURE_LIMIT = 12
OUTPUT_CONTRACT_LIMIT = 12

# Detailed domain procedures and output contracts can legitimately require
# more than eight distinct items. Keep the shared validator strict, but raise
# only these semantic fields' caps before renderer and comparison flows validate
# a brief.
BRIEF.LIST_LIMITS["core_procedure"] = (0, CORE_PROCEDURE_LIMIT)
BRIEF.LIST_LIMITS["output_contract"] = (1, OUTPUT_CONTRACT_LIMIT)


class PromptRendererError(ValueError):
    """Raised when a deterministic prompt cannot be rendered safely."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptRendererError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptRendererError(f"{label}은 JSON 객체여야 합니다.")
    return value


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> str:
    try:
        text = path.expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PromptRendererError(f"공통 정책을 읽을 수 없습니다: {exc}") from exc
    if not text:
        raise PromptRendererError("공통 정책이 비어 있습니다.")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _section(title: str, values: Sequence[str]) -> str | None:
    normalized = [value.strip() for value in values if value.strip()]
    if not normalized:
        return None
    body = "\n".join(f"{index}. {value}" for index, value in enumerate(normalized, 1))
    return f"## {title}\n\n{body}"


def render_prompt(
    brief: Mapping[str, Any],
    ledger: Mapping[str, Any],
    policy: str,
) -> str:
    validated = BRIEF.validate_prompt_build_brief(dict(brief), ledger)
    goal = validated["goal"]

    parts = [
        "# 역할과 목표",
        "",
        "당신은 아래 목표를 반복해서 수행하는 AI다. 지침 자체나 PSOS 생성 과정을 사용자에게 설명하지 말고 실제 결과만 제공한다.",
        "",
        f"**목표:** {goal}",
        "",
        "## 공통 판단 원칙",
        "",
        policy.strip(),
    ]

    sections = (
        ("핵심 작업 절차", validated["core_procedure"]),
        ("사용할 입력·자료·도구", validated["supporting_inputs"]),
        ("반드시 지킬 조건", validated["fixed_constraints"]),
        ("기본값과 예외 처리", validated["defaults_and_exceptions"]),
        ("하지 않을 일", validated["exclusions"]),
        ("검증된 상위 맥락", validated["upstream_context"]),
        ("완료 조건과 출력", validated["output_contract"]),
    )
    for title, values in sections:
        rendered = _section(title, values)
        if rendered:
            parts.extend(["", rendered])

    parts.extend(
        [
            "",
            "## 실행 규칙",
            "",
            "- 필요한 정보가 이미 있으면 확인 질문 없이 바로 수행한다.",
            "- 정보 부족으로 결과가 실질적으로 달라질 때만 핵심 질문 1~2개를 먼저 한다.",
            "- 선택·판단 요청에서는 가능한 경우 하나의 추천이나 다음 행동을 분명히 제시한다.",
            "- 같은 결론을 더 길게 표현하는 것을 개선으로 간주하지 않는다.",
            "- 확인된 사실, 제공 자료에 근거한 추론, 남은 불확실성을 혼동하지 않는다.",
        ]
    )
    return "\n".join(parts).rstrip() + "\n"


def render_from_files(
    *,
    brief_path: Path,
    ledger_path: Path,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> str:
    brief = _read_json(brief_path, "Prompt Build Brief")
    ledger = _read_json(ledger_path, "Goal Ledger")
    policy = load_policy(policy_path)
    try:
        return render_prompt(brief, ledger, policy)
    except BRIEF.PromptBuildBriefError as exc:
        raise PromptRendererError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        prompt = render_from_files(
            brief_path=args.brief,
            ledger_path=args.ledger,
            policy_path=args.policy,
        )
        if args.output is None:
            sys.stdout.write(prompt)
        else:
            output = args.output.expanduser()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(prompt, encoding="utf-8")
            print(output.resolve())
    except PromptRendererError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
