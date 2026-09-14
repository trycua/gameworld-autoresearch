"""Historical billing import tests; all provider rows here are synthetic."""

import copy
from pathlib import Path
import tempfile
import time
import unittest

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger, LedgerConflict
from fps_bench.modal_billing import import_report, normalize_report, usd_to_micro


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = CampaignLedger(Path(self.temp.name) / "ledger.sqlite")
        self.ledger.initialize("test-billing")
        self.scope = {"workspace": "ac-test", "environment": "main", "object_ids": ["ap-test"],
                      "start": "2026-09-12T00:00:00Z", "end": "2026-09-13T00:00:00Z"}
        self.row = {"object_id": "ap-test", "environment": "main",
                    "interval_start": "2026-09-12T12:00:00", "cost": "0.12345678"}

    def spent(self):
        return self.ledger.snapshot()["resources"]["modal_micro_usd"]["committed"]

    def test_decimal_costs_round_up_not_down(self):
        self.assertEqual(usd_to_micro("0.12345678"), 123457)
        self.assertEqual(usd_to_micro("0.00000001"), 1)
        for value in (0.1, "NaN", "Infinity", "-0.1", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                usd_to_micro(value)

    def test_replay_deduplicates_across_restart(self):
        import_report(self.ledger, [self.row], self.scope)
        events = self.ledger.snapshot()["event_count"]
        self.ledger = CampaignLedger(self.ledger.path)
        self.ledger.initialize("test-billing")
        import_report(self.ledger, [self.row], self.scope)
        self.assertEqual(self.spent(), 123457)
        self.assertEqual(self.ledger.snapshot()["event_count"], events)

    def test_late_upward_and_downward_revisions(self):
        import_report(self.ledger, [self.row], self.scope)
        self.row["cost"] = "0.2"
        import_report(self.ledger, [self.row], self.scope)
        self.assertEqual(self.spent(), 200000)
        self.row["cost"] = "0.1"
        import_report(self.ledger, [self.row], self.scope)
        self.assertEqual(self.spent(), 200000)
        self.assertEqual(self.ledger.snapshot()["prior_usage"][0]["latest_actual"], 100000)

    def test_prior_spend_reduces_admission(self):
        self.row["cost"] = "1799"
        import_report(self.ledger, [self.row], self.scope)
        self.ledger.reserve("last", "modal_micro_usd", 1000000, int(time.time()) + 600)
        with self.assertRaises(BudgetRefused):
            self.ledger.reserve("over", "modal_micro_usd", 1, int(time.time()) + 600)

    def test_already_incurred_overrun_is_recorded_and_freezes(self):
        self.row["cost"] = "2001"
        import_report(self.ledger, [self.row], self.scope)
        self.assertEqual(self.spent(), 2001000000)
        self.assertTrue(self.ledger.snapshot()["campaign"]["frozen"])
        self.row["cost"] = "2002"
        import_report(self.ledger, [self.row], self.scope)
        self.assertEqual(self.spent(), 2002000000)

    def test_unrelated_and_out_of_window_rows_excluded(self):
        other = {**self.row, "object_id": "ap-other"}
        outside = {**self.row, "interval_start": self.scope["end"]}
        self.assertEqual(len(normalize_report([self.row, other, outside], self.scope)), 1)

    def test_duplicate_or_wrong_environment_rejected_before_import(self):
        for rows in ([self.row, self.row], [{**self.row, "environment": "elsewhere"}]):
            with self.assertRaises(ValueError):
                import_report(self.ledger, rows, self.scope)
        self.assertEqual(self.spent(), 0)

    def test_partial_hours_rejected(self):
        self.row["interval_start"] = "2026-09-12T12:01:00"
        with self.assertRaises(ValueError):
            import_report(self.ledger, [self.row], self.scope)

    def test_scope_cannot_expand_after_import(self):
        import_report(self.ledger, [self.row], self.scope)
        scope = copy.deepcopy(self.scope)
        scope["object_ids"].append("ap-other")
        with self.assertRaises(LedgerConflict):
            import_report(self.ledger, [self.row], scope)

    def test_initial_import_refuses_possible_existing_job_overlap(self):
        self.ledger.reserve("paid-job", "modal_micro_usd", 100, int(time.time()) + 600)
        with self.assertRaises(LedgerConflict):
            import_report(self.ledger, [self.row], self.scope)

    def test_legacy_ledger_snapshot_and_upgrade_preserve_usage(self):
        self.ledger.reserve("old-job", "modal_micro_usd", 100, int(time.time()) + 600)
        with self.ledger.transaction() as connection:
            connection.execute("DROP TABLE prior_usage")
        self.assertEqual(self.spent(), 100)
        self.ledger.initialize("test-billing")
        self.assertEqual(self.spent(), 100)


if __name__ == "__main__":
    unittest.main()
