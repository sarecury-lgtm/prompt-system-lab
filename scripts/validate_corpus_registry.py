#!/usr/bin/env python3
"""Validate PR001-PR130 corpus inventory against corpus/registry.csv.

The validator is intentionally conservative. It checks repository structure and
extracts metadata, but it does not promote evidence status automatically.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "corpus" / "registry.csv"

RANGE_FILES = {
    "prompt-corpus/famous-prompts.md": range(1, 21),
    "prompt-corpus/famous-prompts-pr021-pr040.md": range(21, 41),
    "prompt-corpus/famous-prompts-pr041-pr060.md": range(41, 61),
    "prompt-corpus/famous-prompts-pr061-pr080.md": range(61, 81),
    "prompt-corpus/famous-prompts-pr081-pr100.md": range(81, 101),
    "prompt-corpus/famous-prompts-pr101-pr120.md": range(101, 121),
    "prompt-corpus/famous-prompts-pr121-pr130.md": range(121, 131),
}

ENTRY_HEADING = re.compile(r"^###\s+(PR\d{3})(?:\s+[—-]\s+(.+?))?\s*$", re.MULTILINE)
NAME_FIELD = re.compile(r"^-\s+\*\*Name:\*\*\s*(.+?)\s*$", re.MULTILINE)
URL_FIELD = re.compile(r"^-\s+\*\*Source URL:\*\*\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Entry:
    entry_id: str
    source_file: str
    title: str
    source_url: str
    source_url_status: str
    content_level: str
    has_safety_boundary: bool
    block: str


def expected_source_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for source_file, numbers in RANGE_FILES.items():
        for number in numbers:
            result[f"PR{number:03d}"] = source_file
    return result


def classify_content(block: str) -> str:
    required_review_sections = (
        "## Pattern lesson",
        "## Mechanism",
        "## Failure mode",
        "## Reusable move",
    )
    if all(section in block for section in required_review_sections):
        return "structured-review"
    if "## Evidence note" in block:
        return "evidence-note"
    if "## Short excerpt" in block or "**Short excerpt:**" in block:
        return "excerpt-or-paraphrase"
    if "## Structure summary" in block or "**Structure summary:**" in block:
        return "summary-only"
    return "metadata-only"


def parse_file(relative_path: str) -> list[Entry]:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    matches = list(ENTRY_HEADING.finditer(text))
    entries: list[Entry] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].rstrip()
        entry_id = match.group(1)
        heading_title = (match.group(2) or "").strip()
        name_match = NAME_FIELD.search(block)
        title = heading_title or (name_match.group(1).strip() if name_match else "")
        url_match = URL_FIELD.search(block)
        source_url = url_match.group(1).strip() if url_match else ""
        source_url_status = "present" if source_url and source_url.lower() not in {"n/a", "none", "unknown"} else "missing"
        has_safety_boundary = "Safety / reproduction note" in block or "Safety note" in block

        entries.append(
            Entry(
                entry_id=entry_id,
                source_file=relative_path,
                title=title,
                source_url=source_url,
                source_url_status=source_url_status,
                content_level=classify_content(block),
                has_safety_boundary=has_safety_boundary,
                block=block,
            )
        )
    return entries


def load_registry() -> list[dict[str, str]]:
    with REGISTRY_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def duplicates(values: Iterable[str]) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(value for value, count in counts.items() if count > 1)


def write_extracted(entries: list[Entry], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "entry_id",
                "source_file",
                "title",
                "source_url",
                "source_url_status",
                "content_level",
                "has_safety_boundary",
            ]
        )
        for entry in sorted(entries, key=lambda item: item.entry_id):
            writer.writerow(
                [
                    entry.entry_id,
                    entry.source_file,
                    entry.title,
                    entry.source_url,
                    entry.source_url_status,
                    entry.content_level,
                    str(entry.has_safety_boundary).lower(),
                ]
            )


def build_report(entries: list[Entry], registry: list[dict[str, str]]) -> tuple[str, bool]:
    expected = expected_source_map()
    by_id: dict[str, list[Entry]] = {}
    for entry in entries:
        by_id.setdefault(entry.entry_id, []).append(entry)

    found_ids = set(by_id)
    expected_ids = set(expected)
    missing_ids = sorted(expected_ids - found_ids)
    unexpected_ids = sorted(found_ids - expected_ids)
    duplicate_ids = sorted(entry_id for entry_id, items in by_id.items() if len(items) > 1)

    wrong_range: list[str] = []
    missing_titles: list[str] = []
    missing_urls: list[str] = []
    for entry_id, items in sorted(by_id.items()):
        for entry in items:
            if entry_id in expected and expected[entry_id] != entry.source_file:
                wrong_range.append(f"{entry_id}: {entry.source_file} (expected {expected[entry_id]})")
            if not entry.title:
                missing_titles.append(entry_id)
            if entry.source_url_status == "missing":
                missing_urls.append(entry_id)

    registry_ids = [row.get("entry_id", "") for row in registry]
    registry_duplicates = duplicates(registry_ids)
    registry_missing = sorted(expected_ids - set(registry_ids))
    registry_unexpected = sorted(set(registry_ids) - expected_ids)
    registry_wrong_source: list[str] = []
    registry_by_id = {row.get("entry_id", ""): row for row in registry}
    for entry_id, expected_file in expected.items():
        row = registry_by_id.get(entry_id)
        if row and row.get("source_file") != expected_file:
            registry_wrong_source.append(
                f"{entry_id}: {row.get('source_file')} (expected {expected_file})"
            )

    counts_by_level: dict[str, int] = {}
    for entry in entries:
        counts_by_level[entry.content_level] = counts_by_level.get(entry.content_level, 0) + 1

    structural_failures = any(
        [
            missing_ids,
            unexpected_ids,
            duplicate_ids,
            wrong_range,
            registry_duplicates,
            registry_missing,
            registry_unexpected,
            registry_wrong_source,
        ]
    )

    def render(items: list[str]) -> str:
        return ", ".join(items) if items else "none"

    lines = [
        "# Corpus Registry Validation Report",
        "",
        "Generated by `scripts/validate_corpus_registry.py`.",
        "",
        "## Structural result",
        "",
        f"- Result: {'FAIL' if structural_failures else 'PASS'}",
        f"- Expected IDs: {len(expected_ids)}",
        f"- Parsed entries: {len(entries)}",
        f"- Registry rows: {len(registry)}",
        f"- Missing corpus IDs: {render(missing_ids)}",
        f"- Duplicate corpus IDs: {render(duplicate_ids)}",
        f"- Unexpected corpus IDs: {render(unexpected_ids)}",
        f"- IDs in wrong range file: {render(wrong_range)}",
        f"- Missing registry IDs: {render(registry_missing)}",
        f"- Duplicate registry IDs: {render(registry_duplicates)}",
        f"- Unexpected registry IDs: {render(registry_unexpected)}",
        f"- Wrong registry source file: {render(registry_wrong_source)}",
        "",
        "## Metadata warnings",
        "",
        "These warnings do not fail structural validation.",
        "",
        f"- Entries without parsed title: {render(sorted(set(missing_titles)))}",
        f"- Entries without parsed source URL: {render(sorted(set(missing_urls)))}",
        "",
        "## Content-level inventory",
        "",
    ]
    for level in sorted(counts_by_level):
        lines.append(f"- {level}: {counts_by_level[level]}")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report validates inventory shape and extracts local metadata. It does not verify external URLs, authorship, prompt effectiveness, copyright status, or runtime value. Content-level labels describe the local entry format only and must not be treated as evidence grades.",
            "",
        ]
    )
    return "\n".join(lines), structural_failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "audit" / "corpus-registry-validation.generated.md",
    )
    parser.add_argument(
        "--extracted",
        type=Path,
        default=ROOT / "audit" / "corpus-registry-extracted.generated.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries: list[Entry] = []
    for relative_path in RANGE_FILES:
        entries.extend(parse_file(relative_path))

    registry = load_registry()
    report, failed = build_report(entries, registry)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    write_extracted(entries, args.extracted)
    print(report)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
