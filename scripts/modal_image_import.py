"""Run one supervised public-image import; keep its $25 reservation until settlement."""

import argparse
import asyncio
import json
from pathlib import Path

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.modal_image_import import TrainingImageImport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--provenance-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--supervised-probe", action="store_true", required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing canonical campaign ledger required")
    ledger = CampaignLedger(args.database)
    if ledger.snapshot()["campaign"]["id"] != args.campaign:
        parser.error("Campaign identity mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    scope = json.loads(args.scope.read_bytes())
    result = asyncio.run(TrainingImageImport(ledger).run(scope, args.provenance, args.provenance_sha256))
    exclusive_write(args.output / "import.json", canonical(result))
    exclusive_write(args.output / "ledger-after.json", canonical(ledger.snapshot()))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
