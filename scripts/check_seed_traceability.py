"""Fail-closed Seed release gate; never counts Runtime's own tests."""

import argparse
from pathlib import Path
from agent_meta_seed_harness.evidence import PROFILES, check_traceability


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, required=True)
    args = parser.parse_args()
    problems = check_traceability(Path(__file__).resolve().parents[1], args.profile)
    for problem in problems:
        print(problem)
    print(f"{args.profile}: {'FAILED' if problems else 'VERIFIED'} ({len(problems)} issues)")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
