"""Run after installing the Seed wheel; works from any working directory."""

from pathlib import Path
from agent_meta_seed_harness.boundary import check_project

if __name__ == "__main__":
    issues = check_project(Path(__file__).resolve().parents[1])
    for issue in issues:
        print(issue)
    raise SystemExit(bool(issues))
