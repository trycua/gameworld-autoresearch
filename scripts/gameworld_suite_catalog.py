"""Generate the pinned all-game GameWorld auto-research catalog."""

import argparse
import json
from pathlib import Path

from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.gameworld_suite_catalog import discover, validate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = discover(args.upstream, args.games)
    exclusive_write(args.output, canonical(manifest))
    print(json.dumps(validate(manifest)))
