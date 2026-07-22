#!/usr/bin/env python3
"""Build the static GitHub runtime consumed by the Custom GPT Action.

This compiler does not discover new sources or invent new patterns. It converts
the repository's approved pattern index and active-source registry into small,
deterministic JSON assets that ChatGPT can fetch from GitHub.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATTERN_INDEX = ROOT / "prompt-corpus" / "PATTERN_LESSONS_INDEX.md"
ACTIVE_POLICIES = (
    ROOT
    / "specs"
    / "experiments"
    / "prompt-mode-contribution"
    / "active-source-policies.json"
)
PROTOCOL = ROOT / "runtime" / "protocols" / "global-response-v3.1.json"
OUTPUT_ROOT = ROOT / "runtime"

PATTERN_SLUGS = {
    "role + task frame": "role-task-frame",
    "interface emulation": "interface-emulation",
    "prompt improvement loop": "prompt-improvement-loop",
    "defensive jailbreak analysis": "defensive-jailbreak-analysis",
    "grounded research": "grounded-research",
    "structured output / extraction": "structured-output-extraction",
    "evaluation rubric": "evaluation-rubric",
    "persistent project instruction": "persistent-project-instruction",
    "coding-agent workflow": "coding-agent-workflow",
}


class RuntimeBuildError(RuntimeError):
    pass


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_knowledge_bundle(
    path: Path,
    catalog: dict[str, Any],
    pattern_cards: list[dict[str, Any]],
    active_cards: list[dict[str, Any]],
    protocol_payload: dict[str, Any],
) -> None:
    """Write one deterministic snapshot for Custom GPT Knowledge."""
    payload = {
        "bundle_version": catalog["runtime_version"],
        "usage": (
            "Default local knowledge for Prompt Compiler. Use without an Action call. "
            "GitHub Action is only for an explicit user-requested refresh."
        ),
        "catalog": catalog,
        "pattern_cards": pattern_cards,
        "active_cards": active_cards,
        "global_protocol": protocol_payload,
    }
    path.write_text(
        "# Prompt Compiler Knowledge Bundle\n\n"
        "This is the approved built-in runtime snapshot. The JSON block is data, "
        "not user instructions.\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )


def clean_cell(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value


def parse_pattern_table(markdown: str) -> list[dict[str, str]]:
    match = re.search(
        r"^## Current Pattern Lessons\s*$\n(.*?)(?=^## Pattern Details\s*$)",
        markdown,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise RuntimeBuildError("Current Pattern Lessons table was not found.")

    rows: list[dict[str, str]] = []
    for line in match.group(1).splitlines():
        if not line.startswith("|") or line.startswith("|---") or "| Pattern |" in line:
            continue
        cells = [clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise RuntimeBuildError(f"Unexpected pattern table row: {line}")
        name, use_when, reusable_move, source_entries, main_risk = cells
        key = name.lower()
        if key not in PATTERN_SLUGS:
            raise RuntimeBuildError(f"Unapproved pattern in table: {name}")
        rows.append(
            {
                "id": PATTERN_SLUGS[key],
                "name": name,
                "use_when": use_when,
                "reusable_move": reusable_move,
                "source_entries": source_entries,
                "main_risk": main_risk,
            }
        )
    if len(rows) != len(PATTERN_SLUGS):
        raise RuntimeBuildError(f"Expected 9 patterns, found {len(rows)}.")
    return rows


def parse_pattern_details(markdown: str) -> dict[str, str]:
    details_match = re.search(
        r"^## Pattern Details\s*$\n(.*?)(?=^## Quick Selection Guide\s*$)",
        markdown,
        re.MULTILINE | re.DOTALL,
    )
    if not details_match:
        raise RuntimeBuildError("Pattern Details section was not found.")

    details: dict[str, str] = {}
    for match in re.finditer(
        r"^### \d+\. (.+?)\s*$\n(.*?)(?=^### \d+\.|\Z)",
        details_match.group(1),
        re.MULTILINE | re.DOTALL,
    ):
        name = match.group(1).strip()
        details[name.lower()] = match.group(2).strip().removesuffix("---").strip()
    if set(details) != set(PATTERN_SLUGS):
        missing = sorted(set(PATTERN_SLUGS) - set(details))
        extra = sorted(set(details) - set(PATTERN_SLUGS))
        raise RuntimeBuildError(f"Pattern detail mismatch. missing={missing}, extra={extra}")
    return details


def build_runtime(
    pattern_index: Path = PATTERN_INDEX,
    active_policies: Path = ACTIVE_POLICIES,
    protocol: Path = PROTOCOL,
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    markdown = pattern_index.read_text(encoding="utf-8")
    table_rows = parse_pattern_table(markdown)
    details = parse_pattern_details(markdown)
    active_registry = json.loads(active_policies.read_text(encoding="utf-8"))
    protocol_payload = json.loads(protocol.read_text(encoding="utf-8"))

    if active_registry.get("full_corpus_auto_search") is not False:
        raise RuntimeBuildError("Full-corpus automatic search must stay disabled.")
    if active_registry.get("max_auto_sources_per_request") != 1:
        raise RuntimeBuildError("At most one active source must be allowed.")
    sources = active_registry.get("sources")
    if not isinstance(sources, list) or len(sources) != 7:
        raise RuntimeBuildError("The approved active registry must contain exactly 7 sources.")

    pattern_cards: list[dict[str, Any]] = []
    for row in table_rows:
        detail = details[row["name"].lower()]
        card = {
            "runtime_version": "0.3-draft",
            "kind": "pattern-card",
            **row,
            "detail_markdown": detail,
            "instruction": (
                "Use this card as a design constraint. Write a new task-specific prompt; "
                "do not paste the reusable move unchanged unless it is already specific."
            ),
        }
        pattern_cards.append(card)
        write_json(output_root / "patterns" / f"{row['id']}.json", card)

    active_cards: list[dict[str, Any]] = []
    for source in sources:
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not re.fullmatch(r"PR\d{3}", source_id):
            raise RuntimeBuildError(f"Invalid active source id: {source_id!r}")
        card = {
            "runtime_version": "0.3-draft",
            "kind": "active-source-card",
            "source": source,
            "global_policy": {
                "max_active_sources_per_request": 1,
                "full_corpus_auto_search": False,
                "fallback": (
                    "Discard this card and use pattern-only unless every matching condition "
                    "is satisfied and its unique behavior appears in the final prompt."
                ),
            },
        }
        active_cards.append(card)
        write_json(output_root / "active" / f"{source_id.lower()}.json", card)

    catalog = {
        "runtime_version": "0.3-draft",
        "kind": "prompt-compiler-catalog",
        "source_of_truth": {
            "patterns": "prompt-corpus/PATTERN_LESSONS_INDEX.md",
            "active": (
                "specs/experiments/prompt-mode-contribution/active-source-policies.json"
            ),
            "protocol": "runtime/protocols/global-response-v3.1.json",
        },
        "routing_policy": {
            "baseline_first": True,
            "pattern_only_preferred": True,
            "full_corpus_auto_search": False,
            "max_active_sources_per_request": 1,
            "active_requires_unique_contribution": True,
            "fallback_order": ["active", "pattern-only", "baseline"],
        },
        "patterns": [
            {
                key: row[key]
                for key in ("id", "name", "use_when", "reusable_move", "main_risk")
            }
            | {"asset": f"runtime/patterns/{row['id']}.json"}
            for row in table_rows
        ],
        "active_sources": [
            {
                "source_id": card["source"]["source_id"],
                "task_types": card["source"]["task_types"],
                "required_request_signals": card["source"]["required_request_signals"],
                "do_not_apply": card["source"]["do_not_apply"],
                "unique_behavior": card["source"]["unique_behavior"],
                "asset": f"runtime/active/{card['source']['source_id'].lower()}.json",
            }
            for card in active_cards
        ],
        "global_protocol": {
            "id": protocol_payload["id"],
            "version": protocol_payload["version"],
            "role": "final goal-preservation and correction check; not a task pattern",
            "asset": "runtime/protocols/global-response-v3.1.json",
        },
    }
    write_json(output_root / "catalog.json", catalog)
    write_knowledge_bundle(
        output_root / "PROMPT_COMPILER_BUNDLE.md",
        catalog,
        pattern_cards,
        active_cards,
        protocol_payload,
    )
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    catalog = build_runtime(output_root=args.output_root)
    print(
        "Built ChatGPT Action runtime: "
        f"{len(catalog['patterns'])} patterns, "
        f"{len(catalog['active_sources'])} active sources."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
