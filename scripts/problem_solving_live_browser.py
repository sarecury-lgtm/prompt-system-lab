#!/usr/bin/env python3
"""Verify current product-page transaction state with installed headless Chrome."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


# [CLAUDE_CONTEXT]
# Purpose: Turn rendered product-page state into a deterministic PSOS receipt.
# Key decision: cached search HTML never counts; Chrome-rendered negative signals win.
# Watch out for: unknown is intentionally non-success because commerce pages vary widely.

PRODUCT_PATH_PATTERN = re.compile(
    r"(?:/products?/|/goods?/|/item|detail|goods_view|itempage|goodscode=|goodsno=)",
    re.IGNORECASE,
)
TRANSACTION_FINDING_PATTERN = re.compile(
    r"판매|구매|주문|재고|품절|가격|배송|available|stock|buy|order|price|shipping",
    re.IGNORECASE,
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
STRONG_NEGATIVE_PATTERNS = (
    re.compile(r"현재\s*판매\s*중인\s*상품이\s*아닙니다", re.IGNORECASE),
    re.compile(r"판매가\s*종료된\s*상품(?:입니다)?", re.IGNORECASE),
    re.compile(r"판매\s*(?:중지|종료)된?\s*상품", re.IGNORECASE),
    re.compile(r"(?:현재\s*)?품절된?\s*상품", re.IGNORECASE),
    re.compile(r"\b(?:sold\s*out|out\s*of\s*stock|no\s*longer\s*available)\b", re.IGNORECASE),
)
PURCHASE_CONTROL_PATTERN = re.compile(
    r"<(?:button|a|input)\b[^>]*(?:>[^<]*(?:바로\s*구매|구매하기|주문하기|"
    r"buy\s*now|add\s*to\s*cart|place\s*order)[^<]*</(?:button|a)>|"
    r"(?:value|aria-label)=[\"'][^\"']*(?:바로\s*구매|구매하기|주문하기|"
    r"buy\s*now|add\s*to\s*cart)[^\"']*[\"'])",
    re.IGNORECASE | re.DOTALL,
)
BOT_CHALLENGE_PATTERN = re.compile(
    r"cf-turnstile-response|challenge-platform|Enable JavaScript and cookies to continue|"
    r"<title>\s*잠시만 기다리십시오",
    re.IGNORECASE,
)


class LiveBrowserError(RuntimeError):
    """Raised when the local browser verifier cannot produce a receipt."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def find_chrome() -> Path | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        str(Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"),
    ]
    for raw in candidates:
        if raw and Path(raw).is_file():
            return Path(raw).resolve()
    return None


def looks_like_product_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(
        parsed.netloc and PRODUCT_PATH_PATTERN.search(parsed.path + "?" + parsed.query)
    )


def verification_targets(execution: dict[str, Any], *, maximum: int = 12) -> list[str]:
    table_targets: list[str] = []
    result_markdown = execution.get("result_markdown", "")
    if isinstance(result_markdown, str):
        for line in result_markdown.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            for url in MARKDOWN_LINK_PATTERN.findall(line):
                if url not in table_targets:
                    table_targets.append(url)
                if len(table_targets) >= maximum:
                    return table_targets
    if table_targets:
        return table_targets

    targets: list[str] = []
    for item in execution.get("evidence", []):
        if not isinstance(item, dict) or item.get("kind") != "web":
            continue
        source = item.get("source")
        finding = item.get("finding")
        if (
            isinstance(source, str)
            and isinstance(finding, str)
            and looks_like_product_url(source)
            and TRANSACTION_FINDING_PATTERN.search(finding)
            and source not in targets
        ):
            targets.append(source)
        if len(targets) >= maximum:
            break
    return targets


def _plain_excerpt(dom: str, match: re.Match[str], radius: int = 180) -> str:
    start = max(0, match.start() - radius)
    end = min(len(dom), match.end() + radius)
    fragment = re.sub(r"<[^>]+>", " ", dom[start:end])
    fragment = re.sub(r"\s+", " ", html.unescape(fragment)).strip()
    return fragment[:500]


def classify_rendered_dom(url: str, dom: str, *, checked_at: str | None = None) -> dict[str, Any]:
    checked_at = checked_at or utc_now()
    visible_dom = re.sub(
        r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
        " ",
        dom,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for pattern in STRONG_NEGATIVE_PATTERNS:
        match = pattern.search(visible_dom)
        if match:
            return {
                "url": url,
                "status": "sold_out",
                "checked_at": checked_at,
                "signal": match.group(0),
                "excerpt": _plain_excerpt(visible_dom, match),
                "dom_sha256": hashlib.sha256(dom.encode("utf-8")).hexdigest(),
            }

    challenge = BOT_CHALLENGE_PATTERN.search(dom)
    if challenge:
        return {
            "url": url,
            "status": "unknown",
            "checked_at": checked_at,
            "signal": "bot_challenge",
            "excerpt": _plain_excerpt(dom, challenge),
            "dom_sha256": hashlib.sha256(dom.encode("utf-8")).hexdigest(),
        }

    control = PURCHASE_CONTROL_PATTERN.search(visible_dom)
    if control:
        return {
            "url": url,
            "status": "available",
            "checked_at": checked_at,
            "signal": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", control.group(0))).strip()[:160],
            "excerpt": _plain_excerpt(visible_dom, control),
            "dom_sha256": hashlib.sha256(dom.encode("utf-8")).hexdigest(),
        }

    return {
        "url": url,
        "status": "unknown",
        "checked_at": checked_at,
        "signal": "no decisive live purchase control",
        "excerpt": "",
        "dom_sha256": hashlib.sha256(dom.encode("utf-8")).hexdigest(),
    }


def fetch_rendered_dom(url: str, chrome_path: Path, *, timeout_seconds: int = 35) -> str:
    with tempfile.TemporaryDirectory(prefix="psos-live-browser-") as profile:
        completed = subprocess.run(
            [
                str(chrome_path),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=12000",
                "--dump-dom",
                url,
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    if completed.returncode != 0 or not (completed.stdout or "").strip():
        detail = (completed.stderr or "").strip()[-500:]
        raise LiveBrowserError(
            f"Chrome DOM fetch failed for {url} (exit {completed.returncode}): {detail}"
        )
    return completed.stdout


def _verify_one(
    url: str,
    chrome_path: Path,
    fetcher: Callable[[str, Path], str],
) -> dict[str, Any]:
    checked_at = utc_now()
    try:
        dom = fetcher(url, chrome_path)
        return classify_rendered_dom(url, dom, checked_at=checked_at)
    except (OSError, subprocess.SubprocessError, LiveBrowserError) as exc:
        return {
            "url": url,
            "status": "unknown",
            "checked_at": checked_at,
            "signal": "browser_error",
            "excerpt": str(exc)[:500],
            "dom_sha256": None,
        }


def apply_authoritative_browser_result(
    markdown: str,
    verified: list[dict[str, Any]],
    *,
    require_available: bool,
) -> str:
    invalid = [
        item
        for item in verified
        if item["status"] == "unknown"
        or (require_available and item["status"] == "sold_out")
    ]
    invalid_urls = {item["url"] for item in invalid}
    kept_lines = [
        line
        for line in markdown.splitlines()
        if not any(url in line for url in invalid_urls)
    ]
    lines = [
        "## 실시간 브라우저 검증 — 아래 판정이 검색·AI 문구보다 우선합니다",
        "",
    ]
    for item in verified:
        lines.append(
            f"- [{item['status']}] {item['url']} — {item['signal']} "
            f"({item['checked_at']})"
        )
    if invalid:
        lines.extend(
            [
                "",
                "`sold_out`과 `unknown` URL이 포함된 후보 행은 아래 검색 기반 결과에서 제거했습니다.",
            ]
        )
    cleaned = "\n".join(kept_lines).strip()
    return "\n".join(lines).rstrip() + ("\n\n" + cleaned if cleaned else "")


def verify_execution(
    payload: dict[str, Any],
    run_dir: Path,
    label: str,
    *,
    chrome_path: Path | None = None,
    fetcher: Callable[[str, Path], str] = fetch_rendered_dom,
    require_available: bool = True,
) -> dict[str, Any]:
    """Attach a trusted live-browser receipt and downgrade invalid commerce claims."""

    execution = payload.get("execution") if isinstance(payload, dict) else None
    if not isinstance(execution, dict):
        raise LiveBrowserError("execution payload is missing")
    targets = verification_targets(execution)
    if not targets:
        return copy.deepcopy(payload)

    browser = chrome_path or find_chrome()
    result = copy.deepcopy(payload)
    verified: list[dict[str, Any]] = []
    if browser is None:
        checked_at = utc_now()
        verified = [
            {
                "url": url,
                "status": "unknown",
                "checked_at": checked_at,
                "signal": "chrome_not_found",
                "excerpt": "",
                "dom_sha256": None,
            }
            for url in targets
        ]
    else:
        with ThreadPoolExecutor(max_workers=min(4, len(targets))) as pool:
            futures = {
                pool.submit(_verify_one, url, browser, fetcher): url for url in targets
            }
            by_url: dict[str, dict[str, Any]] = {}
            for future in as_completed(futures):
                item = future.result()
                by_url[item["url"]] = item
            verified = [by_url[url] for url in targets]

    receipt = {
        "version": 1,
        "checked_at": utc_now(),
        "browser": str(browser) if browser else None,
        "require_available": require_available,
        "targets": verified,
        "counts": {
            status: sum(item["status"] == status for item in verified)
            for status in ("available", "sold_out", "unknown")
        },
    }
    receipt_name = f"{label}-live-browser.json"
    receipt_path = run_dir / receipt_name
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    current = result["execution"]
    for item in verified:
        current["evidence"].append(
            {
                "source": receipt_name,
                "finding": (
                    f"[LIVE_BROWSER] url={item['url']} status={item['status']} "
                    f"checked_at={item['checked_at']} signal={item['signal']}"
                ),
                "kind": "command_output",
            }
        )
    invalid = [
        item
        for item in verified
        if item["status"] == "unknown"
        or (require_available and item["status"] == "sold_out")
    ]
    current["result_markdown"] = apply_authoritative_browser_result(
        str(current.get("result_markdown", "")),
        verified,
        require_available=require_available,
    )
    current["summary"] = (
        "실시간 브라우저 검증: "
        f"available {receipt['counts']['available']}, "
        f"sold_out {receipt['counts']['sold_out']}, "
        f"unknown {receipt['counts']['unknown']}"
    )
    if invalid and current["status"] not in {"blocked_by_capability", "handoff"}:
        current["status"] = "partial"
        limitation = (
            "실시간 브라우저 검증 미통과: "
            + "; ".join(f"{item['url']}={item['status']}" for item in invalid)
        )
        if limitation not in current["limitations"]:
            current["limitations"].append(limitation)
    return result
