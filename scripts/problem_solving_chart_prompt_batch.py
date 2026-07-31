#!/usr/bin/env python3
"""Run several chart-analysis prompts against one shared image set and compare them blindly."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import random
import re
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OS_PATH = ROOT / "scripts" / "problem_solving_os.py"
ANSWER_SCHEMA_PATH = ROOT / "schemas" / "problem-solving-prompt-applied-answer.schema.json"
ASSESSMENT_SCHEMA_PATH = (
    ROOT / "schemas" / "problem-solving-chart-prompt-assessment.schema.json"
)
DEFAULT_RESULTS_DIR = ROOT / "runtime-results" / "chart-prompt-comparison"
EXPECTED_PROMPT_LABELS = (
    "current",
    "without_raw_request",
    "compact_ledger",
    "single_build_brief",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PROMPT_BYTES = 200_000
MAX_CONTEXT_BYTES = 50_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 100 * 1024 * 1024
MAX_IMAGES = 12
MAX_PROMPTS = 8
REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max", "ultra"}


def _load_local_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OS = _load_local_module("psos_for_chart_prompt_batch", OS_PATH)


class ChartPromptBatchError(ValueError):
    """Raised when a chart prompt comparison cannot run reproducibly."""


@dataclass(frozen=True)
class PromptInput:
    label: str
    source_path: Path
    text: str
    sha256: str


@dataclass(frozen=True)
class ImageInput:
    source_path: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class RunProfile:
    model: str
    reasoning_effort: str


Invoker = Callable[
    [str, Path, str, Path, Sequence[Path], RunProfile],
    dict[str, Any],
]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _atomic_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    if not slug:
        raise ChartPromptBatchError("프롬프트 label은 비어 있을 수 없습니다.")
    return slug[:60]


def _canonical_prompt_stem(stem: str) -> str | None:
    value = re.sub(r"\(\d+\)$", "", stem.strip())
    value = re.sub(r"[\s-]+", "_", value.casefold()).strip("_")
    aliases = {
        "current": "current",
        "without_raw_request": "without_raw_request",
        "compact_ledger": "compact_ledger",
        "single_build_brief": "single_build_brief",
    }
    return aliases.get(value)


def discover_prompt_dir(prompt_dir: Path) -> list[tuple[str, Path]]:
    root = prompt_dir.expanduser().resolve()
    if not root.is_dir():
        raise ChartPromptBatchError(f"프롬프트 폴더가 없습니다: {prompt_dir}")
    found: dict[str, Path] = {}
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.casefold() not in {".md", ".txt"}:
            continue
        label = _canonical_prompt_stem(path.stem)
        if label is None:
            continue
        if label in found:
            raise ChartPromptBatchError(
                f"{label} 프롬프트 파일이 둘 이상입니다: {found[label].name}, {path.name}"
            )
        found[label] = path
    missing = [label for label in EXPECTED_PROMPT_LABELS if label not in found]
    if missing:
        raise ChartPromptBatchError(
            "프롬프트 폴더에 필요한 파일이 없습니다: " + ", ".join(missing)
        )
    return [(label, found[label]) for label in EXPECTED_PROMPT_LABELS]


def parse_prompt_specs(
    prompt_specs: Sequence[str],
    prompt_dir: Path | None,
) -> list[PromptInput]:
    pairs: list[tuple[str, Path]] = []
    if prompt_dir is not None:
        pairs.extend(discover_prompt_dir(prompt_dir))
    for raw in prompt_specs:
        if "=" not in raw:
            raise ChartPromptBatchError(
                "--prompt는 label=파일경로 형식이어야 합니다."
            )
        raw_label, raw_path = raw.split("=", 1)
        pairs.append((_slug(raw_label), Path(raw_path)))
    if len(pairs) < 2:
        raise ChartPromptBatchError("비교할 프롬프트 파일을 최소 2개 지정해 주세요.")
    if len(pairs) > MAX_PROMPTS:
        raise ChartPromptBatchError(f"프롬프트는 최대 {MAX_PROMPTS}개까지 비교할 수 있습니다.")

    labels: set[str] = set()
    paths: set[Path] = set()
    result: list[PromptInput] = []
    for raw_label, raw_path in pairs:
        label = _slug(raw_label)
        if label in labels:
            raise ChartPromptBatchError(f"중복 프롬프트 label입니다: {label}")
        path = raw_path.expanduser().resolve()
        if not path.is_file():
            raise ChartPromptBatchError(f"프롬프트 파일이 없습니다: {raw_path}")
        if path in paths:
            raise ChartPromptBatchError(f"같은 프롬프트 파일을 중복 지정했습니다: {path}")
        if path.stat().st_size > MAX_PROMPT_BYTES:
            raise ChartPromptBatchError(
                f"프롬프트 파일은 {MAX_PROMPT_BYTES:,}바이트 이하여야 합니다: {path.name}"
            )
        try:
            text = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ChartPromptBatchError(f"UTF-8 프롬프트 파일이 아닙니다: {path}") from exc
        if not text:
            raise ChartPromptBatchError(f"프롬프트 파일이 비어 있습니다: {path}")
        labels.add(label)
        paths.add(path)
        result.append(
            PromptInput(
                label=label,
                source_path=path,
                text=text,
                sha256=_sha256_text(text),
            )
        )
    return result


def discover_image_dir(image_dir: Path) -> list[Path]:
    root = image_dir.expanduser().resolve()
    if not root.is_dir():
        raise ChartPromptBatchError(f"이미지 폴더가 없습니다: {image_dir}")
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
    ]


def parse_images(image_paths: Sequence[Path], image_dir: Path | None) -> list[ImageInput]:
    raw_paths = list(image_paths)
    if image_dir is not None:
        raw_paths.extend(discover_image_dir(image_dir))
    if not raw_paths:
        raise ChartPromptBatchError("같은 조건으로 분석할 차트 이미지를 하나 이상 지정해 주세요.")
    if len(raw_paths) > MAX_IMAGES:
        raise ChartPromptBatchError(f"차트 이미지는 최대 {MAX_IMAGES}개까지 지원합니다.")

    seen: set[Path] = set()
    total_size = 0
    result: list[ImageInput] = []
    for raw_path in raw_paths:
        lexical = raw_path.expanduser()
        if lexical.is_symlink():
            raise ChartPromptBatchError(f"심볼릭 링크 이미지는 허용하지 않습니다: {raw_path}")
        path = lexical.resolve()
        if not path.is_file():
            raise ChartPromptBatchError(f"차트 이미지가 없습니다: {raw_path}")
        if path in seen:
            continue
        if path.suffix.casefold() not in IMAGE_SUFFIXES:
            raise ChartPromptBatchError(
                f"지원하지 않는 이미지 형식입니다: {path.name}"
            )
        sha256, size = _sha256_file(path)
        if size > MAX_IMAGE_BYTES:
            raise ChartPromptBatchError(
                f"이미지 한 장은 {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하여야 합니다: {path.name}"
            )
        total_size += size
        if total_size > MAX_TOTAL_IMAGE_BYTES:
            raise ChartPromptBatchError(
                f"이미지 전체는 {MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)}MB 이하여야 합니다."
            )
        seen.add(path)
        result.append(ImageInput(source_path=path, sha256=sha256, size=size))
    return result


def read_context(raw_context: str | None, context_file: Path | None) -> str:
    parts: list[str] = []
    if raw_context and raw_context.strip():
        parts.append(raw_context.strip())
    if context_file is not None:
        path = context_file.expanduser().resolve()
        if not path.is_file():
            raise ChartPromptBatchError(f"추가 문맥 파일이 없습니다: {context_file}")
        if path.stat().st_size > MAX_CONTEXT_BYTES:
            raise ChartPromptBatchError(
                f"추가 문맥은 {MAX_CONTEXT_BYTES:,}바이트 이하여야 합니다."
            )
        try:
            text = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ChartPromptBatchError("추가 문맥 파일은 UTF-8이어야 합니다.") from exc
        if text:
            parts.append(text)
    combined = "\n\n".join(parts)
    if len(combined.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise ChartPromptBatchError(
            f"추가 문맥은 합계 {MAX_CONTEXT_BYTES:,}바이트 이하여야 합니다."
        )
    return combined


def resolve_profile(model: str | None, reasoning_effort: str | None) -> RunProfile:
    policy = OS.load_model_policy()
    prompt_profile = policy["routes"]["PROMPT"]["primary"]
    selected_model = model.strip() if model else prompt_profile.model
    selected_effort = reasoning_effort or prompt_profile.reasoning_effort
    if not selected_model:
        raise ChartPromptBatchError("비교에 사용할 model이 비어 있습니다.")
    if selected_effort not in REASONING_EFFORTS:
        raise ChartPromptBatchError(f"지원하지 않는 reasoning effort입니다: {selected_effort}")
    return RunProfile(model=selected_model, reasoning_effort=selected_effort)


def _bundle_digest(prompts: Sequence[PromptInput], images: Sequence[ImageInput], context: str) -> str:
    payload = {
        "prompts": [{"label": item.label, "sha256": item.sha256} for item in prompts],
        "images": [{"sha256": item.sha256, "size": item.size} for item in images],
        "context_sha256": _sha256_text(context),
    }
    return _sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def candidate_mapping(labels: Sequence[str], digest: str) -> dict[str, str]:
    if len(labels) < 2 or len(labels) > MAX_PROMPTS:
        raise ChartPromptBatchError("후보 수가 지원 범위를 벗어났습니다.")
    shuffled = list(labels)
    random.Random(int(digest[:16], 16)).shuffle(shuffled)
    return {chr(ord("A") + index): label for index, label in enumerate(shuffled)}


def _copy_inputs(
    output_dir: Path,
    prompts: Sequence[PromptInput],
    images: Sequence[ImageInput],
    context: str,
) -> tuple[dict[str, Path], list[Path], Path | None]:
    prompt_root = output_dir / "inputs" / "prompts"
    image_root = output_dir / "inputs" / "images"
    prompt_root.mkdir(parents=True, exist_ok=True)
    image_root.mkdir(parents=True, exist_ok=True)
    copied_prompts: dict[str, Path] = {}
    for item in prompts:
        target = prompt_root / f"{item.label}.md"
        target.write_text(item.text.rstrip() + "\n", encoding="utf-8")
        copied_prompts[item.label] = target
    copied_images: list[Path] = []
    for index, item in enumerate(images, start=1):
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", item.source_path.name)
        target = image_root / f"{index:02d}-{safe_name}"
        shutil.copy2(item.source_path, target)
        copied_sha, copied_size = _sha256_file(target)
        if copied_sha != item.sha256 or copied_size != item.size:
            raise ChartPromptBatchError(f"입력 이미지 복사 검증에 실패했습니다: {item.source_path}")
        copied_images.append(target)
    context_path: Path | None = None
    if context:
        context_path = output_dir / "inputs" / "context.md"
        context_path.write_text(context.rstrip() + "\n", encoding="utf-8")
    return copied_prompts, copied_images, context_path


def build_analysis_prompt(prompt_text: str, context: str, image_count: int) -> str:
    context_block = context or "제공된 추가 문맥 없음"
    return f"""아래 사용자 정의 프롬프트를 개선하거나 평가하지 말고 그대로 실행하라.
첨부된 {image_count}개 차트 이미지는 모두 같은 분석 대상의 입력이다.
사용자 정의 프롬프트가 요구하는 차트 분석 결과만 answer_markdown에 작성하라.
내부 시스템, 비교 실험, 프롬프트 이름이나 실행 과정을 언급하지 마라.
보이지 않는 가격·지표·시간대를 만들어내지 마라.

[사용자 정의 프롬프트]
{prompt_text.strip()}

[모든 후보에 동일하게 제공되는 사용자 추가 문맥]
{context_block}
"""


def build_assessment_prompt(
    answers: Mapping[str, str],
    context: str,
    image_count: int,
) -> str:
    candidate_sections = "\n\n".join(
        f"[후보 {candidate_id}]\n{answer.strip()}"
        for candidate_id, answer in answers.items()
    )
    context_block = context or "제공된 추가 문맥 없음"
    candidate_ids = list(answers)
    return f"""당신은 다중 시간대 차트 매매 분석 결과의 블라인드 평가자다.
첨부된 {image_count}개 차트와 동일한 사용자 문맥을 기준으로 후보를 직접 검증한다.
후보의 원래 프롬프트 이름과 내부 변형은 공개되지 않는다.

[평가 기준]
1. observation_fidelity: 차트에 실제로 보이는 가격 구조·거래량·지표만 사용하고 숫자를 꾸미지 않았는가.
2. multi_timeframe_synthesis: 시간대를 따로 나열하지 않고 상위 구조와 하위 신호를 연결했는가.
3. decision_clarity: 진입·대기·관망·보유 수정 중 무엇을 해야 하는지 분명한가.
4. plan_quality: 진입 조건, 손절, 구조적 무효화, 분할 익절과 손익비가 서로 맞물리는가.
5. calibration: 불확실성·충돌 신호·반대 시나리오를 적절히 다루는가.
6. format_cost: 반복과 빈 양식이 실제 판단을 가리는 정도다. 1은 부담이 낮고 5는 매우 높다.

[치명적 실패]
- 차트에서 읽을 수 없는 정확한 가격이나 지표를 사실처럼 생성
- 하위 시간대 반등만으로 상위 하락 구조가 끝났다고 단정
- 사용자의 기대 방향에 맞춰 반대 근거를 누락
- 손절과 무효화 조건 없이 진입을 권고
- 결론을 회피하고 일반적인 투자 경고로 대체
- 서로 충돌하는 진입·손절·익절 계획

치명적 실패가 있는 후보는 점수 합이 높아도 우선순위에서 내려라.
ranking에는 {', '.join(candidate_ids)}를 정확히 한 번씩 가장 좋은 순서로 넣어라.
평가 근거는 후보 본문과 첨부 차트에서 확인되는 내용만 사용하고 추측하지 마라.

[동일 사용자 문맥]
{context_block}

{candidate_sections}
"""


def validate_answer(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"version", "answer_markdown"}:
        raise ChartPromptBatchError("차트 분석 결과가 answer schema와 일치하지 않습니다.")
    if payload["version"] != 1:
        raise ChartPromptBatchError("지원하지 않는 차트 분석 결과 버전입니다.")
    if not isinstance(payload["answer_markdown"], str) or not payload["answer_markdown"].strip():
        raise ChartPromptBatchError("차트 분석 answer_markdown이 비어 있습니다.")
    return {"version": 1, "answer_markdown": payload["answer_markdown"].strip()}


def validate_assessment(payload: Any, candidate_ids: set[str]) -> dict[str, Any]:
    expected = {
        "version",
        "ranking",
        "candidates",
        "preferred_candidate_ids",
        "conclusion",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ChartPromptBatchError("블라인드 평가 결과가 assessment schema와 일치하지 않습니다.")
    if payload["version"] != 1:
        raise ChartPromptBatchError("지원하지 않는 블라인드 평가 버전입니다.")
    ranking = payload["ranking"]
    if not isinstance(ranking, list) or len(ranking) != len(candidate_ids) or set(ranking) != candidate_ids:
        raise ChartPromptBatchError("블라인드 평가 ranking이 후보 전체와 일치하지 않습니다.")
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or len(candidates) != len(candidate_ids):
        raise ChartPromptBatchError("블라인드 평가 candidate 수가 일치하지 않습니다.")
    seen: set[str] = set()
    score_fields = (
        "observation_fidelity",
        "multi_timeframe_synthesis",
        "decision_clarity",
        "plan_quality",
        "calibration",
        "format_cost",
    )
    for item in candidates:
        if not isinstance(item, dict):
            raise ChartPromptBatchError("블라인드 후보 판정이 객체가 아닙니다.")
        candidate_id = item.get("candidate_id")
        if candidate_id not in candidate_ids or candidate_id in seen:
            raise ChartPromptBatchError("블라인드 candidate_id가 유효하지 않습니다.")
        seen.add(candidate_id)
        for field in score_fields:
            value = item.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                raise ChartPromptBatchError(f"{candidate_id}.{field} 점수가 유효하지 않습니다.")
        failures = item.get("critical_failures")
        if not isinstance(failures, list) or any(
            not isinstance(value, str) or not value.strip() for value in failures
        ):
            raise ChartPromptBatchError("critical_failures가 문자열 배열이 아닙니다.")
        if not isinstance(item.get("finding"), str) or not item["finding"].strip():
            raise ChartPromptBatchError("candidate finding이 비어 있습니다.")
    preferred = payload["preferred_candidate_ids"]
    if (
        not isinstance(preferred, list)
        or not preferred
        or len(preferred) > 2
        or len(set(preferred)) != len(preferred)
        or any(value not in candidate_ids for value in preferred)
    ):
        raise ChartPromptBatchError("preferred_candidate_ids가 유효하지 않습니다.")
    if not isinstance(payload["conclusion"], str) or not payload["conclusion"].strip():
        raise ChartPromptBatchError("블라인드 평가 conclusion이 비어 있습니다.")
    return payload


class CodexImageInvoker:
    """Small non-interactive Codex adapter that attaches the same images each time."""

    def __init__(self, workspace: Path, timeout_seconds: int = 900) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.executable = OS.find_codex()
        self._checked = False

    def _check(self) -> None:
        if self._checked:
            return
        completed = subprocess.run(
            OS.subprocess_command(self.executable, ["exec", "--help"]),
            cwd=self.workspace,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
        help_text = completed.stdout or ""
        if completed.returncode != 0:
            raise ChartPromptBatchError("Codex CLI exec capability를 확인하지 못했습니다.")
        required = ("--image", "--output-schema", "--output-last-message")
        missing = [flag for flag in required if flag not in help_text]
        if missing:
            raise ChartPromptBatchError(
                "현재 Codex CLI에 필요한 옵션이 없습니다: " + ", ".join(missing)
            )
        self._checked = True

    def __call__(
        self,
        prompt: str,
        run_dir: Path,
        invocation_name: str,
        schema_path: Path,
        images: Sequence[Path],
        profile: RunProfile,
    ) -> dict[str, Any]:
        self._check()
        engine_dir = run_dir / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        request_path = engine_dir / f"{invocation_name}-request.md"
        output_path = engine_dir / f"{invocation_name}-output.json"
        log_path = engine_dir / f"{invocation_name}.log"
        request_path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
        arguments = [
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "-m",
            profile.model,
            "-c",
            f"model_reasoning_effort={profile.reasoning_effort}",
            "--sandbox",
            "read-only",
            "--cd",
            str(self.workspace),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--color",
            "never",
        ]
        for image in images:
            arguments.extend(["--image", str(image)])
        arguments.append("-")
        try:
            completed = subprocess.run(
                OS.subprocess_command(self.executable, arguments),
                input=prompt,
                cwd=self.workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ChartPromptBatchError(f"Codex CLI 실행 실패: {exc}") from exc
        log_path.write_text(completed.stdout or "", encoding="utf-8")
        if completed.returncode != 0:
            raise ChartPromptBatchError(
                f"{invocation_name} 실행이 exit {completed.returncode}로 실패했습니다."
            )
        if not output_path.is_file():
            raise ChartPromptBatchError(f"{invocation_name} 구조화 결과가 없습니다.")
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChartPromptBatchError(
                f"{invocation_name} 결과 JSON을 읽을 수 없습니다: {exc}"
            ) from exc


def _render_blind_report(
    copied_images: Sequence[Path],
    output_dir: Path,
    answers: Mapping[str, str],
    assessment: Mapping[str, Any] | None,
) -> str:
    lines = ["# 차트 프롬프트 블라인드 비교", "", "## 공통 입력 차트", ""]
    for index, image in enumerate(copied_images, start=1):
        relative = image.relative_to(output_dir).as_posix()
        lines.extend([f"### 차트 {index}", "", f"![차트 {index}]({relative})", ""])
    if assessment:
        lines.extend(["## 자동 블라인드 평가", ""])
        lines.append("순위: " + " > ".join(f"**{item}**" for item in assessment["ranking"]))
        lines.append("")
        lines.append(str(assessment["conclusion"]))
        lines.append("")
        by_id = {item["candidate_id"]: item for item in assessment["candidates"]}
        for candidate_id in assessment["ranking"]:
            item = by_id[candidate_id]
            lines.append(
                f"- **후보 {candidate_id}** — 관찰 {item['observation_fidelity']}/5 · "
                f"시간대 종합 {item['multi_timeframe_synthesis']}/5 · "
                f"결론 {item['decision_clarity']}/5 · 계획 {item['plan_quality']}/5 · "
                f"보정 {item['calibration']}/5 · 형식 부담 {item['format_cost']}/5: "
                f"{item['finding']}"
            )
            if item["critical_failures"]:
                lines.append("  - 치명적 실패: " + "; ".join(item["critical_failures"]))
        lines.append("")
    lines.extend(["## 후보별 실제 분석", ""])
    for candidate_id, answer in answers.items():
        lines.extend([f"### 후보 {candidate_id}", "", answer.rstrip(), ""])
    lines.extend(
        [
            "## 직접 판정 메모",
            "",
            "- 가장 실제 매매 판단에 도움이 된 후보:",
            "- 보이지 않는 숫자나 지표를 만든 후보:",
            "- 결론은 좋지만 너무 장황했던 후보:",
            "- 최종 선택:",
            "",
        ]
    )
    return "\n".join(lines)


def _render_revealed_report(
    blind_report: str,
    mapping: Mapping[str, str],
    prompt_paths: Mapping[str, Path],
    output_dir: Path,
) -> str:
    lines = [blind_report.rstrip(), "", "## 후보 정체 공개", ""]
    for candidate_id, label in mapping.items():
        relative = prompt_paths[label].relative_to(output_dir).as_posix()
        lines.append(f"- **후보 {candidate_id}** = `{label}` · [{relative}]({relative})")
    lines.append("")
    return "\n".join(lines)


def run_chart_prompt_comparison(
    *,
    prompts: Sequence[PromptInput],
    images: Sequence[ImageInput],
    context: str,
    output_dir: Path,
    profile: RunProfile,
    judge: bool = True,
    force: bool = False,
    invoker: Invoker | None = None,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise ChartPromptBatchError(
            f"결과 폴더가 비어 있지 않습니다. --force가 필요합니다: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    copied_prompts, copied_images, context_path = _copy_inputs(
        output_dir, prompts, images, context
    )
    digest = _bundle_digest(prompts, images, context)
    mapping = candidate_mapping([item.label for item in prompts], digest)
    by_label = {item.label: item for item in prompts}
    runtime_invoker = invoker or CodexImageInvoker(ROOT, timeout_seconds)

    candidates_root = output_dir / "candidates"
    candidates_root.mkdir(parents=True, exist_ok=True)
    answers: dict[str, str] = {}
    candidate_records: list[dict[str, Any]] = []
    for candidate_id, label in mapping.items():
        prompt_input = by_label[label]
        payload = runtime_invoker(
            build_analysis_prompt(prompt_input.text, context, len(copied_images)),
            output_dir,
            f"chart-analysis-{candidate_id}",
            ANSWER_SCHEMA_PATH,
            copied_images,
            profile,
        )
        answer = validate_answer(payload)
        markdown_path = candidates_root / f"{candidate_id}.md"
        json_path = candidates_root / f"{candidate_id}.json"
        markdown_path.write_text(answer["answer_markdown"].rstrip() + "\n", encoding="utf-8")
        _atomic_json(json_path, answer)
        answers[candidate_id] = answer["answer_markdown"]
        candidate_records.append(
            {
                "candidate_id": candidate_id,
                "prompt_label": label,
                "prompt_sha256": prompt_input.sha256,
                "answer_sha256": _sha256_text(answer["answer_markdown"]),
                "answer_path": markdown_path.relative_to(output_dir).as_posix(),
                "answer_json_path": json_path.relative_to(output_dir).as_posix(),
            }
        )

    assessment: dict[str, Any] | None = None
    if judge:
        raw_assessment = runtime_invoker(
            build_assessment_prompt(answers, context, len(copied_images)),
            output_dir,
            "chart-analysis-blind-assessment",
            ASSESSMENT_SCHEMA_PATH,
            copied_images,
            profile,
        )
        assessment = validate_assessment(raw_assessment, set(mapping))
        _atomic_json(output_dir / "assessment.json", assessment)

    blind_text = _render_blind_report(copied_images, output_dir, answers, assessment)
    blind_path = output_dir / "blind-report.md"
    blind_path.write_text(blind_text, encoding="utf-8")
    report_text = _render_revealed_report(
        blind_text, mapping, copied_prompts, output_dir
    )
    report_path = output_dir / "report.md"
    report_path.write_text(report_text, encoding="utf-8")

    manifest = {
        "version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bundle_sha256": digest,
        "profile": {
            "model": profile.model,
            "reasoning_effort": profile.reasoning_effort,
            "web_search": False,
            "sandbox": "read-only",
        },
        "prompt_inputs": [
            {
                "label": item.label,
                "source_path": str(item.source_path),
                "copied_path": copied_prompts[item.label].relative_to(output_dir).as_posix(),
                "sha256": item.sha256,
            }
            for item in prompts
        ],
        "image_inputs": [
            {
                "source_path": str(item.source_path),
                "copied_path": copied_images[index].relative_to(output_dir).as_posix(),
                "sha256": item.sha256,
                "size": item.size,
            }
            for index, item in enumerate(images)
        ],
        "context_path": (
            context_path.relative_to(output_dir).as_posix() if context_path else None
        ),
        "context_sha256": _sha256_text(context),
        "candidate_mapping": mapping,
        "candidates": candidate_records,
        "assessment": assessment,
        "blind_report_path": blind_path.relative_to(output_dir).as_posix(),
        "report_path": report_path.relative_to(output_dir).as_posix(),
    }
    manifest_path = _atomic_json(output_dir / "manifest.json", manifest)
    return {
        "version": 1,
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "blind_report_path": str(blind_path),
        "report_path": str(report_path),
        "assessment_completed": assessment is not None,
    }


def default_output_dir() -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return DEFAULT_RESULTS_DIR / stamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        help="current, without_raw_request, compact_ledger, single_build_brief 파일이 있는 폴더",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        default=[],
        help="추가 프롬프트. label=파일경로 형식이며 여러 번 사용할 수 있습니다.",
    )
    parser.add_argument("--image", type=Path, action="append", default=[])
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--context")
    parser.add_argument("--context-file", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=sorted(REASONING_EFFORTS))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--open-report", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        prompts = parse_prompt_specs(args.prompt, args.prompt_dir)
        images = parse_images(args.image, args.image_dir)
        context = read_context(args.context, args.context_file)
        profile = resolve_profile(args.model, args.reasoning_effort)
        output_dir = args.output_dir or default_output_dir()
        result = run_chart_prompt_comparison(
            prompts=prompts,
            images=images,
            context=context,
            output_dir=output_dir,
            profile=profile,
            judge=not args.no_judge,
            force=args.force,
            timeout_seconds=args.timeout_seconds,
        )
    except (ChartPromptBatchError, OS.ProblemSolvingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result["report_path"])
    if args.open_report:
        webbrowser.open(Path(result["report_path"]).as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
