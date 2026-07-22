#!/usr/bin/env python3
"""Semi-automated prompt corpus upgrade pipeline.

Uses only the Python standard library. It intentionally never edits the raw
corpus files or PATTERN_LESSONS_INDEX.md during apply; those changes remain
human-reviewed.
"""

from __future__ import annotations

import argparse
import copy
import contextlib
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "prompt-corpus"
MANIFEST_PATH = CORPUS_DIR / "corpus-manifest.json"
PATTERN_INDEX_PATH = CORPUS_DIR / "PATTERN_LESSONS_INDEX.md"
PATTERN_VERIFICATION_PATH = CORPUS_DIR / "PATTERN_VERIFICATION.md"
DRAFTS_DIR = CORPUS_DIR / "pipeline-drafts"
INDEX_CANDIDATES_DIR = CORPUS_DIR / "index-candidates"
DEFAULT_REPORT_PATH = ROOT / "reports" / "corpus-pipeline-validation.json"
RUNS_DIR = ROOT / "reports" / "corpus-pipeline-runs"
REVIEW_SCHEMA_PATH = CORPUS_DIR / "independent-review.schema.json"

CORPUS_FILES = (
    CORPUS_DIR / "famous-prompts.md",
    CORPUS_DIR / "famous-prompts-pr021-pr040.md",
    CORPUS_DIR / "famous-prompts-pr041-pr060.md",
    CORPUS_DIR / "famous-prompts-pr061-pr080.md",
    CORPUS_DIR / "famous-prompts-pr081-pr100.md",
    CORPUS_DIR / "famous-prompts-pr101-pr120.md",
    CORPUS_DIR / "famous-prompts-pr121-pr130.md",
)

UPGRADE_STATUSES = (
    "cataloged",
    "lesson-draft",
    "verified",
    "tested",
)
PATTERN_LINK_STATUSES = (
    "unlinked",
    "candidate",
    "referenced",
    "confirmed",
)
AUTOMATION_STATUSES = ("pending", "applied", "deferred")
DUPLICATE_STATUSES = ("unique", "distinct", "canonical", "alias", "deferred")

# Classifications already established by the repository's duplicate review.
DISTINCT_DUPLICATE_IDS = {
    *(f"PR{number:03d}" for number in range(1, 11)),
    *(f"PR{number:03d}" for number in range(81, 86)),
}
DUPLICATE_ALIASES = {
    "PR123": "PR012",
    "PR119": "PR015",
    "PR103": "PR033",
    "PR104": "PR034",
    "PR105": "PR035",
    "PR102": "PR036",
    "PR101": "PR037",
}
DEFERRED_DUPLICATE_IDS = {"PR016", "PR100"}
EVIDENCE_RELATIONS = (
    "direct",
    "partial",
    "adjacent",
    "synthesized",
    "unverified",
)
STATUS_RANK = {status: index for index, status in enumerate(UPGRADE_STATUSES)}
ID_RE = re.compile(r"^PR\d{3}$")
ENTRY_HEADING_RE = re.compile(
    r"^###\s+(PR\d{3})(?:\s+[—-]\s*(.+?))?\s*$", re.MULTILINE
)
PATTERN_HEADING_RE = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
PR_RANGE_RE = re.compile(r"PR(\d{3})(?:\s*[–-]\s*PR?(\d{3}))?")
LOCAL_ONLY_MARKERS = (
    "local entry",
    "local corpus",
    "existing structure summary",
    "exact upstream prompt wording was not verified",
    "exact reddit prompt text was not verified",
    "exact anthropic example text was not verified",
    "exact fabric pattern text was not verified",
)

WEAK_PATTERNS = (
    "Grounded Research",
    "Evaluation Rubric",
    "Persistent Project Instruction",
    "Coding-Agent Workflow",
)
PRIORITY_PATTERN_GAPS = (
    "Structured Output / Extraction",
    "Grounded Research",
    "Defensive Jailbreak Analysis",
)
PREFERRED_PATTERN_SOURCES = {
    "Structured Output / Extraction": ("PR061", "PR062", "PR064", "PR106"),
    "Grounded Research": ("PR039", "PR109", "PR106", "PR040"),
    "Defensive Jailbreak Analysis": (
        "PR025", "PR026", "PR027", "PR028", "PR029", "PR030", "PR031", "PR032"
    ),
}
PATTERN_GAPS = {
    "Structured Output / Extraction": (
        "Direct original-source evidence for exact schemas, missing-value policy, "
        "and no-extra-commentary extraction behavior."
    ),
    "Grounded Research": (
        "Original-source evidence for retrieval, citations, uncertainty handling, "
        "and evidence-before-recommendation behavior."
    ),
    "Evaluation Rubric": (
        "Primary-source rubric or eval evidence with observable scoring anchors, "
        "failure examples, and regression checks."
    ),
    "Persistent Project Instruction": (
        "Source-specific trigger, scope, priority, boundary, routing, and fallback examples."
    ),
    "Coding-Agent Workflow": (
        "Source-specific inspect, plan, edit, validate, report, and permission-boundary evidence."
    ),
    "Defensive Jailbreak Analysis": (
        "Direct evidence for safely classifying jailbreak mechanisms without "
        "improving or reproducing operational attack prompts."
    ),
}

PATTERN_KEYWORDS = {
    "Structured Output / Extraction": (
        "structured output", "extraction", "extract", "json", "schema", "classification",
    ),
    "Grounded Research": (
        "rag",
        "retrieval",
        "citation",
        "cite your sources",
        "hallucination",
        "document question",
    ),
    "Evaluation Rubric": (
        "evaluation",
        "evaluator",
        "rubric",
        "testing",
        "promptops",
        "prompt quality",
        "quality of a prompt",
    ),
    "Persistent Project Instruction": (
        "project instruction",
        "custom instruction",
        "system prompt",
        "cursor rules",
        ".cursorrules",
        "instruction layering",
    ),
    "Coding-Agent Workflow": (
        "coding agent",
        "coding assistant",
        "code editing",
        "software-generation agent",
        "cursor",
        "cline",
        "aider",
        "continue.dev",
        "gpt engineer",
        "open interpreter",
        "roo code",
        "codex",
    ),
    "Defensive Jailbreak Analysis": (
        "jailbreak", "prompt injection", "dan", "adversarial", "safety",
    ),
}

LARGE_COLLECTION_MARKERS = (
    "awesome",
    "collection",
    "library",
    "prompt pack",
    "roundup",
    "marketplace",
    "topic",
    "directory",
    "100 prompts",
    "100000",
)


# These are evidence-backed, current-repository mismatches. They are reported,
# not auto-fixed. Each check is conditional, so it disappears once the index is
# reviewed and corrected.
KNOWN_INDEX_LABEL_MISMATCHES = (
    {
        "pattern": "Grounded Research",
        "source_id": "PR111",
        "actual_name_contains": "Prompt Evaluator",
        "wrong_label_contains": "RAG / retrieval quality discussion",
        "message": (
            "Index labels PR111 as a RAG/retrieval source, but corpus PR111 is "
            "the 10x Prompt Evaluator; corpus PR109 is the RAG entry."
        ),
    },
    {
        "pattern": "Structured Output / Extraction",
        "source_id": "PR062",
        "actual_name_contains": "Anthropic Prompt Engineering Overview",
        "wrong_label_contains": "OpenAI Cookbook",
        "message": (
            "Index labels PR062 as OpenAI Cookbook, but corpus PR062 is the "
            "Anthropic Prompt Engineering Overview."
        ),
    },
    {
        "pattern": "Structured Output / Extraction",
        "source_id": "PR064",
        "actual_name_contains": "OpenAI Prompt Examples",
        "wrong_label_contains": "Learn Prompting",
        "message": (
            "Index labels PR064 as Learn Prompting, but corpus PR064 is OpenAI "
            "Prompt Examples / Cookbook."
        ),
    },
    {
        "pattern": "Evaluation Rubric",
        "source_id": "PR108",
        "actual_name_contains": "Pattern-Matching",
        "wrong_label_contains": "Prompt evaluation rubric discussion",
        "message": (
            "Index labels PR108 as a prompt-evaluation rubric discussion, but "
            "corpus PR108 is a metacognition/pattern-matching claim."
        ),
    },
    {
        "pattern": "Evaluation Rubric",
        "source_id": "PR109",
        "actual_name_contains": "RAG",
        "wrong_label_contains": "Prompt testing / evaluation discussion",
        "message": (
            "Index labels PR109 as prompt testing/evaluation, but corpus PR109 "
            "is the RAG/hallucination-control entry."
        ),
    },
    {
        "pattern": "Evaluation Rubric",
        "source_id": "PR110",
        "actual_name_contains": "Evaluate the Quality",
        "wrong_label_contains": "Prompt versioning discussion",
        "message": (
            "Index labels PR110 as prompt versioning, but corpus PR110 is the "
            "prompt-quality evaluation discussion."
        ),
    },
)

KNOWN_SUSPICIOUS_LINKS = (
    {
        "pattern": "Grounded Research",
        "source_ids": ("PR039", "PR040", "PR106"),
        "message": (
            "Grounded Research still cites student use-case/roundup entries and "
            "an anti-hallucination prompt. Review PR039, PR040, and PR106 against "
            "original sources before assigning relation strengths."
        ),
    },
    {
        "pattern": "Evaluation Rubric",
        "source_ids": ("PR108", "PR109", "PR110", "PR118"),
        "message": (
            "Evaluation Rubric includes metacognition and RAG entries, while the "
            "explicit evaluator entry PR111 is absent. PR118 is at most indirect."
        ),
    },
)


class PipelineError(Exception):
    """User-facing validation or pipeline failure."""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def pipeline_draft_has_lesson(source_id: str) -> bool:
    path = DRAFTS_DIR / f"{source_id}.md"
    if not path.is_file():
        return False
    text = read_text(path)
    return all(
        re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE | re.IGNORECASE)
        for heading in ("Pattern lesson", "Mechanism", "Failure mode", "Reusable move")
    )


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing JSON file: {relative(path)}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(
            f"Invalid JSON in {relative(path)} at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def extract_bold_field(body: str, field: str) -> str | None:
    match = re.search(
        rf"^-\s*\*\*{re.escape(field)}:\*\*\s*(.*?)\s*$",
        body,
        re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def extract_section(body: str, heading: str) -> str | None:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        body,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def extract_evidence_note(body: str) -> str | None:
    section = extract_section(body, "Evidence note")
    if section:
        return " ".join(line.strip(" -") for line in section.splitlines() if line.strip())

    match = re.search(
        r"^-\s*\*\*Evidence note:\*\*\s*(.*?)(?=^-\s*\*\*[^\n]+:\*\*|\Z)",
        body,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    return " ".join(line.strip(" -") for line in match.group(1).splitlines() if line.strip()) or None


def extract_tags(body: str) -> list[str]:
    value = extract_bold_field(body, "Tags") or extract_section(body, "Tags") or ""
    tags = re.findall(r"`([^`]+)`", value)
    if not tags and value:
        tags = [part.strip() for part in value.split(",") if part.strip()]
    return tags


def parse_corpus() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in CORPUS_FILES:
        if not path.exists():
            continue
        text = read_text(path)
        matches = list(ENTRY_HEADING_RE.finditer(text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end() : end]
            source_id = match.group(1)
            heading_name = (match.group(2) or "").strip()
            name = extract_bold_field(body, "Name") or heading_name or source_id
            source_url = extract_bold_field(body, "Source URL")
            source_status = extract_bold_field(body, "Source status") or "unverified"
            source_type = extract_bold_field(body, "Type")
            lesson_parts = {
                "pattern_lesson": extract_section(body, "Pattern lesson")
                or extract_bold_field(body, "Pattern lesson"),
                "mechanism": extract_section(body, "Mechanism")
                or extract_bold_field(body, "Mechanism"),
                "failure_mode": extract_section(body, "Failure mode")
                or extract_bold_field(body, "Failure mode"),
                "reusable_move": extract_section(body, "Reusable move")
                or extract_bold_field(body, "Reusable move"),
            }
            entries.append(
                {
                    "source_id": source_id,
                    "name": name,
                    "source_url": source_url,
                    "source_status": source_status,
                    "source_type": source_type,
                    "tags": extract_tags(body),
                    "evidence_note": extract_evidence_note(body),
                    "lesson_present": all(bool(value) for value in lesson_parts.values()),
                    "lesson": lesson_parts,
                    "corpus_file": relative(path),
                    "corpus_line": text.count("\n", 0, match.start()) + 1,
                }
            )
    return entries


def expand_pr_ranges(text: str) -> list[str]:
    result: list[str] = []
    for match in PR_RANGE_RE.finditer(text):
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        if end < start or end - start > 200:
            continue
        result.extend(f"PR{number:03d}" for number in range(start, end + 1))
    return result


def parse_pattern_index() -> dict[str, Any]:
    text = read_text(PATTERN_INDEX_PATH)
    headings = list(PATTERN_HEADING_RE.finditer(text))
    patterns: dict[str, list[str]] = {}
    labels: dict[tuple[str, str], str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.end() : end]
        pattern = heading.group(1).strip()
        related_match = re.search(
            r"\*\*Related source entries\*\*\s*(.*?)(?=^---\s*$|\Z)",
            section,
            re.MULTILINE | re.DOTALL,
        )
        if not related_match:
            patterns[pattern] = []
            continue
        related_block = related_match.group(1)
        ids: list[str] = []
        for line in related_block.splitlines():
            line_ids = expand_pr_ranges(line)
            ids.extend(line_ids)
            if not line_ids:
                continue
            label_match = re.search(r"PR\d{3}(?:\s*[–-]\s*PR?\d{3})?\s+[—-]\s+(.+)", line)
            label = label_match.group(1).strip() if label_match else ""
            for source_id in line_ids:
                labels[(pattern, source_id)] = label
        patterns[pattern] = sorted(set(ids))
    return {
        "text": text,
        "patterns": patterns,
        "labels": labels,
        "all_refs": sorted(set(expand_pr_ranges(text))),
    }


def reverse_pattern_map(patterns: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for pattern, source_ids in patterns.items():
        for source_id in source_ids:
            result[source_id].append(pattern)
    return {source_id: sorted(values) for source_id, values in result.items()}


def source_search_text(source: dict[str, Any]) -> str:
    values = [
        source.get("name"),
        source.get("source_url"),
        source.get("source_status"),
        source.get("source_type"),
        " ".join(source.get("tags") or []),
    ]
    return " ".join(str(value or "") for value in values).lower()


def keyword_in_text(keyword: str, text: str) -> bool:
    if keyword.isalnum():
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
    return keyword in text


def inferred_weak_patterns(source: dict[str, Any]) -> list[str]:
    text = source_search_text(source)
    return sorted(
        pattern
        for pattern, keywords in PATTERN_KEYWORDS.items()
        if any(keyword_in_text(keyword, text) for keyword in keywords)
    )


def is_large_collection(source: dict[str, Any]) -> bool:
    text = source_search_text(source)
    return any(marker in text for marker in LARGE_COLLECTION_MARKERS)


def primary_source_score(source: dict[str, Any]) -> int:
    text = source_search_text(source)
    url = normalized_url(source.get("source_url"))
    official_markers = (
        "official", "documentation", "docs", "paper", "research paper",
        "original repository", "openai.com", "anthropic.com", "arxiv.org",
    )
    if any(marker in text for marker in official_markers):
        return 3
    if "github.com/" in url and "/topics/" not in url and not is_large_collection(source):
        return 2
    return 0


def specificity_score(source: dict[str, Any]) -> int:
    if is_large_collection(source):
        return 0
    text = source_search_text(source)
    concrete = ("workflow", "agent", "skill", "prompt", "rubric", "evaluator", "rag")
    return 2 if any(marker in text for marker in concrete) else 1


def duplicate_metadata(source_id: str) -> tuple[str, str | None, str | None]:
    if source_id in DISTINCT_DUPLICATE_IDS:
        return "distinct", None, "Same URL, but a different prompt, rule, or case."
    if source_id in DUPLICATE_ALIASES:
        canonical = DUPLICATE_ALIASES[source_id]
        return "alias", canonical, "Same underlying evidence as the canonical entry."
    if source_id in set(DUPLICATE_ALIASES.values()):
        return "canonical", source_id, "Canonical entry for identical underlying evidence."
    if source_id in DEFERRED_DUPLICATE_IDS:
        return "deferred", None, "The shared URL does not establish whether the evidence is identical."
    return "unique", None, None


def make_manifest() -> dict[str, Any]:
    corpus_entries = parse_corpus()
    index_data = parse_pattern_index()
    related = reverse_pattern_map(index_data["patterns"])
    sources: list[dict[str, Any]] = []
    for entry in sorted(corpus_entries, key=lambda item: item["source_id"]):
        lesson_present = entry["lesson_present"] or pipeline_draft_has_lesson(entry["source_id"])
        upgrade_status = "lesson-draft" if lesson_present else "cataloged"
        referenced_patterns = related.get(entry["source_id"], [])
        inferred_patterns = inferred_weak_patterns(entry)
        related_patterns = sorted(set(referenced_patterns + inferred_patterns))
        pattern_link_status = (
            "referenced" if referenced_patterns
            else "candidate" if inferred_patterns
            else "unlinked"
        )
        duplicate_status, canonical_source_id, duplicate_note = duplicate_metadata(
            entry["source_id"]
        )
        sources.append(
            {
                "source_id": entry["source_id"],
                "name": entry["name"],
                "source_url": entry["source_url"],
                "source_status": entry["source_status"],
                "upgrade_status": upgrade_status,
                "pattern_link_status": pattern_link_status,
                "automation_status": (
                    "deferred" if duplicate_status == "deferred" else "pending"
                ),
                "deferred_reasons": (
                    ["duplicate-classification-uncertain"]
                    if duplicate_status == "deferred" else []
                ),
                "last_automation_run": None,
                "automation_attempts": 0,
                "duplicate_status": duplicate_status,
                "canonical_source_id": canonical_source_id,
                "duplicate_note": duplicate_note,
                "related_patterns": related_patterns,
                "referenced_patterns": referenced_patterns,
                "confirmed_patterns": [],
                "evidence_relation": "unverified",
                "evidence_note": entry["evidence_note"],
                "verified_at": None,
                "tested": False,
                "source_checked": False,
                "checked_at": None,
                "verification_basis": None,
                "lesson_present": lesson_present,
                "test_evidence": None,
                "source_type": entry["source_type"],
                "tags": entry["tags"],
                "corpus_file": entry["corpus_file"],
                "corpus_line": entry["corpus_line"],
            }
        )
    return {
        "schema_version": 1,
        "upgrade_status_values": list(UPGRADE_STATUSES),
        "pattern_link_status_values": list(PATTERN_LINK_STATUSES),
        "automation_status_values": list(AUTOMATION_STATUSES),
        "duplicate_status_values": list(DUPLICATE_STATUSES),
        "evidence_relation_values": list(EVIDENCE_RELATIONS),
        "source_count": len(sources),
        "sources": sources,
    }


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_json(path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
        raise PipelineError(f"{relative(path)} must contain a sources array.")
    manifest.setdefault("automation_status_values", list(AUTOMATION_STATUSES))
    manifest.setdefault("duplicate_status_values", list(DUPLICATE_STATUSES))
    for source in manifest["sources"]:
        source.setdefault("automation_status", "pending")
        source.setdefault("deferred_reasons", [])
        source.setdefault("last_automation_run", None)
        source.setdefault("automation_attempts", 0)
        duplicate_status, canonical_source_id, duplicate_note = duplicate_metadata(
            str(source.get("source_id"))
        )
        source.setdefault("duplicate_status", duplicate_status)
        source.setdefault("canonical_source_id", canonical_source_id)
        source.setdefault("duplicate_note", duplicate_note)
        if duplicate_status == "deferred" and source["automation_status"] == "pending":
            source["automation_status"] = "deferred"
            source["deferred_reasons"] = ["duplicate-classification-uncertain"]
    return manifest


def issue(
    issues: list[dict[str, Any]],
    severity: str,
    code: str,
    file: str,
    message: str,
    source_id: str | None = None,
    pattern: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "file": file,
        "message": message,
    }
    if source_id:
        payload["source_id"] = source_id
    if pattern:
        payload["pattern"] = pattern
    issues.append(payload)


def normalized_url(url: str | None) -> str:
    return (url or "").strip().rstrip("/").lower()


def validate_repository(manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    corpus_entries = parse_corpus()
    index_data = parse_pattern_index()
    corpus_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in corpus_entries:
        corpus_by_id[entry["source_id"]].append(entry)

    manifest_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in manifest["sources"]:
        source_id = source.get("source_id")
        manifest_by_id[str(source_id)].append(source)

    for source_id, entries in sorted(corpus_by_id.items()):
        if len(entries) > 1:
            locations = ", ".join(
                f"{entry['corpus_file']}:{entry['corpus_line']}" for entry in entries
            )
            issue(
                issues,
                "error",
                "duplicate-pr-id",
                locations,
                f"Duplicate corpus ID {source_id}.",
                source_id,
            )

    for source_id, entries in sorted(manifest_by_id.items()):
        if len(entries) > 1:
            issue(
                issues,
                "error",
                "duplicate-manifest-id",
                relative(MANIFEST_PATH),
                f"Manifest contains {len(entries)} records for {source_id}.",
                source_id,
            )

    corpus_ids = set(corpus_by_id)
    manifest_ids = set(manifest_by_id)
    for source_id in sorted(corpus_ids - manifest_ids):
        entry = corpus_by_id[source_id][0]
        issue(
            issues,
            "error",
            "missing-manifest-source",
            entry["corpus_file"],
            f"Corpus source {source_id} is missing from the manifest.",
            source_id,
        )

    for source_id in sorted(set(index_data["all_refs"]) - corpus_ids):
        issue(
            issues,
            "error",
            "missing-index-source",
            relative(PATTERN_INDEX_PATH),
            f"Pattern index references {source_id}, which is absent from the corpus.",
            source_id,
        )

    urls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in corpus_entries:
        key = normalized_url(entry.get("source_url"))
        if key:
            urls[key].append(entry)
    for url, entries in sorted(urls.items()):
        if len(entries) > 1:
            ids = ", ".join(entry["source_id"] for entry in entries)
            files = sorted(set(entry["corpus_file"] for entry in entries))
            issue(
                issues,
                "warning",
                "duplicate-source-url",
                ", ".join(files),
                f"Duplicate source URL used by {ids}: {url}",
            )

    canonical_patterns = set(index_data["patterns"])
    for source_id, sources in sorted(manifest_by_id.items()):
        source = sources[0]
        status = source.get("upgrade_status")
        link_status = source.get("pattern_link_status")
        automation_status = source.get("automation_status")
        duplicate_status = source.get("duplicate_status")
        relation = source.get("evidence_relation")
        source_file = source.get("corpus_file") or relative(MANIFEST_PATH)

        if status not in UPGRADE_STATUSES:
            issue(
                issues,
                "error",
                "invalid-upgrade-status",
                source_file,
                f"Invalid upgrade_status {status!r} for {source_id}.",
                source_id,
            )
            continue
        if link_status not in PATTERN_LINK_STATUSES:
            issue(
                issues,
                "error",
                "invalid-pattern-link-status",
                source_file,
                f"Invalid pattern_link_status {link_status!r} for {source_id}.",
                source_id,
            )
        if automation_status not in AUTOMATION_STATUSES:
            issue(
                issues, "error", "invalid-automation-status", source_file,
                f"Invalid automation_status {automation_status!r} for {source_id}.", source_id,
            )
        if duplicate_status not in DUPLICATE_STATUSES:
            issue(
                issues, "error", "invalid-duplicate-status", source_file,
                f"Invalid duplicate_status {duplicate_status!r} for {source_id}.", source_id,
            )
        if duplicate_status == "alias":
            canonical_id = source.get("canonical_source_id")
            canonical = manifest_by_id.get(str(canonical_id), [])
            if not canonical or normalized_url(canonical[0].get("source_url")) != normalized_url(
                source.get("source_url")
            ):
                issue(
                    issues, "error", "invalid-canonical-alias", source_file,
                    f"{source_id} alias does not point to a canonical entry with the same URL.",
                    source_id,
                )
        deferred_reasons = source.get("deferred_reasons")
        if automation_status == "deferred" and (
            not isinstance(deferred_reasons, list) or not deferred_reasons
        ):
            issue(
                issues, "error", "deferred-without-reason", source_file,
                f"{source_id} is deferred without a reason.", source_id,
            )
        if relation not in EVIDENCE_RELATIONS:
            issue(
                issues,
                "error",
                "invalid-evidence-relation",
                source_file,
                f"Invalid evidence_relation {relation!r} for {source_id}.",
                source_id,
            )
        if relation in {"direct", "partial"} and not source.get("evidence_note"):
            issue(
                issues,
                "error",
                "missing-evidence-note",
                source_file,
                f"{source_id} is {relation} but has no evidence_note.",
                source_id,
            )
        if status in {"verified", "tested"}:
            if not source.get("source_checked") or not source.get("checked_at"):
                issue(
                    issues,
                    "error",
                    "unchecked-status-promotion",
                    source_file,
                    f"{source_id} is {status} without source_checked and checked_at.",
                    source_id,
                )
        corpus_has_lesson = pipeline_draft_has_lesson(source_id) or bool(
            corpus_by_id.get(source_id) and corpus_by_id[source_id][0].get("lesson_present")
        )
        if status in {"lesson-draft", "verified", "tested"} and not corpus_has_lesson:
            issue(
                issues,
                "error",
                "lesson-draft-without-lesson",
                source_file,
                f"{source_id} is {status} but its corpus entry has no complete lesson fields.",
                source_id,
            )
        if status in {"verified", "tested"} or source.get("verified_at") is not None:
            note = str(source.get("evidence_note") or "")
            basis = source.get("verification_basis")
            if basis != "external-source" or not source.get("verified_at"):
                issue(
                    issues,
                    "error",
                    "verified-without-external-source",
                    source_file,
                    (
                        f"{source_id} is {status} without external-source basis "
                        "and verified_at."
                    ),
                    source_id,
                )
            if any(marker in note.lower() for marker in LOCAL_ONLY_MARKERS):
                issue(
                    issues,
                    "error",
                    "summary-only-verified",
                    source_file,
                    f"{source_id} is verified using a note that disclaims original-source checking.",
                    source_id,
                )
            if relation == "unverified":
                issue(
                    issues,
                    "error",
                    "verified-unverified-relation",
                    source_file,
                    f"{source_id} is {status} but evidence_relation is unverified.",
                    source_id,
                )
        if status == "tested":
            test_path = source.get("test_evidence")
            if not source.get("tested") or not test_path or not (ROOT / test_path).exists():
                issue(
                    issues,
                    "error",
                    "tested-without-evidence",
                    source_file,
                    f"{source_id} is tested without a valid test_evidence path.",
                    source_id,
                )
        related_patterns = source.get("related_patterns") or []
        referenced_patterns = source.get("referenced_patterns") or []
        confirmed_patterns = source.get("confirmed_patterns") or []
        if link_status == "unlinked" and related_patterns:
            issue(
                issues, "error", "unlinked-with-patterns", source_file,
                f"{source_id} is unlinked but has related patterns.", source_id,
            )
        if link_status == "candidate" and (not related_patterns or referenced_patterns):
            issue(
                issues, "error", "invalid-candidate-link", source_file,
                f"{source_id} candidate links require inferred patterns and no index references.",
                source_id,
            )
        if link_status == "referenced":
            actual_refs = set(reverse_pattern_map(index_data["patterns"]).get(source_id, []))
            if not referenced_patterns or set(referenced_patterns) != actual_refs:
                issue(
                    issues, "error", "stale-referenced-link", source_file,
                    f"{source_id} referenced_patterns do not match the current pattern index.",
                    source_id,
                )
        if link_status == "confirmed":
            if not confirmed_patterns or status not in {"verified", "tested"}:
                issue(
                    issues, "error", "unverified-confirmed-link", source_file,
                    f"{source_id} confirmed links require verified evidence and confirmed_patterns.",
                    source_id,
                )
        for pattern in related_patterns + referenced_patterns + confirmed_patterns:
            if pattern not in canonical_patterns:
                issue(
                    issues,
                    "error",
                    "unknown-pattern-link",
                    source_file,
                    f"{source_id} links to unknown pattern {pattern!r}.",
                    source_id,
                    pattern,
                )

        corpus_match = corpus_by_id.get(source_id, [])
        if corpus_match and normalized_url(source.get("source_url")) != normalized_url(
            corpus_match[0].get("source_url")
        ):
            issue(
                issues,
                "error",
                "manifest-url-mismatch",
                source_file,
                f"Manifest URL for {source_id} differs from the raw corpus URL.",
                source_id,
            )

    corpus_single = {source_id: values[0] for source_id, values in corpus_by_id.items()}
    for check in KNOWN_INDEX_LABEL_MISMATCHES:
        pattern_ids = index_data["patterns"].get(check["pattern"], [])
        entry = corpus_single.get(check["source_id"])
        current_label = index_data["labels"].get(
            (check["pattern"], check["source_id"]), ""
        )
        if (
            check["source_id"] in pattern_ids
            and entry
            and check["actual_name_contains"].lower() in entry["name"].lower()
            and check["wrong_label_contains"].lower() in current_label.lower()
        ):
            issue(
                issues,
                "error",
                "index-source-number-mismatch",
                relative(PATTERN_INDEX_PATH),
                check["message"],
                check["source_id"],
                check["pattern"],
            )

    verification_text = read_text(PATTERN_VERIFICATION_PATH)
    current_coding_ids = set(index_data["patterns"].get("Coding-Agent Workflow", []))
    stale_block = all(
        marker in verification_text
        for marker in (
            "- PR082 - Cursor Rules",
            "- PR083 - Cline",
            "- PR084 - Roo Code",
            "- PR085 - Open Interpreter",
        )
    )
    if stale_block and {"PR088", "PR091"}.issubset(current_coding_ids):
        issue(
            issues,
            "error",
            "stale-verification-reference",
            relative(PATTERN_VERIFICATION_PATH),
            (
                "Coding-agent verification still records the shifted PR082-PR088 "
                "mapping even though the current index uses PR086-PR093."
            ),
            pattern="Coding-Agent Workflow",
        )
    if (
        "The source list in the index appears stale or shifted" in verification_text
        and {"PR086", "PR087", "PR088", "PR089", "PR090", "PR091", "PR092", "PR093"}
        .intersection(current_coding_ids)
    ):
        issue(
            issues,
            "error",
            "stale-verification-conclusion",
            relative(PATTERN_VERIFICATION_PATH),
            (
                "Verification says the current coding-agent index is stale, but "
                "the index was subsequently corrected; preserve this as history or update it."
            ),
            pattern="Coding-Agent Workflow",
        )

    for check in KNOWN_SUSPICIOUS_LINKS:
        current = set(index_data["patterns"].get(check["pattern"], []))
        if current.intersection(check["source_ids"]):
            issue(
                issues,
                "warning",
                "suspicious-pattern-link",
                relative(PATTERN_INDEX_PATH),
                check["message"],
                pattern=check["pattern"],
            )

    if (
        "Only the current repository corpus text was used" in verification_text
        and "No source URLs were opened" in verification_text
    ):
        issue(
            issues,
            "warning",
            "local-only-pattern-verification",
            relative(PATTERN_VERIFICATION_PATH),
            (
                "Pattern verification explicitly used local summaries without "
                "opening source URLs; it cannot promote manifest sources to verified."
            ),
        )

    issues.sort(
        key=lambda item: (
            0 if item["severity"] == "error" else 1,
            item["code"],
            item.get("source_id", ""),
            item["message"],
        )
    )
    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    return {
        "schema_version": 1,
        "manifest": relative(MANIFEST_PATH),
        "corpus_entries": len(corpus_entries),
        "manifest_sources": len(manifest["sources"]),
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
    }


def print_validation_report(report: dict[str, Any]) -> None:
    for item in report["issues"]:
        location = item["file"]
        if item.get("source_id"):
            location += f" [{item['source_id']}]"
        if item.get("pattern"):
            location += f" [{item['pattern']}]"
        print(f"{item['severity'].upper()} {item['code']}: {location}: {item['message']}")
    print(
        f"SUMMARY corpus={report['corpus_entries']} manifest={report['manifest_sources']} "
        f"errors={report['errors']} warnings={report['warnings']}"
    )


def command_init(args: argparse.Namespace) -> int:
    if MANIFEST_PATH.exists() and not args.force:
        raise PipelineError(
            f"{relative(MANIFEST_PATH)} already exists; use --force only to rebuild it."
        )
    manifest = make_manifest()
    write_json(MANIFEST_PATH, manifest)
    print(f"WROTE {relative(MANIFEST_PATH)} sources={manifest['source_count']}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    report = validate_repository(manifest)
    print_validation_report(report)
    if args.report:
        report_path = (ROOT / args.report).resolve() if not Path(args.report).is_absolute() else Path(args.report)
        try:
            report_path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise PipelineError("Report path must stay inside the repository.") from exc
        write_json(report_path, report)
        print(f"WROTE {relative(report_path)}")
    return 1 if report["errors"] else 0


def duplicate_url_ids(manifest: dict[str, Any]) -> set[str]:
    groups: dict[str, list[str]] = defaultdict(list)
    for source in manifest["sources"]:
        url = normalized_url(source.get("source_url"))
        if url:
            groups[url].append(source.get("source_id"))
    return {
        source_id
        for source_ids in groups.values()
        if len(source_ids) > 1
        for source_id in source_ids
    }


def has_automatic_verified_evidence(manifest: dict[str, Any], pattern: str) -> bool:
    return any(
        source.get("automation_status") == "applied"
        and source.get("upgrade_status") in {"verified", "tested"}
        and source.get("evidence_relation") in {"direct", "partial"}
        and pattern in (source.get("related_patterns") or [])
        for source in manifest["sources"]
    )


def select_priority_pattern_gaps(
    manifest: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for pattern in PRIORITY_PATTERN_GAPS:
        if len(selected) >= limit:
            break
        if has_automatic_verified_evidence(manifest, pattern):
            continue
        candidates = []
        for source in manifest["sources"]:
            if pattern not in (source.get("related_patterns") or []):
                continue
            if source.get("duplicate_status") in {"alias", "deferred"}:
                continue
            automation = source.get("automation_status")
            status = source.get("upgrade_status")
            attempts = int(source.get("automation_attempts") or 0)
            retry_draft = (
                status == "lesson-draft"
                and automation in {"applied", "deferred"}
                and attempts < 1
            )
            pending = automation == "pending" and status in {"cataloged", "lesson-draft"}
            if retry_draft or pending:
                candidates.append(source)
        candidates.sort(
            key=lambda source: (
                0 if source.get("upgrade_status") == "lesson-draft" else 1,
                (
                    PREFERRED_PATTERN_SOURCES[pattern].index(source.get("source_id"))
                    if source.get("source_id") in PREFERRED_PATTERN_SOURCES[pattern]
                    else len(PREFERRED_PATTERN_SOURCES[pattern])
                ),
                -primary_source_score(source),
                -specificity_score(source),
                source.get("source_id", ""),
            )
        )
        if not candidates:
            continue
        source = candidates[0]
        selected.append(
            {
                "source_id": source.get("source_id"),
                "name": source.get("name"),
                "source_url": source.get("source_url"),
                "current_status": source.get("upgrade_status"),
                "pattern_link_status": (
                    "referenced"
                    if pattern in (source.get("referenced_patterns") or [])
                    else "candidate"
                ),
                "target_pattern": pattern,
                "gap": PATTERN_GAPS[pattern],
            }
        )
    return selected


def select_next(
    manifest: dict[str, Any],
    limit: int,
    include_duplicates: bool = False,
    strategy: str = "default",
) -> list[dict[str, Any]]:
    if limit < 1:
        raise PipelineError("--limit must be at least 1.")
    if strategy == "pattern-gaps":
        return select_priority_pattern_gaps(manifest, limit)
    candidates = []
    legacy_drafts = []
    for source in manifest["sources"]:
        status = source.get("upgrade_status")
        if source.get("automation_status") in {"applied", "deferred"}:
            continue
        if source.get("duplicate_status") in {"alias", "deferred"}:
            continue
        if status == "lesson-draft":
            legacy_drafts.append(source)
        elif status == "cataloged":
            candidates.append(source)
        else:
            continue
    def priority(source: dict[str, Any]) -> tuple[Any, ...]:
        weak_count = len(set(source.get("related_patterns") or []) & set(WEAK_PATTERNS))
        return (
            0 if weak_count else 1,
            -primary_source_score(source),
            -specificity_score(source),
            1 if is_large_collection(source) else 0,
            0 if source.get("related_patterns") else 1,
            source.get("source_id", ""),
        )

    candidates.sort(key=priority)
    legacy_drafts.sort(key=lambda source: source.get("source_id", ""))
    if strategy == "pattern-gaps":
        def pattern_priority(source: dict[str, Any], pattern: str) -> tuple[Any, ...]:
            text = source_search_text(source)
            keyword_hits = sum(
                1 for keyword in PATTERN_KEYWORDS[pattern] if keyword_in_text(keyword, text)
            )
            return (
                -primary_source_score(source),
                -keyword_hits,
                -specificity_score(source),
                1 if is_large_collection(source) else 0,
                0 if source.get("pattern_link_status") == "referenced" else 1,
                source.get("source_id", ""),
            )

        pattern_candidates = {
            pattern: sorted(
                [source for source in candidates if pattern in (source.get("related_patterns") or [])],
                key=lambda source, current=pattern: pattern_priority(source, current),
            )
            for pattern in WEAK_PATTERNS
        }
        selected: list[tuple[dict[str, Any], str]] = [
            (
                source,
                (source.get("related_patterns") or ["Unassigned"])[0],
            )
            for source in legacy_drafts[:limit]
        ]
        used: set[str] = {source["source_id"] for source, _ in selected}
        while len(selected) < limit:
            added = False
            for pattern in WEAK_PATTERNS:
                match = next(
                    (
                        source for source in pattern_candidates[pattern]
                        if source.get("source_id") not in used
                        and pattern in (source.get("related_patterns") or [])
                    ),
                    None,
                )
                if match is None:
                    continue
                selected.append((match, pattern))
                used.add(match["source_id"])
                added = True
                if len(selected) >= limit:
                    break
            if not added:
                break
        return [
            {
                "source_id": source.get("source_id"),
                "name": source.get("name"),
                "source_url": source.get("source_url"),
                "current_status": source.get("upgrade_status"),
                "pattern_link_status": (
                    "referenced"
                    if pattern in (source.get("referenced_patterns") or [])
                    else "candidate"
                ),
                "target_pattern": pattern,
                "gap": PATTERN_GAPS.get(
                    pattern,
                    "기존 Pattern lesson의 원문 근거와 reusable move를 독립적으로 재검토합니다.",
                ),
            }
            for source, pattern in selected
        ]
    if strategy != "default":
        raise PipelineError(f"Unknown next strategy: {strategy}")
    return [
        {
            "source_id": source.get("source_id"),
            "name": source.get("name"),
            "source_url": source.get("source_url"),
            "current_status": source.get("upgrade_status"),
            "possible_patterns": source.get("related_patterns") or [],
        }
        for source in (legacy_drafts + candidates)[:limit]
    ]


def command_next(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    print(
        json.dumps(
            select_next(manifest, args.limit, args.include_duplicates, args.strategy),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def require_nonempty_string(payload: dict[str, Any], field: str, context: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"{context}: {field} must be a non-empty string.")
    return value.strip()


def parse_iso_date(value: Any, field: str, context: str, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise PipelineError(f"{context}: {field} must be YYYY-MM-DD or null.")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise PipelineError(f"{context}: {field} must be YYYY-MM-DD.") from exc
    return value


def safe_repo_path(value: str, context: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise PipelineError(f"{context}: path must stay inside the repository.") from exc
    return path


def validate_apply_item(
    item: dict[str, Any],
    existing: dict[str, Any] | None,
    index_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str] | None]:
    source_id = require_nonempty_string(item, "source_id", "source")
    context = source_id
    if not ID_RE.fullmatch(source_id):
        raise PipelineError(f"{context}: source_id must match PR###.")
    name = require_nonempty_string(item, "name", context)
    source_url = require_nonempty_string(item, "source_url", context)
    source_status = require_nonempty_string(item, "source_status", context)
    status = require_nonempty_string(item, "upgrade_status", context)
    link_status = require_nonempty_string(item, "pattern_link_status", context)
    relation = require_nonempty_string(item, "evidence_relation", context)
    if status not in UPGRADE_STATUSES:
        raise PipelineError(f"{context}: invalid upgrade_status {status!r}.")
    if relation not in EVIDENCE_RELATIONS:
        raise PipelineError(f"{context}: invalid evidence_relation {relation!r}.")
    if link_status not in PATTERN_LINK_STATUSES:
        raise PipelineError(f"{context}: invalid pattern_link_status {link_status!r}.")

    if existing:
        current_status = existing.get("upgrade_status", "cataloged")
        if STATUS_RANK[status] < STATUS_RANK.get(current_status, 0):
            raise PipelineError(
                f"{context}: status cannot move backward from {current_status} to {status}."
            )
        if normalized_url(existing.get("source_url")) != normalized_url(source_url) and not item.get(
            "allow_source_url_change"
        ):
            raise PipelineError(
                f"{context}: source_url differs from manifest; set allow_source_url_change true "
                "only after reviewing the correction."
            )

    related_patterns = item.get("related_patterns")
    if not isinstance(related_patterns, list) or not all(
        isinstance(value, str) and value.strip() for value in related_patterns
    ):
        raise PipelineError(f"{context}: related_patterns must be an array of names.")
    related_patterns = sorted(set(value.strip() for value in related_patterns))
    index_refs = set(reverse_pattern_map(index_data["patterns"]).get(source_id, []))
    if link_status == "unlinked" and related_patterns:
        raise PipelineError(f"{context}: unlinked cannot have related_patterns.")
    if link_status == "candidate" and (not related_patterns or index_refs):
        raise PipelineError(
            f"{context}: candidate requires possible patterns and no current index reference."
        )
    if link_status == "referenced" and not index_refs:
        raise PipelineError(f"{context}: referenced requires a current pattern-index reference.")

    evidence_note = item.get("evidence_note")
    if evidence_note is not None and (not isinstance(evidence_note, str) or not evidence_note.strip()):
        raise PipelineError(f"{context}: evidence_note must be a non-empty string or null.")
    evidence_note = evidence_note.strip() if isinstance(evidence_note, str) else None
    if relation in {"direct", "partial"} and not evidence_note:
        raise PipelineError(f"{context}: {relation} requires evidence_note.")

    source_checked = item.get("source_checked", False)
    if not isinstance(source_checked, bool):
        raise PipelineError(f"{context}: source_checked must be boolean.")
    checked_at = parse_iso_date(item.get("checked_at"), "checked_at", context)
    verified_at = parse_iso_date(item.get("verified_at"), "verified_at", context)
    verification_basis = item.get("verification_basis")
    if verification_basis not in {None, "external-source", "corpus-summary", "pattern-document"}:
        raise PipelineError(f"{context}: invalid verification_basis.")

    lesson = item.get("lesson")
    lesson_fields = ("pattern_lesson", "mechanism", "failure_mode", "reusable_move")
    if lesson is not None and not isinstance(lesson, dict):
        raise PipelineError(f"{context}: lesson must be an object or null.")
    if lesson:
        for field in lesson_fields:
            require_nonempty_string(lesson, field, f"{context}.lesson")

    if status in {"verified", "tested"}:
        if not source_checked or not checked_at or not evidence_note:
            raise PipelineError(
                f"{context}: {status} requires source_checked, checked_at, and evidence_note."
            )
    if status == "lesson-draft" and not lesson:
        raise PipelineError(f"{context}: {status} requires a complete lesson object.")
    if status in {"verified", "tested"} or verified_at is not None:
        if verification_basis != "external-source" or not verified_at:
            raise PipelineError(
                f"{context}: verified or later requires external-source basis and verified_at."
            )
        if relation == "unverified":
            raise PipelineError(f"{context}: verified or later cannot use unverified relation.")
        lowered_note = (evidence_note or "").lower()
        if any(marker in lowered_note for marker in LOCAL_ONLY_MARKERS):
            raise PipelineError(
                f"{context}: evidence_note disclaims original-source checking; cannot verify."
            )
    if link_status == "confirmed" and status not in {"verified", "tested"}:
        raise PipelineError(f"{context}: confirmed pattern links require verified evidence.")

    tested = item.get("tested", False)
    if not isinstance(tested, bool):
        raise PipelineError(f"{context}: tested must be boolean.")
    test_evidence = item.get("test_evidence")
    if status == "tested":
        if not tested or not isinstance(test_evidence, str):
            raise PipelineError(f"{context}: tested status requires tested=true and test_evidence.")
        if not safe_repo_path(test_evidence, context).is_file():
            raise PipelineError(f"{context}: test_evidence does not exist: {test_evidence}")

    base = copy.deepcopy(existing) if existing else {
        "source_id": source_id,
        "tags": [],
        "corpus_file": None,
        "corpus_line": None,
        "source_type": None,
        "lesson_present": False,
    }
    base.update(
        {
            "source_id": source_id,
            "name": name,
            "source_url": source_url,
            "source_status": source_status,
            "upgrade_status": status,
            "pattern_link_status": link_status,
            "related_patterns": related_patterns,
            "referenced_patterns": sorted(index_refs),
            "confirmed_patterns": related_patterns if link_status == "confirmed" else [],
            "evidence_relation": relation,
            "evidence_note": evidence_note,
            "verified_at": verified_at,
            "tested": tested,
            "source_checked": source_checked,
            "checked_at": checked_at,
            "verification_basis": verification_basis,
            "lesson_present": bool(lesson) or bool(base.get("lesson_present")),
            "test_evidence": test_evidence,
        }
    )
    if isinstance(item.get("source_type"), str):
        base["source_type"] = item["source_type"].strip()
    if isinstance(item.get("tags"), list):
        base["tags"] = sorted(set(str(tag).strip() for tag in item["tags"] if str(tag).strip()))

    lesson_text: dict[str, str] | None = None
    if lesson:
        lesson_text = {field: str(lesson[field]).strip() for field in lesson_fields}
        for optional in ("short_excerpt", "structure_summary", "safety_note"):
            if isinstance(lesson.get(optional), str) and lesson[optional].strip():
                lesson_text[optional] = lesson[optional].strip()
    return base, lesson_text


def render_lesson_draft(source: dict[str, Any], lesson: dict[str, str]) -> str:
    patterns = ", ".join(source["related_patterns"]) or "Unassigned"
    return f"""# {source['source_id']} — {source['name']}

Status: {source['upgrade_status']}
Source URL: {source['source_url']}
Source status: {source['source_status']}
Checked at: {source.get('checked_at') or 'null'}
Verified at: {source.get('verified_at') or 'null'}
Evidence relation: {source['evidence_relation']}
Related patterns: {patterns}

## Evidence note

{source.get('evidence_note') or 'Unverified.'}

## Short excerpt

{lesson.get('short_excerpt', 'Not supplied.')}

## Structure summary

{lesson.get('structure_summary', 'Not supplied.')}

## Pattern lesson

{lesson['pattern_lesson']}

## Mechanism

{lesson['mechanism']}

## Failure mode

{lesson['failure_mode']}

## Reusable move

{lesson['reusable_move']}

## Safety / reproduction note

{lesson.get('safety_note', 'Review source rights and safety boundaries before reuse.')}
"""


def render_index_candidates(
    batch_id: str,
    applied: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Pattern Index Candidates — {batch_id}",
        "",
        "This file is a review queue. It does not modify PATTERN_LESSONS_INDEX.md.",
        "",
    ]
    for source in applied:
        eligible = bool(source.get("verified_at")) and source["evidence_relation"] != "unverified"
        lines.extend(
            [
                f"## {source['source_id']} — {source['name']}",
                "",
                f"- Status: {source['upgrade_status']}",
                f"- Evidence relation: {source['evidence_relation']}",
                f"- Related patterns: {', '.join(source['related_patterns']) or 'Unassigned'}",
                f"- Index eligibility: {'REVIEW' if eligible else 'HOLD — not verified'}",
                f"- Evidence note: {source.get('evidence_note') or 'null'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def command_apply(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = (ROOT / input_path).resolve()
    try:
        input_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise PipelineError("Batch result path must stay inside the repository.") from exc
    payload = load_json(input_path)
    if not isinstance(payload, dict):
        raise PipelineError("Batch result must be a JSON object.")
    batch_id = require_nonempty_string(payload, "batch_id", "batch")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", batch_id):
        raise PipelineError("batch_id may contain only letters, numbers, dot, underscore, and hyphen.")
    items = payload.get("sources")
    if not isinstance(items, list) or not items:
        raise PipelineError("Batch result must contain a non-empty sources array.")

    manifest = load_manifest()
    by_id = {source["source_id"]: source for source in manifest["sources"]}
    index_data = parse_pattern_index()
    updates: list[dict[str, Any]] = []
    drafts: dict[Path, str] = {}
    seen: set[str] = set()
    for raw_item in items:
        if not isinstance(raw_item, dict):
            raise PipelineError("Each sources item must be an object.")
        source_id = str(raw_item.get("source_id", ""))
        if source_id in seen:
            raise PipelineError(f"Batch contains duplicate source_id {source_id}.")
        seen.add(source_id)
        updated, lesson = validate_apply_item(raw_item, by_id.get(source_id), index_data)
        updates.append(updated)
        by_id[source_id] = updated
        if lesson:
            drafts[DRAFTS_DIR / f"{source_id}.md"] = render_lesson_draft(updated, lesson)

    candidate_path = INDEX_CANDIDATES_DIR / f"{batch_id}.md"
    if candidate_path.exists() and not args.overwrite:
        raise PipelineError(
            f"{relative(candidate_path)} exists; use --overwrite only after review."
        )

    new_manifest = copy.deepcopy(manifest)
    new_manifest["sources"] = sorted(by_id.values(), key=lambda source: source["source_id"])
    new_manifest["source_count"] = len(new_manifest["sources"])
    candidate_text = render_index_candidates(batch_id, updates)

    output_files = [relative(MANIFEST_PATH), relative(candidate_path)] + [
        relative(path) for path in sorted(drafts)
    ]
    if args.dry_run:
        print(json.dumps({"dry_run": True, "would_write": output_files}, indent=2))
        return 0

    write_json(MANIFEST_PATH, new_manifest)
    for path, content in drafts.items():
        atomic_write_text(path, content)
    atomic_write_text(candidate_path, candidate_text)
    print(json.dumps({"applied": len(updates), "files": output_files}, indent=2))
    return 0


def find_codex_executable() -> str:
    configured = os.environ.get("CODEX_BIN")
    if configured:
        return configured
    names = ("codex.cmd", "codex.exe", "codex") if os.name == "nt" else ("codex",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise PipelineError(
        "Codex CLI was not found. Install/sign in to Codex, or set CODEX_BIN to its executable."
    )


def build_codex_research_prompt(
    batch_id: str,
    selection: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> str:
    by_id = {source["source_id"]: source for source in manifest["sources"]}
    records = []
    for selected in selection:
        record = copy.deepcopy(by_id[selected["source_id"]])
        record["target_pattern"] = selected.get("target_pattern")
        record["target_gap"] = selected.get("gap")
        records.append(record)
    return f"""You are the evidence-research worker for a prompt corpus pipeline.

Return only JSON conforming to prompt-corpus/batch-result.schema.json. The exact
batch_id must be {batch_id!r}. Return exactly one source result for every selected
source_id and no others.

For every source_url, open the original page or original repository and inspect it.
Do not rely only on this repository's summary. Record only content directly visible
at that source. If the URL cannot be opened, set source_checked=false, checked_at=null,
verification_basis=null, evidence_relation="unverified", verified_at=null,
upgrade_status="cataloged", and lesson=null.

If the original source is visible, set source_checked=true and checked_at to today's
date. Write a concise evidence_note distinguishing directly observed content from
your synthesis. A lesson must contain all four fields: pattern_lesson, mechanism,
failure_mode, and reusable_move. Use lesson-draft unless the original source itself
provides enough direct evidence to justify verified. verified requires
verification_basis="external-source", a verified_at date, and a non-unverified
evidence relation. Never use confirmed for pattern_link_status; preserve referenced
when the manifest says referenced, otherwise use candidate or unlinked. Do not add a
pattern merely because it appears in a local summary. Do not edit repository files.

Selected records and target gaps:
{json.dumps(records, ensure_ascii=False, indent=2)}
"""


def invoke_codex_exec(
    prompt: str,
    output_path: Path,
    log_path: Path,
    schema_path: Path,
) -> None:
    codex = find_codex_executable()
    model = os.environ.get("CORPUS_PIPELINE_CODEX_MODEL", "gpt-5.5")
    command = [
        codex,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--model",
        model,
        "--sandbox",
        "read-only",
        "--cd",
        str(ROOT),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "--color",
        "never",
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        raise PipelineError(f"Could not start Codex CLI: {exc}") from exc
    atomic_write_text(log_path, completed.stdout or "")
    if completed.returncode != 0:
        raise PipelineError(
            f"codex exec failed with exit code {completed.returncode}; see {relative(log_path)}."
        )
    if not output_path.is_file():
        raise PipelineError(f"codex exec produced no result file: {relative(output_path)}")


def filter_generated_batch(
    payload: Any,
    batch_id: str,
    selection: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rejected: list[dict[str, str]] = []
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise PipelineError("Codex result is not a batch-result object with a sources array.")
    if payload.get("batch_id") != batch_id:
        raise PipelineError(
            f"Codex returned batch_id {payload.get('batch_id')!r}; expected {batch_id!r}."
        )
    selected_ids = {item["source_id"] for item in selection}
    returned_ids = [str(item.get("source_id", "")) for item in payload["sources"] if isinstance(item, dict)]
    for source_id in sorted(selected_ids - set(returned_ids)):
        rejected.append({"source_id": source_id, "reason": "Codex returned no result."})

    by_id = {source["source_id"]: source for source in manifest["sources"]}
    index_data = parse_pattern_index()
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in payload["sources"]:
        if not isinstance(raw_item, dict):
            rejected.append({"source_id": "unknown", "reason": "Result item is not an object."})
            continue
        source_id = str(raw_item.get("source_id", ""))
        try:
            if source_id not in selected_ids:
                raise PipelineError("Source was not selected by this run.")
            if source_id in seen:
                raise PipelineError("Duplicate result for the same source_id.")
            seen.add(source_id)
            if raw_item.get("pattern_link_status") == "confirmed":
                raise PipelineError("Pattern links require human confirmation; confirmed is not automatic.")
            if not raw_item.get("source_checked") and (
                raw_item.get("upgrade_status") != "cataloged"
                or raw_item.get("verified_at") is not None
                or raw_item.get("lesson") is not None
            ):
                raise PipelineError("Unchecked source cannot be promoted or produce a lesson.")
            validate_apply_item(raw_item, by_id.get(source_id), index_data)
            accepted.append(raw_item)
        except PipelineError as exc:
            rejected.append({"source_id": source_id or "unknown", "reason": str(exc)})
    return {"batch_id": batch_id, "sources": accepted}, rejected


def build_independent_review_prompt(batch_id: str, candidates: list[dict[str, Any]]) -> str:
    compact = [
        {
            "source_id": item["source_id"],
            "source_url": item["source_url"],
            "related_patterns": item["related_patterns"],
            "evidence_relation": item["evidence_relation"],
            "evidence_note": item.get("evidence_note"),
            "lesson": item.get("lesson"),
        }
        for item in candidates
    ]
    return f"""You are an independent evidence reviewer. This is a new session: do not
assume the writer's research was correct and do not use local corpus summaries as
evidence. Return only JSON conforming to
prompt-corpus/independent-review.schema.json with exact batch_id {batch_id!r} and
one review for every candidate source_id.

For each candidate, independently open source_url and inspect the original page or
original repository. Then assess the candidate. PASS only when all are true:
- the original source was actually accessible in this review;
- the source supports the proposed reusable_move without exaggeration;
- the evidence_note clearly separates observed facts from synthesis;
- the lesson contains no material omission or contradiction;
- evidence_relation is the best classification;
- supported_patterns exactly lists the patterns actually supported by this source.

Use FAIL for inaccessible sources, overstatement, missing evidence, source mismatch,
or unsupported reusable moves. Never infer support from the local source name or
tags. `direct` means the source explicitly teaches or demonstrates the move;
`partial` means it supports only part; `adjacent` means related but not evidence for
the move; `synthesized` means the move is chiefly the writer's interpretation.

Candidates:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""


def parse_independent_reviews(
    payload: Any,
    batch_id: str,
    source_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    problems: list[dict[str, str]] = []
    if not isinstance(payload, dict) or payload.get("batch_id") != batch_id:
        raise PipelineError("Independent review returned the wrong batch_id or object shape.")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        raise PipelineError("Independent review has no reviews array.")
    by_id: dict[str, dict[str, Any]] = {}
    for review in reviews:
        source_id = str(review.get("source_id", "")) if isinstance(review, dict) else "unknown"
        if not isinstance(review, dict):
            problems.append({"source_id": source_id, "reason": "review-invalid-object"})
        elif source_id not in source_ids:
            problems.append({"source_id": source_id, "reason": "review-unselected-source"})
        elif source_id in by_id:
            problems.append({"source_id": source_id, "reason": "review-duplicate"})
        else:
            by_id[source_id] = review
    for source_id in sorted(source_ids - set(by_id)):
        problems.append({"source_id": source_id, "reason": "review-missing"})
    return by_id, problems


def decide_automatic_application(
    selection: list[dict[str, Any]],
    writer_batch: dict[str, Any],
    writer_rejections: list[dict[str, str]],
    reviews: dict[str, dict[str, Any]],
    review_problems: list[dict[str, str]],
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    deferred: dict[str, list[str]] = defaultdict(list)
    for item in writer_rejections:
        reason = item["reason"]
        deferred[item["source_id"]].append(
            reason if reason in DEFERRED_REASON_LABELS else "writer-validation-failed"
        )
    for item in review_problems:
        deferred[item["source_id"]].append(item["reason"])
    writers = {item["source_id"]: item for item in writer_batch["sources"]}
    existing = {item["source_id"]: item for item in manifest["sources"]}
    index_data = parse_pattern_index()
    accepted: list[dict[str, Any]] = []
    for selected in selection:
        source_id = selected["source_id"]
        writer = writers.get(source_id)
        review = reviews.get(source_id)
        reasons = deferred[source_id]
        if writer is None:
            if not reasons:
                reasons.append("writer-result-missing")
            continue
        if not writer.get("source_checked") or not writer.get("checked_at"):
            reasons.append("writer-source-unchecked")
        if writer.get("verification_basis") != "external-source":
            reasons.append("external-source-record-missing")
        if not writer.get("evidence_note"):
            reasons.append("evidence-note-missing")
        if not writer.get("lesson") or writer.get("upgrade_status") == "cataloged":
            reasons.append("writer-lesson-missing")
        duplicate_status = existing.get(source_id, {}).get("duplicate_status")
        if duplicate_status == "deferred":
            reasons.append("duplicate-classification-uncertain")
        elif duplicate_status == "alias":
            reasons.append("duplicate-alias-not-processable")
        if review is None:
            if "review-missing" not in reasons:
                reasons.append("review-missing")
        else:
            if review.get("verdict") != "PASS":
                reasons.append("independent-review-failed")
            if not review.get("source_checked") or not review.get("checked_at"):
                reasons.append("reviewer-source-unchecked")
            if not review.get("reusable_move_supported"):
                reasons.append("reusable-move-unsupported")
            if not review.get("claims_match_source"):
                reasons.append("source-claim-mismatch")
            if not review.get("evidence_note_adequate"):
                reasons.append("evidence-note-inadequate")
            if writer.get("evidence_relation") != review.get("evidence_relation"):
                reasons.append("model-disagreement-relation")
            if set(writer.get("related_patterns") or []) != set(review.get("supported_patterns") or []):
                reasons.append("model-disagreement-patterns")
        try:
            validate_apply_item(writer, existing.get(source_id), index_data)
        except PipelineError:
            reasons.append("deterministic-validation-failed")
        deferred[source_id] = sorted(set(reasons))
        if not deferred[source_id]:
            if (
                writer.get("upgrade_status") == "lesson-draft"
                and writer.get("evidence_relation") in {"direct", "partial"}
            ):
                writer["upgrade_status"] = "verified"
                writer["verified_at"] = writer.get("checked_at")
            accepted.append(writer)
            deferred.pop(source_id, None)
    return accepted, dict(deferred)


def capture_apply(input_path: Path, dry_run: bool) -> tuple[int, str]:
    output = io.StringIO()
    args = argparse.Namespace(
        input=str(input_path), dry_run=dry_run, overwrite=False
    )
    with contextlib.redirect_stdout(output):
        result = command_apply(args)
    return result, output.getvalue().strip()


DEFERRED_REASON_LABELS = {
    "writer-execution-failed": "작성 세션 실행 실패",
    "writer-validation-failed": "작성 결과 형식 또는 상태 검증 실패",
    "writer-result-missing": "작성 결과 누락",
    "writer-source-unchecked": "작성 단계에서 원문 확인 실패",
    "external-source-record-missing": "외부 원문 확인 기록 누락",
    "evidence-note-missing": "근거 기록 누락",
    "writer-lesson-missing": "Pattern lesson 초안 누락",
    "duplicate-classification-uncertain": "중복 URL의 실제 근거 동일성 판단 불가",
    "duplicate-alias-not-processable": "canonical 항목으로 통합된 별칭",
    "review-invalid-object": "독립 검토 결과 형식 오류",
    "review-unselected-source": "선택되지 않은 자료의 검토 결과",
    "review-duplicate": "독립 검토 결과 중복",
    "review-missing": "독립 검토 결과 누락",
    "review-execution-failed": "독립 검토 세션 실행 실패",
    "review-validation-failed": "독립 검토 결과 형식 검증 실패",
    "independent-review-failed": "독립 검토 불통과",
    "reviewer-source-unchecked": "독립 검토에서 원문 확인 실패",
    "reusable-move-unsupported": "원문이 reusable move를 뒷받침하지 않음",
    "source-claim-mismatch": "원문과 작성 내용 불일치",
    "evidence-note-inadequate": "근거 기록이 불충분함",
    "model-disagreement-relation": "두 모델의 근거 관계 판정 불일치",
    "model-disagreement-patterns": "두 모델의 지원 패턴 판정 불일치",
    "deterministic-validation-failed": "URL·ID·필수 필드·상태 전이 검증 실패",
}


def pattern_evidence_status(manifest: dict[str, Any]) -> list[dict[str, str]]:
    statuses: list[dict[str, str]] = []
    for pattern in parse_pattern_index()["patterns"]:
        linked = [
            source for source in manifest["sources"]
            if pattern in (source.get("related_patterns") or [])
        ]
        auto_verified = [
            source for source in linked
            if source.get("automation_status") == "applied"
            and source.get("upgrade_status") in {"verified", "tested"}
            and source.get("evidence_relation") in {"direct", "partial"}
        ]
        auto_drafts = [
            source for source in linked
            if source.get("automation_status") == "applied"
            and source.get("upgrade_status") == "lesson-draft"
        ]
        existing_drafts = [
            source for source in linked
            if source.get("upgrade_status") == "lesson-draft"
            and source.get("automation_status") == "pending"
        ]
        deferred_drafts = [
            source for source in linked
            if source.get("upgrade_status") == "lesson-draft"
            and source.get("automation_status") == "deferred"
        ]
        if auto_verified:
            label = f"자동 검증 근거 {len(auto_verified)}개"
        elif auto_drafts:
            label = f"독립 검토 통과 초안 {len(auto_drafts)}개"
        elif existing_drafts:
            label = f"기존 초안 {len(existing_drafts)}개, 자동 검토 전"
        elif deferred_drafts:
            label = f"자동 검토 보류 초안 {len(deferred_drafts)}개"
        else:
            label = "검증된 근거 없음"
        statuses.append({"pattern": pattern, "status": label})
    return statuses


def goal_decisions(report: dict[str, Any]) -> list[str]:
    return []


def print_run_summary(summary: dict[str, Any]) -> None:
    print(f"처리한 자료 수: {summary['processed']}")
    print(f"자동 반영된 수: {summary['applied']}")
    print(f"보류된 수: {summary['deferred']}")
    print("보류 이유별 개수:")
    if summary["deferred_reason_counts"]:
        for reason, count in summary["deferred_reason_counts"].items():
            print(f"- {DEFERRED_REASON_LABELS.get(reason, reason)}: {count}")
    else:
        print("- 없음")
    print("현재 패턴별 근거 상태:")
    for item in summary["pattern_evidence"]:
        print(f"- {item['pattern']}: {item['status']}")
    print("시스템이 해결하지 못해 사용자 목표 결정이 필요한 사항:")
    if summary["goal_decisions"]:
        for decision in summary["goal_decisions"]:
            print(f"- {decision}")
    else:
        print("- 없음")


def command_run(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    selection = select_next(
        manifest,
        args.limit,
        False,
        args.strategy,
    )
    if not selection:
        raise PipelineError("No eligible sources were selected.")
    now = dt.datetime.now(dt.timezone.utc)
    batch_id = f"corpus-run-{now.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    run_dir = RUNS_DIR / batch_id
    run_dir.mkdir(parents=True, exist_ok=False)
    selection_path = run_dir / "selection.json"
    prompt_path = run_dir / "writer-prompt.md"
    raw_result_path = run_dir / "writer-result.raw.json"
    codex_log_path = run_dir / "writer-codex.log"
    review_prompt_path = run_dir / "reviewer-prompt.md"
    review_result_path = run_dir / "reviewer-result.raw.json"
    review_log_path = run_dir / "reviewer-codex.log"
    accepted_path = run_dir / "batch-result.accepted.json"
    deferred_path = run_dir / "deferred.json"
    decision_path = run_dir / "decision.json"
    dry_run_path = run_dir / "apply-dry-run.json"
    apply_path = run_dir / "apply-result.json"
    validation_path = run_dir / "validation.json"
    summary_path = run_dir / "summary.json"

    write_json(selection_path, selection)
    prompt = build_codex_research_prompt(batch_id, selection, manifest)
    atomic_write_text(prompt_path, prompt)
    try:
        invoke_codex_exec(
            prompt,
            raw_result_path,
            codex_log_path,
            CORPUS_DIR / "batch-result.schema.json",
        )
        payload = load_json(raw_result_path)
        writer_batch, writer_rejections = filter_generated_batch(
            payload, batch_id, selection, manifest
        )
    except PipelineError as exc:
        atomic_write_text(run_dir / "writer-error.txt", str(exc) + "\n")
        writer_batch = {"batch_id": batch_id, "sources": []}
        writer_rejections = [
            {"source_id": item["source_id"], "reason": "writer-execution-failed"}
            for item in selection
        ]
    review_prompt = build_independent_review_prompt(batch_id, writer_batch["sources"])
    atomic_write_text(review_prompt_path, review_prompt)
    if writer_batch["sources"]:
        try:
            invoke_codex_exec(
                review_prompt,
                review_result_path,
                review_log_path,
                REVIEW_SCHEMA_PATH,
            )
            review_payload = load_json(review_result_path)
        except PipelineError as exc:
            atomic_write_text(run_dir / "reviewer-error.txt", str(exc) + "\n")
            review_payload = {"batch_id": batch_id, "reviews": []}
            review_execution_failed = True
        else:
            review_execution_failed = False
    else:
        review_payload = {"batch_id": batch_id, "reviews": []}
        write_json(review_result_path, review_payload)
        atomic_write_text(review_log_path, "No schema-valid writer results to review.\n")
        review_execution_failed = False
    writer_ids = {item["source_id"] for item in writer_batch["sources"]}
    if review_execution_failed:
        reviews = {}
        review_problems = [
            {"source_id": source_id, "reason": "review-execution-failed"}
            for source_id in sorted(writer_ids)
        ]
    else:
        try:
            reviews, review_problems = parse_independent_reviews(
                review_payload, batch_id, writer_ids
            )
        except PipelineError as exc:
            atomic_write_text(run_dir / "reviewer-validation-error.txt", str(exc) + "\n")
            reviews = {}
            review_problems = [
                {"source_id": source_id, "reason": "review-validation-failed"}
                for source_id in sorted(writer_ids)
            ]
    accepted, deferred = decide_automatic_application(
        selection,
        writer_batch,
        writer_rejections,
        reviews,
        review_problems,
        manifest,
    )
    accepted_batch = {"batch_id": batch_id, "sources": accepted}
    write_json(accepted_path, accepted_batch)
    write_json(deferred_path, {"batch_id": batch_id, "sources": deferred})
    write_json(
        decision_path,
        {
            "batch_id": batch_id,
            "applied_source_ids": [item["source_id"] for item in accepted],
            "deferred": deferred,
        },
    )

    if accepted:
        _, dry_output = capture_apply(accepted_path, dry_run=True)
        try:
            dry_payload = json.loads(dry_output)
        except json.JSONDecodeError:
            dry_payload = {"output": dry_output}
        write_json(dry_run_path, dry_payload)
        _, apply_output = capture_apply(accepted_path, dry_run=False)
        try:
            apply_payload = json.loads(apply_output)
        except json.JSONDecodeError:
            apply_payload = {"output": apply_output}
        write_json(apply_path, apply_payload)
    else:
        write_json(dry_run_path, {"dry_run": True, "accepted": 0, "would_write": []})
        write_json(apply_path, {"applied": 0, "files": []})

    current_manifest = load_manifest()
    by_id = {source["source_id"]: source for source in current_manifest["sources"]}
    accepted_ids = {item["source_id"] for item in accepted}
    for selected in selection:
        source_id = selected["source_id"]
        source = by_id[source_id]
        source["last_automation_run"] = batch_id
        source["automation_attempts"] = int(source.get("automation_attempts") or 0) + 1
        if source_id in accepted_ids:
            source["automation_status"] = "applied"
            source["deferred_reasons"] = []
        else:
            source["automation_status"] = "deferred"
            source["deferred_reasons"] = deferred.get(
                source_id, ["deterministic-validation-failed"]
            )
    write_json(MANIFEST_PATH, current_manifest)

    report = validate_repository(current_manifest)
    write_json(validation_path, report)
    reason_counts: dict[str, int] = defaultdict(int)
    for reasons in deferred.values():
        for reason in reasons:
            reason_counts[reason] += 1
    summary = {
        "batch_id": batch_id,
        "processed": len(selection),
        "applied": len(accepted),
        "deferred": len(selection) - len(accepted),
        "deferred_reason_counts": dict(sorted(reason_counts.items())),
        "pattern_evidence": pattern_evidence_status(current_manifest),
        "goal_decisions": goal_decisions(report),
    }
    write_json(summary_path, summary)
    print_run_summary(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the initial manifest from the corpus.")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    validate_parser = subparsers.add_parser("validate", help="Validate corpus, manifest, and pattern links.")
    validate_parser.add_argument(
        "--report",
        nargs="?",
        const=relative(DEFAULT_REPORT_PATH),
        help="Write a JSON report; optionally provide a repository-relative path.",
    )
    validate_parser.set_defaults(func=command_validate)

    next_parser = subparsers.add_parser("next", help="Select the next unprocessed sources.")
    next_parser.add_argument("--limit", type=int, default=10)
    next_parser.add_argument(
        "--strategy",
        choices=("default", "pattern-gaps"),
        default="default",
        help="Use pattern-gaps to select representatives for weak patterns.",
    )
    next_parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="Include unresolved duplicate-URL groups that are skipped by default.",
    )
    next_parser.set_defaults(func=command_next)

    apply_parser = subparsers.add_parser("apply", help="Validate and apply a Work batch result.")
    apply_parser.add_argument("input")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--overwrite", action="store_true")
    apply_parser.set_defaults(func=command_apply)

    run_parser = subparsers.add_parser(
        "run", help="Select, research with codex exec, validate, and apply a corpus batch."
    )
    run_parser.add_argument("--limit", type=int, default=10)
    run_parser.add_argument(
        "--strategy",
        choices=("default", "pattern-gaps"),
        default="default",
    )
    run_parser.set_defaults(func=command_run)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return int(args.func(args))
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
