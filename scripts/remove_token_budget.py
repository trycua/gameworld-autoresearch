"""Apply the user-authorized token policy removal with a backup and immutable receipt."""

import argparse
import json
import os
from pathlib import Path
import sqlite3

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write


def migrate(database, output):
    database, output = Path(database), Path(output)
    if not database.is_file() or database.is_symlink():
        raise ValueError("Existing canonical database required")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    backup = output / "before.sqlite"
    source, destination = sqlite3.connect(database), sqlite3.connect(backup)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    os.chmod(backup, 0o400)
    ledger = CampaignLedger(database)
    before = ledger.snapshot()
    exclusive_write(output / "before.json", canonical(before), 0o400)
    result = ledger.remove_token_budget()
    after = ledger.snapshot()
    if (before['resources']['modal_micro_usd'] != after['resources']['modal_micro_usd']
            or [row for row in before['reservations'] if row['resource'] == 'modal_micro_usd']
            != [row for row in after['reservations'] if row['resource'] == 'modal_micro_usd']
            or before['prior_usage'] != after['prior_usage']
            or before['reconciled_modal_groups'] != after['reconciled_modal_groups']):
        raise RuntimeError("Token policy migration changed unrelated accounting")
    exclusive_write(output / "after.json", canonical(after), 0o400)
    receipt = {"campaign": after['campaign']['id'], "backup_sha256": digest(backup.read_bytes()),
               "result": result, "modal_unchanged": True}
    exclusive_write(output / "receipt.json", canonical(receipt), 0o400)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--authorize-removal', required=True, action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.database, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
