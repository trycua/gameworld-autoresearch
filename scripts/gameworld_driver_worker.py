"""Apply, rebuild and verify one approved cua-driver candidate in a Fleet worker."""

import argparse
import json
from pathlib import Path

from fps_bench.driver_candidate import materialize_driver_candidate
from fps_bench.gameworld_research import load_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("/opt/gameworld-autoresearch"))
    parser.add_argument("--policy", type=Path, default=Path("/opt/gameworld-autoresearch/configs/gameworld-autoresearch.json"))
    args = parser.parse_args()
    policy, _ = load_policy(args.policy, args.root / "configs/evaluation/gameworld-suite-v1.json")
    result = materialize_driver_candidate(
        args.proposal, args.proposal_sha256, args.patch, args.output, policy, args.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
