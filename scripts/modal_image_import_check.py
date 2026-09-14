"""Offline import reservation, idempotence, provenance and ambiguity checks."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
import unittest

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger, LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_image_import import TrainingImageImport, RESERVATION_MICRO_USD


class FakeBackend:
    def __init__(self):
        self.builds = 0
        self.failure = False

    async def scope(self, scope):
        return {**scope, "checked_at": datetime.now(timezone.utc).isoformat()}

    async def build(self, image, scope):
        self.builds += 1
        if self.failure:
            raise TimeoutError("unknown provider outcome")
        return "im-offline"


class ImageImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.ledger = CampaignLedger(self.root / "ledger.sqlite")
        self.ledger.initialize("offline-import")
        self.backend = FakeBackend()
        self.importer = TrainingImageImport(self.ledger, self.backend)
        self.scope = {"workspace": "test", "environment": "main", "environment_id": "en-test",
                      "app": "gameworld-test", "app_id": "ap-test", "isolation_policy": "app-scoped"}
        data = canonical({"schema_version": 1, "source_revision": "a" * 40,
                          "image": "ghcr.io/trycua/gameworld-autoresearch@sha256:" + "b" * 64})
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes(data)
        self.expected = digest(data)

    def run_import(self):
        return asyncio.run(self.importer.run(self.scope, self.manifest, self.expected))

    def test_import_reserves_and_replay_does_not_rebuild_or_refund(self):
        result = self.run_import()
        self.assertEqual(self.backend.builds, 1)
        self.assertEqual(self.run_import(), result)
        self.assertEqual(self.backend.builds, 1)
        holds = self.ledger.snapshot()["reservations"]
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0]["state"], "held")
        self.assertEqual(holds[0]["amount"], RESERVATION_MICRO_USD)
        self.assertFalse(result["billing_reconciled"])

    def test_budget_refusal_prevents_import(self):
        self.ledger.reserve("other", "modal_micro_usd", 1_790_000_000, int(time.time()) + 3600)
        with self.assertRaises(BudgetRefused):
            self.run_import()
        self.assertEqual(self.backend.builds, 0)

    def test_ambiguous_outcome_keeps_hold_and_never_retries(self):
        self.backend.failure = True
        with self.assertRaises(TimeoutError):
            self.run_import()
        with self.assertRaises(LedgerConflict):
            self.run_import()
        self.assertEqual(self.backend.builds, 1)
        self.assertEqual(self.ledger.snapshot()["reservations"][0]["state"], "held")
        self.importer = TrainingImageImport(self.ledger, self.backend)
        with self.assertRaises(LedgerConflict):
            self.run_import()

    def test_bad_provenance_or_mutable_tag_prevents_import(self):
        self.expected = "c" * 64
        with self.assertRaises(ValueError):
            self.run_import()
        data = canonical({"schema_version": 1, "source_revision": "a" * 40,
                          "image": "ghcr.io/trycua/gameworld-autoresearch:latest"})
        self.manifest.write_bytes(data)
        self.expected = digest(data)
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertEqual(self.backend.builds, 0)
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_scope_mismatch_prevents_import(self):
        self.scope["app_id"] = None
        with self.assertRaises(ValueError):
            self.run_import()
        self.assertEqual(self.backend.builds, 0)


if __name__ == "__main__":
    unittest.main()
