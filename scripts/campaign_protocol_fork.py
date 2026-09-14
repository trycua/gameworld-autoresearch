"""Fork terminal campaign accounting into a fresh protocol-bound ledger."""

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
ACCOUNTING_TABLES = {
    "campaign", "events", "limits", "modal_prior_scope", "modal_reconciliation_groups",
    "modal_reconciliation_members", "modal_reconciliation_observations",
    "modal_reconciliation_rows", "prior_usage", "reservations", "sqlite_sequence",
    "training_image_imports",
}
PROTOCOL_TABLES = {
    "candidates", "controller", "decisions", "jobs", "private_split_leases", "promotions",
    "modal_training_attempts", "modal_training_launches", "modal_training_transfers",
}


def _tables(connection):
    return {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _validate_terminal(connection):
    tables = _tables(connection)
    unknown = tables - ACCOUNTING_TABLES - PROTOCOL_TABLES - {
        name for name in tables if name.startswith("gameworld_")}
    if unknown:
        raise ValueError(f"Unknown campaign tables require an explicit fork policy: {sorted(unknown)}")
    if "jobs" in tables and connection.execute(
            "SELECT 1 FROM jobs WHERE state!='cleaned' LIMIT 1").fetchone():
        raise ValueError("Protocol fork requires every controller job to be cleaned")
    held = {row[0] for row in connection.execute(
        "SELECT id FROM reservations WHERE state='held'")}
    completed_imports = ({row[0] for row in connection.execute(
        "SELECT id FROM training_image_imports WHERE state='complete'")}
                         if "training_image_imports" in tables else set())
    if held - completed_imports:
        raise ValueError("Protocol fork requires every non-import resource hold to be terminal")
    if "training_image_imports" in tables and connection.execute(
            "SELECT 1 FROM training_image_imports WHERE state!='complete' LIMIT 1").fetchone():
        raise ValueError("Protocol fork requires every image import to be complete")
    return tables


def fork(source, destination, campaign, receipt_path):
    source, destination, receipt_path = map(Path, (source, destination, receipt_path))
    if not IDENTIFIER.fullmatch(campaign):
        raise ValueError("Fresh campaign identity required")
    if (not source.is_file() or source.is_symlink() or destination.exists()
            or receipt_path.exists() or destination.resolve() == source.resolve()):
        raise ValueError("Protocol fork paths must be regular, distinct and new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    source_ledger = CampaignLedger(source)
    source_snapshot = source_ledger.snapshot()
    descriptor, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    temporary.unlink()
    try:
        source_connection = sqlite3.connect(source)
        source_connection.row_factory = sqlite3.Row
        target = sqlite3.connect(temporary)
        try:
            source_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            tables = _validate_terminal(source_connection)
            source_connection.backup(target)
        finally:
            target.close()
            source_connection.close()
        if source_ledger.snapshot() != source_snapshot:
            raise RuntimeError("Source campaign changed during protocol fork")
        source_snapshot_sha256 = digest(canonical(source_snapshot))
        target = sqlite3.connect(temporary)
        target.row_factory = sqlite3.Row
        try:
            target.execute("PRAGMA foreign_keys=OFF")
            target.execute("BEGIN IMMEDIATE")
            for table in sorted(tables - ACCOUNTING_TABLES):
                target.execute(f'DROP TABLE "{table}"')
            previous = target.execute("SELECT id FROM campaign").fetchone()[0]
            if previous == campaign:
                raise ValueError("Protocol fork requires a new campaign identity")
            target.execute("UPDATE campaign SET id=?", (campaign,))
            payload = {"previous_campaign": previous, "campaign": campaign,
                       "source_snapshot_sha256": source_snapshot_sha256}
            target.execute("INSERT INTO events(timestamp,kind,payload) VALUES (strftime('%s','now'),?,?)",
                           ("campaign_protocol_forked", canonical(payload).decode()))
            target.commit()
        finally:
            target.close()
        os.chmod(temporary, 0o600)
        temporary.rename(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    destination_snapshot = CampaignLedger(destination).snapshot()
    for key in ("resources", "reservations", "prior_usage", "reconciled_modal_groups"):
        if destination_snapshot[key] != source_snapshot[key]:
            raise RuntimeError(f"Fork changed campaign accounting: {key}")
    if (destination_snapshot["campaign"]["id"] != campaign
            or destination_snapshot["campaign"]["frozen"] != source_snapshot["campaign"]["frozen"]
            or destination_snapshot["campaign"]["reason"] != source_snapshot["campaign"]["reason"]
            or destination_snapshot["event_count"] != source_snapshot["event_count"] + 1):
        raise RuntimeError("Fork changed campaign status or event custody")
    receipt = {
        "schema_version": 1, "source": str(source.resolve()),
        "source_campaign": source_snapshot["campaign"]["id"],
        "source_snapshot_sha256": source_snapshot_sha256,
        "destination": str(destination.resolve()), "campaign": campaign,
        "destination_database_sha256": digest(destination.read_bytes()),
        "accounting": destination_snapshot["resources"],
        "preserved_reservations": len(destination_snapshot["reservations"]),
        "preserved_prior_usage": len(destination_snapshot["prior_usage"]),
        "event_count": destination_snapshot["event_count"],
    }
    exclusive_write(receipt_path, canonical(receipt), 0o400)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fork(args.source, args.destination, args.campaign, args.receipt), sort_keys=True))


if __name__ == "__main__":
    main()
