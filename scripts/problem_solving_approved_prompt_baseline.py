#!/usr/bin/env python3
"""Select approved PROMPT baselines and inject them before Prompt Build Brief compilation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "approved-prompts" / "registry.json"
BASELINE_MARKER = "[기존 Prompt Compiler baseline]"


class ApprovedPromptBaselineError(ValueError):
    """Raised when an approved baseline registry or asset is invalid."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApprovedPromptBaselineError(f"{label}을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(value, dict):
        raise ApprovedPromptBaselineError(f"{label}은 JSON 객체여야 합니다.")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _string_list(value: Any, label: str, *, minimum: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ApprovedPromptBaselineError(f"{label}은 문자열 배열이어야 합니다.")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ApprovedPromptBaselineError(f"{label}에 빈 값이 있습니다.")
        text = item.strip().casefold()
        if text in normalized:
            raise ApprovedPromptBaselineError(f"{label}에 중복 값이 있습니다.")
        normalized.append(text)
    if len(normalized) < minimum:
        raise ApprovedPromptBaselineError(f"{label}은 최소 {minimum}개여야 합니다.")
    return normalized


def load_registry(
    registry_path: Path = REGISTRY_PATH,
    *,
    repository_root: Path = ROOT,
) -> list[dict[str, Any]]:
    payload = _read_json(registry_path, registry_path.name)
    if set(payload) != {"version", "entries"} or payload["version"] != 1:
        raise ApprovedPromptBaselineError("승인 baseline registry 최상위 형식이 올바르지 않습니다.")
    entries = payload["entries"]
    if not isinstance(entries, list):
        raise ApprovedPromptBaselineError("registry.entries가 배열이 아닙니다.")

    approved_root = (repository_root / "approved-prompts").resolve()
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in entries:
        expected = {
            "id",
            "status",
            "prompt_path",
            "prompt_sha256",
            "match",
            "evidence",
        }
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ApprovedPromptBaselineError("승인 baseline entry 필드가 올바르지 않습니다.")
        entry_id = raw["id"]
        if not isinstance(entry_id, str) or not entry_id.strip() or entry_id in seen:
            raise ApprovedPromptBaselineError("승인 baseline id가 비었거나 중복입니다.")
        seen.add(entry_id)
        if raw["status"] != "approved":
            raise ApprovedPromptBaselineError(f"{entry_id}: status는 approved여야 합니다.")
        prompt_path_value = raw["prompt_path"]
        if not isinstance(prompt_path_value, str) or not prompt_path_value.strip():
            raise ApprovedPromptBaselineError(f"{entry_id}: prompt_path가 비어 있습니다.")
        prompt_path = (repository_root / prompt_path_value).resolve()
        try:
            prompt_path.relative_to(approved_root)
        except ValueError as exc:
            raise ApprovedPromptBaselineError(
                f"{entry_id}: prompt_path가 approved-prompts 밖을 가리킵니다."
            ) from exc
        try:
            prompt = prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ApprovedPromptBaselineError(
                f"{entry_id}: 승인 prompt를 읽을 수 없습니다: {exc}"
            ) from exc
        if not prompt.strip():
            raise ApprovedPromptBaselineError(f"{entry_id}: 승인 prompt가 비어 있습니다.")
        actual_sha = _sha256_text(prompt)
        if raw["prompt_sha256"] != actual_sha:
            raise ApprovedPromptBaselineError(f"{entry_id}: prompt SHA-256이 일치하지 않습니다.")

        match = raw["match"]
        if not isinstance(match, dict) or set(match) != {
            "all_terms",
            "any_terms",
            "none_terms",
        }:
            raise ApprovedPromptBaselineError(f"{entry_id}: match 필드가 올바르지 않습니다.")
        all_terms = _string_list(match["all_terms"], f"{entry_id}.all_terms", minimum=1)
        any_terms = _string_list(match["any_terms"], f"{entry_id}.any_terms")
        none_terms = _string_list(match["none_terms"], f"{entry_id}.none_terms")
        evidence = raw["evidence"]
        if not isinstance(evidence, dict) or not evidence:
            raise ApprovedPromptBaselineError(f"{entry_id}: evidence가 비어 있습니다.")

        validated.append(
            {
                **copy.deepcopy(raw),
                "id": entry_id,
                "prompt_path": prompt_path_value,
                "prompt": prompt.rstrip(),
                "match": {
                    "all_terms": all_terms,
                    "any_terms": any_terms,
                    "none_terms": none_terms,
                },
            }
        )
    return validated


def select_approved_prompt(
    request: str,
    registry_path: Path = REGISTRY_PATH,
    *,
    repository_root: Path = ROOT,
) -> dict[str, Any] | None:
    text = request.casefold().strip()
    if not text:
        return None
    matches: list[dict[str, Any]] = []
    for entry in load_registry(registry_path, repository_root=repository_root):
        rules = entry["match"]
        if not all(term in text for term in rules["all_terms"]):
            continue
        if rules["any_terms"] and not any(term in text for term in rules["any_terms"]):
            continue
        if any(term in text for term in rules["none_terms"]):
            continue
        matches.append(entry)
    if len(matches) != 1:
        return None
    return matches[0]


def rewrite_compiler_baseline(
    prompt: str,
    approved: Mapping[str, Any],
) -> tuple[str, bool]:
    marker_position = prompt.find(BASELINE_MARKER)
    if marker_position < 0:
        return prompt, False
    start = prompt.find("{", marker_position + len(BASELINE_MARKER))
    if start < 0:
        return prompt, False
    try:
        baseline, end = json.JSONDecoder().raw_decode(prompt[start:])
    except json.JSONDecodeError:
        return prompt, False
    if not isinstance(baseline, dict):
        return prompt, False

    updated = copy.deepcopy(baseline)
    updated["final_prompt"] = approved["prompt"]
    updated["approved_baseline"] = {
        "id": approved["id"],
        "prompt_path": approved["prompt_path"],
        "prompt_sha256": approved["prompt_sha256"],
        "evidence": approved["evidence"],
    }
    rendered = json.dumps(updated, ensure_ascii=False, indent=2)
    return prompt[:start] + rendered + prompt[start + end :], True


def approved_engine_class(
    base_class: type,
    *,
    registry_path: Path = REGISTRY_PATH,
    repository_root: Path = ROOT,
) -> type:
    class ApprovedPromptBuildBriefEngine(base_class):
        __approved_baseline_wrapper__ = True

        def __init__(self, delegate: Any, *, request: str, os_module: Any) -> None:
            self._approved_baseline = select_approved_prompt(
                request,
                registry_path=registry_path,
                repository_root=repository_root,
            )
            self._approved_baseline_injected = False
            super().__init__(
                delegate,
                request=request,
                os_module=os_module,
            )

        def execute(self, prompt: str, run_dir: Path, invocation: Any) -> dict[str, Any]:
            if (
                self._approved_baseline is not None
                and invocation.phase == "executor"
                and invocation.route == "PROMPT"
            ):
                prompt, injected = rewrite_compiler_baseline(
                    prompt,
                    self._approved_baseline,
                )
                self._approved_baseline_injected = (
                    self._approved_baseline_injected or injected
                )
            return super().execute(prompt, run_dir, invocation)

        def record(self) -> dict[str, Any] | None:
            record = super().record()
            if (
                record is None
                or self._approved_baseline is None
                or not self._approved_baseline_injected
            ):
                return record
            approved_record = {
                "id": self._approved_baseline["id"],
                "prompt_path": self._approved_baseline["prompt_path"],
                "prompt_sha256": self._approved_baseline["prompt_sha256"],
                "evidence": copy.deepcopy(self._approved_baseline["evidence"]),
            }
            record["approved_baseline"] = approved_record
            for entry in record.get("entries", []):
                if isinstance(entry, dict):
                    entry["baseline_source"] = "approved_registry"
                    entry["approved_baseline_id"] = approved_record["id"]
            return record

    ApprovedPromptBuildBriefEngine.__name__ = "ApprovedPromptBuildBriefEngine"
    return ApprovedPromptBuildBriefEngine


def patch_quality_runtime(quality_module: Any) -> type:
    current = quality_module.PROMPT_BRIEF.PromptBuildBriefEngine
    if getattr(current, "__approved_baseline_wrapper__", False):
        return current
    wrapped = approved_engine_class(current)
    quality_module.PROMPT_BRIEF.PromptBuildBriefEngine = wrapped
    return wrapped
