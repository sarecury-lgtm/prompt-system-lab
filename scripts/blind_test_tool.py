from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALGORITHM_VERSION = "blind-hmac-sha256-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_distinct_paths(input_dir: Path, session_dir: Path) -> None:
    input_resolved = input_dir.resolve()
    session_resolved = session_dir.resolve()
    if input_resolved == session_resolved:
        raise ValueError("session_dir must be different from input_dir")
    if input_resolved in session_resolved.parents:
        raise ValueError("session_dir must not be inside input_dir")


def collect_files(input_dir: Path) -> list[dict[str, Any]]:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    records: list[dict[str, Any]] = []
    for path in sorted(p for p in input_dir.rglob("*") if p.is_file()):
        relpath = path.relative_to(input_dir).as_posix()
        records.append(
            {
                "relative_path": relpath,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if len(records) < 2:
        raise ValueError("At least two input files are required for a blind test")
    return records


def canonical_input_digest(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_bytes(canonical)


def derive_shuffle_seed(secret_seed: bytes, external_nonce: str) -> bytes:
    return hmac.new(
        secret_seed,
        (ALGORITHM_VERSION + "\0" + external_nonce).encode("utf-8"),
        hashlib.sha256,
    ).digest()


def ranked_records(
    records: list[dict[str, Any]], secret_seed: bytes, external_nonce: str
) -> list[dict[str, Any]]:
    derived_seed = derive_shuffle_seed(secret_seed, external_nonce)
    ranked: list[dict[str, Any]] = []
    for record in records:
        message = (
            record["relative_path"]
            + "\0"
            + record["sha256"]
            + "\0"
            + str(record["size_bytes"])
        ).encode("utf-8")
        rank_key = hmac.new(derived_seed, message, hashlib.sha256).hexdigest()
        ranked.append({**record, "rank_key": rank_key})
    return sorted(ranked, key=lambda item: (item["rank_key"], item["relative_path"]))


def blind_filename(blind_id: str, original_relative_path: str) -> str:
    suffixes = "".join(Path(original_relative_path).suffixes)
    return f"{blind_id}{suffixes}"


def load_secret_seed(session_dir: Path) -> bytes:
    seed_path = session_dir / "private" / "secret_seed.hex"
    if not seed_path.exists():
        raise FileNotFoundError(f"Missing private seed: {seed_path}")
    try:
        return bytes.fromhex(seed_path.read_text(encoding="utf-8").strip())
    except ValueError as exc:
        raise ValueError("private/secret_seed.hex is not valid hexadecimal") from exc


def command_commit(args: argparse.Namespace) -> None:
    input_dir = args.input_dir
    session_dir = args.session_dir
    ensure_distinct_paths(input_dir, session_dir)

    if session_dir.exists() and any(session_dir.iterdir()) and not args.force:
        raise FileExistsError(
            f"Session directory is not empty: {session_dir}. Use --force to replace it."
        )
    if args.force and session_dir.exists():
        shutil.rmtree(session_dir)

    records = collect_files(input_dir)
    secret_seed = bytes.fromhex(args.seed_hex) if args.seed_hex else secrets.token_bytes(32)
    if len(secret_seed) < 16:
        raise ValueError("Seed must contain at least 16 bytes")

    input_digest = canonical_input_digest(records)
    seed_commitment = sha256_bytes(secret_seed)

    write_json(
        session_dir / "public" / "commitment.json",
        {
            "version": 1,
            "algorithm": ALGORITHM_VERSION,
            "created_at_utc": utc_now(),
            "item_count": len(records),
            "input_set_sha256": input_digest,
            "seed_commitment_sha256": seed_commitment,
            "next_step": (
                "Publish or timestamp this file before choosing the external nonce. "
                "Do not share anything under private/."
            ),
        },
    )
    write_json(
        session_dir / "private" / "input_snapshot.json",
        {
            "version": 1,
            "algorithm": ALGORITHM_VERSION,
            "input_root": str(input_dir.resolve()),
            "input_set_sha256": input_digest,
            "items": records,
        },
    )
    seed_path = session_dir / "private" / "secret_seed.hex"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(secret_seed.hex() + "\n", encoding="utf-8")
    (session_dir / "private" / "DO_NOT_SHARE.txt").write_text(
        "Keep this directory private until scoring is complete.\n",
        encoding="utf-8",
    )

    print(f"Committed {len(records)} files.")
    print(f"Public commitment: {session_dir / 'public' / 'commitment.json'}")
    print("Publish or timestamp commitment.json before running shuffle for stronger auditability.")


def command_shuffle(args: argparse.Namespace) -> None:
    input_dir = args.input_dir
    session_dir = args.session_dir
    ensure_distinct_paths(input_dir, session_dir)

    commitment_path = session_dir / "public" / "commitment.json"
    snapshot_path = session_dir / "private" / "input_snapshot.json"
    if not commitment_path.exists() or not snapshot_path.exists():
        raise FileNotFoundError("Run the commit command first")

    commitment = read_json(commitment_path)
    snapshot = read_json(snapshot_path)
    secret_seed = load_secret_seed(session_dir)

    current_records = collect_files(input_dir)
    current_digest = canonical_input_digest(current_records)
    if current_digest != snapshot["input_set_sha256"]:
        raise ValueError("Input files changed after commitment; start a new session")
    if sha256_bytes(secret_seed) != commitment["seed_commitment_sha256"]:
        raise ValueError("Secret seed does not match the published commitment")

    blind_dir = session_dir / "public" / "blind_files"
    if blind_dir.exists():
        if not args.force:
            raise FileExistsError(
                f"Blind output already exists: {blind_dir}. Use --force to rebuild."
            )
        shutil.rmtree(blind_dir)
    blind_dir.mkdir(parents=True, exist_ok=True)

    ordered = ranked_records(current_records, secret_seed, args.external_nonce)
    width = max(3, len(str(len(ordered))))
    mapping: list[dict[str, Any]] = []
    public_items: list[dict[str, Any]] = []

    for index, record in enumerate(ordered, start=1):
        blind_id = f"{args.label_prefix}{index:0{width}d}"
        filename = blind_filename(blind_id, record["relative_path"])
        source = input_dir / record["relative_path"]
        destination = blind_dir / filename
        shutil.copyfile(source, destination)

        mapping.append(
            {
                "blind_id": blind_id,
                "blind_filename": filename,
                "original_relative_path": record["relative_path"],
                "sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
                "rank_key": record["rank_key"],
            }
        )
        public_items.append(
            {
                "blind_id": blind_id,
                "blind_filename": filename,
                "sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
            }
        )

    write_json(
        session_dir / "public" / "blind_manifest.json",
        {
            "version": 1,
            "algorithm": ALGORITHM_VERSION,
            "created_at_utc": utc_now(),
            "external_nonce": args.external_nonce,
            "external_nonce_note": args.external_nonce_note,
            "input_set_sha256": current_digest,
            "seed_commitment_sha256": commitment["seed_commitment_sha256"],
            "items": public_items,
        },
    )
    write_json(
        session_dir / "private" / "mapping.json",
        {
            "version": 1,
            "algorithm": ALGORITHM_VERSION,
            "external_nonce": args.external_nonce,
            "external_nonce_note": args.external_nonce_note,
            "items": mapping,
        },
    )
    print(f"Created blind pack with {len(mapping)} files: {blind_dir}")
    print("Share only the public/ directory until scoring is complete.")


def command_prepare(args: argparse.Namespace) -> None:
    commit_args = argparse.Namespace(
        input_dir=args.input_dir,
        session_dir=args.session_dir,
        force=args.force,
        seed_hex=args.seed_hex,
    )
    command_commit(commit_args)
    shuffle_args = argparse.Namespace(
        input_dir=args.input_dir,
        session_dir=args.session_dir,
        force=True,
        external_nonce=args.external_nonce,
        external_nonce_note=args.external_nonce_note,
        label_prefix=args.label_prefix,
    )
    command_shuffle(shuffle_args)


def command_reveal(args: argparse.Namespace) -> None:
    session_dir = args.session_dir
    commitment = read_json(session_dir / "public" / "commitment.json")
    manifest = read_json(session_dir / "public" / "blind_manifest.json")
    mapping = read_json(session_dir / "private" / "mapping.json")
    secret_seed = load_secret_seed(session_dir)

    reveal = {
        "version": 1,
        "algorithm": ALGORITHM_VERSION,
        "revealed_at_utc": utc_now(),
        "secret_seed_hex": secret_seed.hex(),
        "seed_commitment_sha256": commitment["seed_commitment_sha256"],
        "external_nonce": manifest["external_nonce"],
        "external_nonce_note": manifest.get("external_nonce_note", ""),
        "input_set_sha256": commitment["input_set_sha256"],
        "items": mapping["items"],
    }
    write_json(session_dir / "reveal" / "reveal.json", reveal)
    print(f"Reveal package created: {session_dir / 'reveal' / 'reveal.json'}")


def command_verify(args: argparse.Namespace) -> None:
    input_dir = args.input_dir
    session_dir = args.session_dir
    ensure_distinct_paths(input_dir, session_dir)

    commitment = read_json(session_dir / "public" / "commitment.json")
    manifest = read_json(session_dir / "public" / "blind_manifest.json")
    reveal = read_json(session_dir / "reveal" / "reveal.json")
    secret_seed = bytes.fromhex(reveal["secret_seed_hex"])

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check(
        "algorithm_version",
        commitment.get("algorithm") == ALGORITHM_VERSION
        and manifest.get("algorithm") == ALGORITHM_VERSION
        and reveal.get("algorithm") == ALGORITHM_VERSION,
        ALGORITHM_VERSION,
    )
    calculated_commitment = sha256_bytes(secret_seed)
    check(
        "seed_commitment",
        calculated_commitment == commitment["seed_commitment_sha256"],
        calculated_commitment,
    )

    current_records = collect_files(input_dir)
    current_digest = canonical_input_digest(current_records)
    check(
        "input_set_digest",
        current_digest == commitment["input_set_sha256"],
        current_digest,
    )

    external_nonce = reveal["external_nonce"]
    recomputed = ranked_records(current_records, secret_seed, external_nonce)
    width = max(3, len(str(len(recomputed))))
    expected_mapping: list[dict[str, Any]] = []
    label_prefix = ""
    if reveal["items"]:
        first_id = reveal["items"][0]["blind_id"]
        label_prefix = first_id.rstrip("0123456789")
    for index, record in enumerate(recomputed, start=1):
        blind_id = f"{label_prefix}{index:0{width}d}"
        expected_mapping.append(
            {
                "blind_id": blind_id,
                "original_relative_path": record["relative_path"],
                "sha256": record["sha256"],
                "size_bytes": record["size_bytes"],
                "rank_key": record["rank_key"],
            }
        )

    revealed_core = [
        {
            "blind_id": item["blind_id"],
            "original_relative_path": item["original_relative_path"],
            "sha256": item["sha256"],
            "size_bytes": item["size_bytes"],
            "rank_key": item["rank_key"],
        }
        for item in reveal["items"]
    ]
    check(
        "recomputed_order_matches_reveal",
        expected_mapping == revealed_core,
        f"expected {len(expected_mapping)} mappings, revealed {len(revealed_core)}",
    )

    blind_dir = session_dir / "public" / "blind_files"
    manifest_by_id = {item["blind_id"]: item for item in manifest["items"]}
    files_ok = True
    file_details: list[str] = []
    for item in reveal["items"]:
        blind_id = item["blind_id"]
        manifest_item = manifest_by_id.get(blind_id)
        if manifest_item is None:
            files_ok = False
            file_details.append(f"missing manifest item {blind_id}")
            continue
        blind_path = blind_dir / manifest_item["blind_filename"]
        if not blind_path.exists():
            files_ok = False
            file_details.append(f"missing blind file {blind_path.name}")
            continue
        digest = sha256_file(blind_path)
        if digest != item["sha256"]:
            files_ok = False
            file_details.append(f"hash mismatch {blind_path.name}")
    check(
        "blind_file_hashes",
        files_ok,
        "; ".join(file_details) if file_details else "all blind file hashes match",
    )

    passed = all(item["passed"] for item in checks)
    report = {
        "version": 1,
        "algorithm": ALGORITHM_VERSION,
        "verified_at_utc": utc_now(),
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "important_limit": (
            "PASS proves the published commitment, revealed seed, mapping, and file bytes are consistent. "
            "Without an external nonce chosen after commitment, it cannot prove the creator did not reroll "
            "seeds before publishing the commitment."
        ),
    }
    write_json(session_dir / "verification_report.json", report)
    print(report["result"])
    for item in checks:
        mark = "OK" if item["passed"] else "FAIL"
        print(f"[{mark}] {item['check']}: {item['detail']}")
    if not passed:
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create and audit blind-test file packs using commit-reveal randomness. "
            "Uses only the Python standard library."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_paths(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("input_dir", type=Path)
        subparser.add_argument("session_dir", type=Path)

    commit_parser = subparsers.add_parser("commit", help="Commit to inputs and a secret seed")
    add_common_paths(commit_parser)
    commit_parser.add_argument("--force", action="store_true")
    commit_parser.add_argument("--seed-hex", help=argparse.SUPPRESS)
    commit_parser.set_defaults(func=command_commit)

    shuffle_parser = subparsers.add_parser("shuffle", help="Create the blinded file pack")
    add_common_paths(shuffle_parser)
    shuffle_parser.add_argument("--external-nonce", default="")
    shuffle_parser.add_argument("--external-nonce-note", default="")
    shuffle_parser.add_argument("--label-prefix", default="O")
    shuffle_parser.add_argument("--force", action="store_true")
    shuffle_parser.set_defaults(func=command_shuffle)

    prepare_parser = subparsers.add_parser(
        "prepare", help="One-step commit and shuffle for casual/internal use"
    )
    add_common_paths(prepare_parser)
    prepare_parser.add_argument("--external-nonce", default="")
    prepare_parser.add_argument("--external-nonce-note", default="")
    prepare_parser.add_argument("--label-prefix", default="O")
    prepare_parser.add_argument("--force", action="store_true")
    prepare_parser.add_argument("--seed-hex", help=argparse.SUPPRESS)
    prepare_parser.set_defaults(func=command_prepare)

    reveal_parser = subparsers.add_parser("reveal", help="Create the post-scoring reveal package")
    reveal_parser.add_argument("session_dir", type=Path)
    reveal_parser.set_defaults(func=command_reveal)

    verify_parser = subparsers.add_parser("verify", help="Verify randomness and file integrity")
    add_common_paths(verify_parser)
    verify_parser.set_defaults(func=command_verify)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
