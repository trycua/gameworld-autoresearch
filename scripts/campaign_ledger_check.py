"""Run with python -m unittest discover -s scripts -p campaign_ledger_check.py."""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger, LedgerConflict, accounting_totals


def concurrent_reserve(arguments):
    path, index, deadline = arguments
    try:
        CampaignLedger(path).reserve(str(index), "litellm_tokens", 100_000_000, deadline)
        return True
    except BudgetRefused:
        return False


class CampaignLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "campaign.sqlite"
        self.ledger = CampaignLedger(self.path)
        self.ledger.initialize("test-campaign")
        self.deadline = int(time.time()) + 3600

    def hold(self, name="job", amount=100, resource="litellm_tokens", purpose="normal"):
        return self.ledger.reserve(name, resource, amount, self.deadline, purpose)

    def test_normal_modal_cannot_spend_shutdown_reserve(self):
        self.hold(amount=1_800_000_000, resource="modal_micro_usd")
        with self.assertRaises(BudgetRefused):
            self.hold("extra", 1, "modal_micro_usd")
        self.hold("cleanup", 200_000_000, "modal_micro_usd", "shutdown")
        with self.assertRaises(BudgetRefused):
            self.hold("cleanup-extra", 1, "modal_micro_usd", "shutdown")

    def test_token_policy_removal_preserves_modal_and_history(self):
        self.hold("litellm:unknown", 3342336)
        self.hold("modal", 5_000_000, "modal_micro_usd")
        self.ledger.freeze("Ambiguous upstream usage for litellm:unknown")
        before = self.ledger.snapshot()
        result = self.ledger.remove_token_budget()
        after = self.ledger.snapshot()
        self.assertTrue(result["token_freeze_cleared"])
        self.assertFalse(after["campaign"]["frozen"])
        self.assertEqual(before["resources"]["modal_micro_usd"], after["resources"]["modal_micro_usd"])
        token = next(row for row in after["reservations"] if row["id"] == "litellm:unknown")
        self.assertEqual(token["state"], "retired_token_policy")
        self.assertIsNone(token["actual"])
        self.assertIsNone(after["resources"]["litellm_tokens"]["total_limit"])
        self.assertFalse(after["resources"]["litellm_tokens"]["enforced"])
        self.assertEqual(accounting_totals(after)["litellm_tokens"]["reserved"], 0)
        self.assertEqual(accounting_totals(after)["litellm_tokens"]["retired_unmeasured"], 3342336)
        self.assertTrue(self.ledger.remove_token_budget()["already_removed"])
        with self.assertRaises(BudgetRefused):
            self.hold("another-token-hold")

    def test_token_policy_removal_does_not_clear_modal_freeze(self):
        self.hold("litellm:unknown")
        self.ledger.freeze("Provider charges exceed retained allocation")
        self.assertFalse(self.ledger.remove_token_budget()["token_freeze_cleared"])
        self.assertTrue(self.ledger.snapshot()["campaign"]["frozen"])

    def test_token_migration_writes_backup_and_receipt(self):
        from scripts.remove_token_budget import migrate
        self.hold("litellm:unknown")
        self.ledger.freeze("Ambiguous upstream usage for litellm:unknown")
        output = self.path.parent / "migration"
        result = migrate(self.path, output)
        self.assertTrue(result['modal_unchanged'])
        self.assertTrue((output / 'receipt.json').is_file())
        self.assertTrue(CampaignLedger(output / 'before.sqlite').snapshot()['campaign']['frozen'])
        self.assertFalse(self.ledger.snapshot()['campaign']['frozen'])

    def test_token_removal_does_not_hide_modal_overrun(self):
        self.hold('modal', 100, 'modal_micro_usd')
        self.ledger.settle('modal', 101, 'modal-overrun-receipt')
        with self.ledger.transaction() as connection:
            connection.execute("INSERT INTO reservations VALUES (?,?,?,'normal',?,'held',NULL,NULL)",
                               ('litellm:unknown', 'litellm_tokens', 100, self.deadline))
        self.ledger.freeze('Ambiguous upstream usage for litellm:unknown')
        self.assertFalse(self.ledger.remove_token_budget()['token_freeze_cleared'])
        self.assertTrue(self.ledger.snapshot()['campaign']['frozen'])

    def test_historical_tokens_cannot_reintroduce_removed_budget(self):
        self.ledger.remove_token_budget()
        self.ledger.record_prior_usage('history', 'litellm_tokens', 2_000_000_000, 'historical-receipt')
        self.assertFalse(self.ledger.snapshot()['campaign']['frozen'])

    def test_retired_token_hold_does_not_block_modal_admission(self):
        self.hold("litellm:unknown")
        self.ledger.remove_token_budget()
        with patch("fps_bench.campaign_ledger.time.time", return_value=self.deadline + 1):
            self.ledger.reserve("modal", "modal_micro_usd", 100, self.deadline + 60)

    def test_shutdown_work_cannot_consume_normal_allowance(self):
        self.hold("cleanup", 200_000_000, "modal_micro_usd", "shutdown")
        with self.assertRaises(BudgetRefused):
            self.hold("extra-cleanup", 1, "modal_micro_usd", "shutdown")
        self.hold("normal", 1_800_000_000, "modal_micro_usd")

    def test_initialize_rejects_changed_limits(self):
        with self.ledger.transaction() as connection:
            connection.execute("UPDATE limits SET total=total+1")
        with self.assertRaises(LedgerConflict):
            self.ledger.initialize("test-campaign")

    def test_parallel_processes_cannot_oversubscribe(self):
        with ProcessPoolExecutor(max_workers=8) as executor:
            accepted = list(executor.map(concurrent_reserve,
                                        [(str(self.path), index, self.deadline) for index in range(24)]))
        self.assertEqual(sum(accepted), 10)
        self.assertEqual(self.ledger.snapshot()["resources"]["litellm_tokens"]["remaining"], 0)

    def test_restart_preserves_usage_and_campaign_identity(self):
        self.hold()
        reopened = CampaignLedger(self.path)
        reopened.initialize("test-campaign")
        self.assertEqual(reopened.snapshot()["resources"]["litellm_tokens"]["committed"], 100)
        with self.assertRaises(LedgerConflict):
            reopened.initialize("new-campaign")

    def test_expired_hold_never_refunds_and_blocks_other_resources(self):
        self.hold()
        with patch("fps_bench.campaign_ledger.time.time", return_value=self.deadline + 1):
            self.assertEqual(self.ledger.snapshot()["expired_held"], ["job"])
            with self.assertRaises(BudgetRefused):
                self.ledger.reserve("other", "modal_micro_usd", 1, self.deadline + 100)
        self.assertEqual(self.ledger.snapshot()["resources"]["litellm_tokens"]["committed"], 100)
        self.ledger.settle("job", 40, "provider:request-1")
        self.hold("resumed")

    def test_reservation_and_settlement_are_idempotent(self):
        self.hold()
        self.hold()
        with self.assertRaises(LedgerConflict):
            self.hold(amount=101)
        self.ledger.settle("job", 40, "receipt")
        self.ledger.settle("job", 40, "receipt")
        self.assertEqual(self.ledger.snapshot()["event_count"], 3)
        with self.assertRaises(LedgerConflict):
            self.ledger.settle("job", 0, "receipt")

    def test_receipt_cannot_refund_two_jobs(self):
        self.hold()
        self.hold("other")
        self.ledger.settle("job", 0, "receipt")
        with self.assertRaises(LedgerConflict):
            self.ledger.settle("other", 0, "receipt")
        self.assertEqual(self.ledger.snapshot()["resources"]["litellm_tokens"]["committed"], 100)

    def test_actual_overrun_is_recorded_and_freezes_admission(self):
        self.hold()
        self.ledger.settle("job", 120, "receipt")
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["resources"]["litellm_tokens"]["committed"], 120)
        self.assertTrue(snapshot["campaign"]["frozen"])
        with self.assertRaises(BudgetRefused):
            self.hold("other")

    def test_unknown_usage_requires_explicit_receipt(self):
        self.hold()
        for usage in [None, -1, True, 1.2]:
            with self.assertRaises(ValueError):
                self.ledger.settle("job", usage, "receipt")
        with self.assertRaises(ValueError):
            self.ledger.settle("job", 0, "")
        self.assertEqual(self.ledger.snapshot()["resources"]["litellm_tokens"]["committed"], 100)

    def test_failure_rolls_back_partial_accounting(self):
        with self.assertRaises(RuntimeError):
            with self.ledger.transaction() as connection:
                connection.execute("UPDATE campaign SET frozen=1")
                raise RuntimeError("controller died before commit")
        self.assertFalse(self.ledger.snapshot()["campaign"]["frozen"])

    def test_freeze_still_allows_reconciliation(self):
        self.hold()
        self.ledger.freeze("provider unavailable")
        self.ledger.settle("job", 20, "receipt")
        with self.assertRaises(BudgetRefused):
            self.hold("other")

    def test_invalid_amounts_and_resource_are_rejected(self):
        for amount in [0, -1, True, 1.5, "100"]:
            with self.assertRaises(ValueError):
                self.hold(amount=amount)
        with self.assertRaises(ValueError):
            self.hold(resource="other")
        with self.assertRaises(ValueError):
            self.hold(purpose="shutdown")


if __name__ == "__main__":
    unittest.main()
