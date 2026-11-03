"""Offline, explicit preparation; no adjacent-checkout discovery or HTTP.

The receipt is local text-encoding evidence, not a Runtime Provider descriptor.
The operator supplies downloaded author files and an absent output directory.
The template is verified as data and never executed by this command.
"""

import argparse
import hashlib
import json
from pathlib import Path

from agent_meta_seed_harness.providers.tokenizer import (
    TokenizerUnavailable,
    load_glm53flash_text_encoder,
    tokenizer_lock,
    verify_tokenizer_asset,
)


def prepare(assets_dir, output_dir, vectors_path):
    """Read bounded explicit files; publish the receipt only after verification."""
    assets_dir, output_dir = Path(assets_dir), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("tokenizer output directory already exists")
    lock = tokenizer_lock()
    assets = {}
    for name, expected in lock["files"].items():
        path = assets_dir / name
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise TokenizerUnavailable(
                "tokenizer preparation requires ordinary input files"
            )
        with path.open("rb") as handle:
            assets[name] = verify_tokenizer_asset(
                name, handle.read(expected["bytes"] + 1)
            )
    with Path(vectors_path).open("rb") as handle:
        raw_vectors = handle.read(65537)
    if (
        len(raw_vectors) > 65536
        or hashlib.sha256(raw_vectors).hexdigest() != lock["vectors_sha256"]
    ):
        raise ValueError("tokenizer vector file differs from lock")
    vectors = json.loads(raw_vectors)
    if (
        vectors["schema"] != "seed/local-tokenizer-vectors/v1"
        or vectors["tokenizer_id"] != lock["tokenizer_id"]
        or len(vectors["cases"]) != 7
    ):
        raise ValueError("tokenizer vectors differ from the declared profile")

    encoder = load_glm53flash_text_encoder(assets["tokenizer.json"])
    for case in vectors["cases"]:
        expected = tuple(case["ids"])
        if (
            encoder.encode(case["text"]) != expected
            or encoder.encode(case["text"]) != expected
            or encoder.count(case["text"]) != len(expected)
        ):
            raise ValueError("local tokenizer differs from frozen vectors")
    # All reads and checks precede output creation. A receipt is written last;
    # an I/O failure leaves an incomplete directory, never a successful receipt.
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, raw in assets.items():
        (output_dir / name).write_bytes(raw)
    (output_dir / "local-encoding-v1.json").write_bytes(raw_vectors)
    (output_dir / "tokenizer-lock.json").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    receipt = {
        "schema": "seed/local-tokenizer-preparation/v1",
        "status": "VERIFIED_LOCAL_TEXT_ENCODING_ONLY",
        "tokenizer_id": encoder.tokenizer_id,
        "repository": lock["repository"],
        "revision": lock["revision"],
        "engine": lock["engine"],
        "files": lock["files"],
        "vectors_sha256": hashlib.sha256(raw_vectors).hexdigest(),
        "vector_cases_verified": len(vectors["cases"]),
        "template_executed": False,
        "external_provider_requests": 0,
        "gateway_template_equivalence_verified": False,
        "host_admission_tokenizer_available": False,
        "s04_complete": False,
        "release_complete": False,
    }
    (output_dir / "verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vectors", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.assets_dir, args.output_dir, args.vectors)
    except FileExistsError:
        print(json.dumps({"status": "REFUSED", "error_code": "OUTPUT_EXISTS"}))
        return 3
    except (ValueError, OSError):
        print(
            json.dumps(
                {"status": "FAILED", "error_code": "TOKENIZER_PREPARATION_UNAVAILABLE"}
            )
        )
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "vector_cases_verified",
                    "external_provider_requests",
                    "host_admission_tokenizer_available",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
