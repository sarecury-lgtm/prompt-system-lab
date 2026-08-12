#!/usr/bin/env python3
"""Select comment lines that are likely to contain externally verifiable claims."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


CLAIM_MARKERS = re.compile(
    r"(?:\d|년|월|일|퍼센트|%|판결|징역|벌금|통계|조사|발생|사망|증가|감소|"
    r"정부|법원|경찰|검찰|공식|보도)",
    re.IGNORECASE,
)


def candidate_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and CLAIM_MARKERS.search(line)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 text file")
    args = parser.parse_args()
    text = args.input.read_text(encoding="utf-8")
    for line in candidate_lines(text):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
