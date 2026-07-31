#!/usr/bin/env python3
"""Run a human-first A/B test focused on recommendation and action quality."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import problem_solving_goal_aware_behavior_ab as AB  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "fixtures" / "recommendation-impact-cases.json"
POLICY_PATH = ROOT / "configs" / "psos-goal-aware-assistant-policy.md"
DEFAULT_OUTPUT_ROOT = ROOT / "runtime-results" / "recommendation-impact-ab"


def _escape_markdown_lite(value: str) -> str:
    escaped = html.escape(value)
    lines: list[str] = []
    for raw in escaped.splitlines():
        line = raw.strip()
        if line == "**user**":
            lines.append('<div class="role user">사용자</div>')
            continue
        if line == "**assistant**":
            lines.append('<div class="role assistant">AI</div>')
            continue
        if line.startswith("- "):
            line = f'<div class="bullet">• {line[2:]}</div>'
        else:
            line = line.replace("**", "")
        lines.append(line)
    return "<br>\n".join(lines)


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AB.GoalAwareBehaviorABError("manifest가 JSON 객체가 아닙니다.")
    return value


def _case_card(root: Path, case: Mapping[str, Any]) -> str:
    case_dir = root / case["id"]
    source = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    mapping = case["candidate_mapping"]

    candidates: dict[str, str] = {}
    for candidate_id in ("A", "B"):
        variant = mapping[candidate_id]
        transcript_path = root / case["variants"][variant]["transcript_path"]
        candidates[candidate_id] = transcript_path.read_text(encoding="utf-8")

    case_id = html.escape(case["id"])
    title = html.escape(case["title"])
    context = _escape_markdown_lite(source["context_markdown"])
    candidate_a = _escape_markdown_lite(candidates["A"])
    candidate_b = _escape_markdown_lite(candidates["B"])

    return f"""
<section class="case" id="{case_id}">
  <div class="case-head">
    <div>
      <div class="counter"></div>
      <h2>{title}</h2>
    </div>
    <details>
      <summary>판단 자료 보기</summary>
      <div class="context">{context}</div>
    </details>
  </div>

  <div class="compare">
    <article class="candidate">
      <div class="candidate-title">후보 A</div>
      <div class="candidate-body">{candidate_a}</div>
    </article>
    <article class="candidate">
      <div class="candidate-title">후보 B</div>
      <div class="candidate-body">{candidate_b}</div>
    </article>
  </div>

  <div class="review" data-case="{case_id}" data-title="{title}">
    <div class="review-row">
      <strong>실제로 더 따르고 싶은 답변</strong>
      <label><input type="radio" name="choice-{case_id}" value="A"> A</label>
      <label><input type="radio" name="choice-{case_id}" value="B"> B</label>
      <label><input type="radio" name="choice-{case_id}" value="동률"> 동률</label>
    </div>

    <div class="review-row">
      <strong>가장 큰 차이</strong>
      <select class="difference">
        <option value="">선택</option>
        <option value="추천·행동이 달라짐">추천·행동이 달라짐</option>
        <option value="핵심 근거·조건이 달라짐">핵심 근거·조건이 달라짐</option>
        <option value="주로 표현·가독성 차이">주로 표현·가독성 차이</option>
        <option value="둘 다 별로">둘 다 별로</option>
      </select>

      <label class="impact">
        <input type="checkbox" class="action-change">
        실제 선택이나 행동이 달라질 정도
      </label>
    </div>

    <input class="note" type="text" placeholder="왜 골랐는지 한 줄만 적기">
  </div>
</section>
"""


def build_compare_html(result: Mapping[str, Any]) -> Path:
    root = Path(result["output_dir"])
    manifest = _load_manifest(Path(result["manifest_path"]))
    cases = manifest["cases"]
    cards = "\n".join(_case_card(root, case) for case in cases)
    mapping = {
        case["id"]: case["candidate_mapping"]
        for case in cases
    }
    mapping_json = json.dumps(mapping, ensure_ascii=False).replace("</", "<\\/")

    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>추천·행동 품질 A/B 비교</title>
<style>
  :root {{
    font-family: "Malgun Gothic", "Segoe UI", sans-serif;
    color: #191919;
    background: #f4f5f7;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; }}
  header {{
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 13px 20px;
    background: rgba(255,255,255,.97);
    border-bottom: 1px solid #dfe2e7;
  }}
  header h1 {{ margin: 0; font-size: 19px; }}
  header p {{ flex: 1; margin: 0; color: #666; font-size: 13px; }}
  button {{
    border: 1px solid #c8cdd5;
    border-radius: 8px;
    background: white;
    padding: 8px 12px;
    cursor: pointer;
  }}
  button:disabled {{ opacity: .45; cursor: default; }}
  main {{
    max-width: 1500px;
    margin: 0 auto;
    padding: 18px;
    counter-reset: cases;
  }}
  .case {{
    counter-increment: cases;
    margin-bottom: 22px;
    overflow: hidden;
    background: white;
    border: 1px solid #dfe2e7;
    border-radius: 12px;
  }}
  .case-head {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    padding: 16px 18px;
    border-bottom: 1px solid #e4e7eb;
  }}
  .counter::before {{
    content: "CASE " counter(cases);
    color: #777;
    font-size: 12px;
    font-weight: 700;
  }}
  h2 {{ margin: 3px 0 0; font-size: 19px; }}
  details {{ max-width: 52%; }}
  summary {{ cursor: pointer; color: #555; font-size: 13px; text-align: right; }}
  .context {{
    margin-top: 10px;
    padding: 12px;
    background: #f8f9fb;
    border: 1px solid #e4e7eb;
    border-radius: 8px;
    line-height: 1.6;
    font-size: 13px;
    text-align: left;
  }}
  .compare {{
    display: grid;
    grid-template-columns: 1fr 1fr;
  }}
  .candidate:first-child {{ border-right: 1px solid #e1e4e8; }}
  .candidate-title {{
    position: sticky;
    top: 55px;
    z-index: 5;
    padding: 10px 17px;
    background: #f7f8fa;
    border-bottom: 1px solid #e1e4e8;
    font-size: 16px;
    font-weight: 700;
  }}
  .candidate-body {{
    min-height: 190px;
    padding: 18px;
    line-height: 1.72;
    font-size: 15px;
  }}
  .role {{
    display: inline-block;
    margin: 7px 0 4px;
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 700;
  }}
  .role.user {{ background: #eceff3; }}
  .role.assistant {{ background: #e7eefc; }}
  .bullet {{ margin: 3px 0; }}
  .review {{
    padding: 14px 18px 16px;
    border-top: 1px solid #e1e4e8;
    background: #fbfbfc;
  }}
  .review-row {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 10px;
  }}
  .review-row strong {{ min-width: 170px; }}
  label {{ cursor: pointer; }}
  select, .note {{
    border: 1px solid #cfd4dc;
    border-radius: 7px;
    background: white;
    padding: 8px 10px;
  }}
  .note {{ width: 100%; }}
  .impact {{ margin-left: 10px; }}
  #status {{ color: #555; font-size: 13px; white-space: nowrap; }}
  #reveal-box {{
    display: none;
    max-width: 1500px;
    margin: 0 auto 24px;
    padding: 16px 20px;
    background: white;
    border: 1px solid #dfe2e7;
    border-radius: 10px;
    line-height: 1.65;
  }}
  @media (max-width: 900px) {{
    header p {{ display: none; }}
    .compare {{ grid-template-columns: 1fr; }}
    .candidate:first-child {{
      border-right: 0;
      border-bottom: 1px solid #e1e4e8;
    }}
    .case-head {{ flex-direction: column; }}
    details {{ max-width: 100%; }}
    summary {{ text-align: left; }}
    .review-row {{ align-items: flex-start; flex-wrap: wrap; }}
    .review-row strong {{ width: 100%; }}
  }}
</style>
</head>
<body>
<header>
  <h1>추천·행동 품질 A/B</h1>
  <p>보기 좋은 답보다 실제로 따르고 싶은 답을 고릅니다. 정체 공개는 전부 고른 뒤에만 됩니다.</p>
  <span id="status"></span>
  <button id="copy" type="button">결과 복사</button>
  <button id="reveal" type="button" disabled>정체 공개</button>
</header>

<main>{cards}</main>
<div id="reveal-box"></div>

<script>
const mapping = {mapping_json};
const storageKey = "recommendation-impact-ab:" + location.pathname;

function collect() {{
  const result = {{}};
  document.querySelectorAll(".review").forEach(review => {{
    const checked = review.querySelector("input[type=radio]:checked");
    result[review.dataset.case] = {{
      title: review.dataset.title,
      choice: checked ? checked.value : "",
      difference: review.querySelector(".difference").value,
      actionChange: review.querySelector(".action-change").checked,
      note: review.querySelector(".note").value.trim()
    }};
  }});
  return result;
}}

function save() {{
  localStorage.setItem(storageKey, JSON.stringify(collect()));
  updateStatus();
}}

function load() {{
  const saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
  document.querySelectorAll(".review").forEach(review => {{
    const item = saved[review.dataset.case];
    if (!item) return;
    const radio = [...review.querySelectorAll("input[type=radio]")]
      .find(input => input.value === item.choice);
    if (radio) radio.checked = true;
    review.querySelector(".difference").value = item.difference || "";
    review.querySelector(".action-change").checked = Boolean(item.actionChange);
    review.querySelector(".note").value = item.note || "";
  }});
  updateStatus();
}}

function updateStatus() {{
  const reviews = [...document.querySelectorAll(".review")];
  const done = reviews.filter(
    review => review.querySelector("input[type=radio]:checked")
  ).length;
  document.querySelector("#status").textContent = done + " / " + reviews.length;
  document.querySelector("#reveal").disabled = done !== reviews.length;
}}

document.querySelectorAll("input, select").forEach(element => {{
  element.addEventListener("input", save);
  element.addEventListener("change", save);
}});

document.querySelector("#copy").addEventListener("click", async () => {{
  const result = collect();
  const lines = ["# 추천·행동 품질 A/B 결과", ""];
  Object.entries(result).forEach(([caseId, item], index) => {{
    lines.push(
      `${{index + 1}}. ${{item.title}} — ${{item.choice || "미선택"}}` +
      ` — ${{item.difference || "차이 미선택"}}` +
      ` — 행동 변화: ${{item.actionChange ? "예" : "아니오"}}` +
      (item.note ? ` — ${{item.note}}` : "")
    );
  }});
  await navigator.clipboard.writeText(lines.join("\n"));
  const button = document.querySelector("#copy");
  button.textContent = "복사됨";
  setTimeout(() => button.textContent = "결과 복사", 1200);
}});

document.querySelector("#reveal").addEventListener("click", () => {{
  const result = collect();
  const counts = {{goal_aware: 0, baseline: 0, tie: 0}};
  let substantive = 0;
  const rows = [];

  Object.entries(result).forEach(([caseId, item]) => {{
    let winner = "동률";
    if (item.choice === "A" || item.choice === "B") {{
      winner = mapping[caseId][item.choice];
      counts[winner] += 1;
    }} else {{
      counts.tie += 1;
    }}
    if (
      item.actionChange ||
      item.difference === "추천·행동이 달라짐" ||
      item.difference === "핵심 근거·조건이 달라짐"
    ) {{
      substantive += 1;
    }}
    rows.push(
      `<div><strong>${{item.title}}</strong>: ` +
      `A=${{mapping[caseId].A}}, B=${{mapping[caseId].B}} → 선택 ${{winner}}</div>`
    );
  }});

  const box = document.querySelector("#reveal-box");
  box.innerHTML =
    `<h2>블라인드 해제</h2>` +
    `<p><strong>goal-aware ${{counts.goal_aware}}승 · baseline ${{counts.baseline}}승 · 동률 ${{counts.tie}}</strong><br>` +
    `실질적인 판단·행동 차이가 있다고 표시한 사례: ${{substantive}} / ${{Object.keys(result).length}}</p>` +
    rows.join("");
  box.style.display = "block";
  box.scrollIntoView({{behavior: "smooth"}});
}});

load();
</script>
</body>
</html>
"""

    output = root / "blind_compare.html"
    output.write_text(document, encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--no-open", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    output_dir = args.output_dir
    if output_dir is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = DEFAULT_OUTPUT_ROOT / stamp

    try:
        result = AB.run_comparison(
            cases_path=CASES_PATH,
            policy_path=POLICY_PATH,
            selected_case_ids=args.case or None,
            output_dir=output_dir,
            judge=False,
            timeout_seconds=args.timeout_seconds,
        )
        compare_path = build_compare_html(result)
    except (AB.GoalAwareBehaviorABError, AB.OS.ProblemSolvingError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(compare_path)
    if not args.no_open:
        webbrowser.open(compare_path.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
