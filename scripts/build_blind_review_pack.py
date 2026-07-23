from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

CASE_RE = re.compile(r"^## (?P<case_id>[A-Z]+-[A-Z]+-\d+)\s*$", re.MULTILINE)
VARIANT_RE = re.compile(r"^### (?P<variant>[ABCD])\s*$", re.MULTILINE)


def blind_order(case_id: str, seed: str) -> list[str]:
    variants = list("ABCD")
    return sorted(
        variants,
        key=lambda variant: hashlib.sha256(f"{seed}:{case_id}:{variant}".encode()).hexdigest(),
    )


def parse_cases(text: str) -> dict[str, dict[str, str]]:
    matches = list(CASE_RE.finditer(text))
    parsed: dict[str, dict[str, str]] = {}
    for index, match in enumerate(matches):
        case_id = match.group("case_id")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end]
        variant_matches = list(VARIANT_RE.finditer(block))
        variants: dict[str, str] = {}
        for variant_index, variant_match in enumerate(variant_matches):
            variant = variant_match.group("variant")
            variant_end = (
                variant_matches[variant_index + 1].start()
                if variant_index + 1 < len(variant_matches)
                else len(block)
            )
            variants[variant] = block[variant_match.end():variant_end].strip()
        if set(variants) != set("ABCD"):
            raise ValueError(f"{case_id}: expected A-D, found {sorted(variants)}")
        parsed[case_id] = variants
    if not parsed:
        raise ValueError("No case sections found")
    return parsed


def build(input_path: Path, output_path: Path, mapping_path: Path, seed: str) -> None:
    cases = parse_cases(input_path.read_text(encoding="utf-8"))
    output_lines = [
        "# Blind Review Pack",
        "",
        "Judge the outputs without opening the mapping file. Record only observable differences.",
        "",
    ]
    mapping_rows: list[tuple[str, str, str]] = []

    for case_id, variants in cases.items():
        output_lines.extend([f"## {case_id}", ""])
        for number, variant in enumerate(blind_order(case_id, seed), start=1):
            output_id = f"O{number}"
            output_lines.extend([f"### {output_id}", "", variants[variant], ""])
            mapping_rows.append((case_id, output_id, variant))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "blinded_output_id", "actual_variant"])
        writer.writerows(mapping_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--seed", default="corpus-restoration-v1")
    args = parser.parse_args()
    build(args.input, args.output, args.mapping, args.seed)


if __name__ == "__main__":
    main()
