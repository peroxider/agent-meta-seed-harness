"""Prepare the exact tested candidate after all consumer gates pass."""

import argparse
from pathlib import Path
from agent_meta_runtime.sdk.packages import canonical_json
from agent_meta_seed_harness.evidence import PROFILES
from agent_meta_seed_harness.release import ReleaseNotReady, release_candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--output", type=Path, help="candidate manifest destination; existing different bytes are refused")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        candidate = release_candidate(root, args.profile)
    except ReleaseNotReady as error:
        for issue in error.issues:
            print(issue)
        print("Release refused: required consumer evidence is incomplete.")
        return 1
    output = args.output or root / "dist/release" / args.profile / "candidate.json"
    raw = canonical_json(candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("refusing to overwrite a different release candidate")
    else:
        with output.open("xb") as stream:
            stream.write(raw)
    print(f"Prepared exact tested candidate for operator review: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
