"""Offline checks for accounting-preserving campaign protocol forks."""

from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from fps_bench.campaign_ledger import CampaignLedger
from scripts.campaign_protocol_fork import fork


class CampaignProtocolForkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.sqlite"
        self.destination = self.root / "destination.sqlite"
        self.receipt = self.root / "fork.json"
        self.ledger = CampaignLedger(self.source)
        self.ledger.initialize("old-campaign")
        self.ledger.record_prior_usage("provider-row", "modal_micro_usd", 1234, "provider-receipt")
        self.ledger.reserve("completed", "modal_micro_usd", 5000, int(time.time()) + 600)
        self.ledger.settle("completed", 4000, "settled-receipt")
        with self.ledger.transaction() as connection:
            connection.execute("CREATE TABLE controller(singleton INTEGER PRIMARY KEY, contract_hash TEXT)")
            connection.execute("INSERT INTO controller VALUES (1,'old-contract')")
            connection.execute("CREATE TABLE gameworld_workflows(id TEXT PRIMARY KEY)")

    def test_fork_preserves_accounting_and_drops_protocol_state(self):
        before = self.ledger.snapshot()
        receipt = fork(self.source, self.destination, "new-campaign", self.receipt)
        after = CampaignLedger(self.destination).snapshot()
        self.assertEqual(after["resources"], before["resources"])
        self.assertEqual(after["reservations"], before["reservations"])
        self.assertEqual(after["prior_usage"], before["prior_usage"])
        self.assertEqual(after["campaign"]["id"], "new-campaign")
        with sqlite3.connect(self.destination) as connection:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("controller", tables)
        self.assertNotIn("gameworld_workflows", tables)
        self.assertEqual(receipt["preserved_reservations"], 1)

    def test_active_hold_refuses_fork_without_output(self):
        self.ledger.reserve("active", "modal_micro_usd", 100, int(time.time()) + 600)
        with self.assertRaises(ValueError):
            fork(self.source, self.destination, "new-campaign", self.receipt)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.receipt.exists())

    def test_completed_image_import_hold_carries_forward(self):
        self.ledger.reserve("image-import:one", "modal_micro_usd", 100, int(time.time()) + 600)
        with self.ledger.transaction() as connection:
            connection.execute("CREATE TABLE training_image_imports ("
                               "id TEXT PRIMARY KEY, specification TEXT NOT NULL, state TEXT NOT NULL, "
                               "image_id TEXT, error_type TEXT)")
            connection.execute("INSERT INTO training_image_imports VALUES (?,?,'complete',?,NULL)",
                               ("image-import:one", "{}", "im-test"))
        fork(self.source, self.destination, "new-campaign", self.receipt)
        snapshot = CampaignLedger(self.destination).snapshot()
        held = next(row for row in snapshot["reservations"] if row["id"] == "image-import:one")
        self.assertEqual(held["state"], "held")
        with sqlite3.connect(self.destination) as connection:
            self.assertEqual(connection.execute(
                "SELECT image_id FROM training_image_imports WHERE id='image-import:one'").fetchone()[0],
                             "im-test")


if __name__ == "__main__":
    unittest.main()
