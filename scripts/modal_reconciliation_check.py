"""Conservative group closure, deduplication, revision, and admission checks."""

from datetime import datetime, timezone
import tempfile
from pathlib import Path
import time
import unittest

from fps_bench.campaign_ledger import CampaignLedger, BudgetRefused, LedgerConflict, accounting_totals
from fps_bench.modal_reconciliation import reconcile
from fps_bench.modal_billing import normalize_report


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = CampaignLedger(Path(self.directory.name) / 'ledger.sqlite')
        self.ledger.initialize('test')
        self.ledger.reserve('one', 'modal_micro_usd', 10_000_000, int(time.time()) + 30)
        self.ledger.reserve('two', 'modal_micro_usd', 10_000_000, int(time.time()) + 30)
        with self.ledger.transaction() as connection:
            connection.execute("UPDATE events SET timestamp=1704070800 WHERE kind='reserved'")
            connection.execute("UPDATE reservations SET expires_at=1704078000")
        self.scope = {'workspace': 'test', 'environment': 'main', 'object_ids': ['ap-test'],
                      'start': '2024-01-01T00:00:00Z', 'end': '2024-01-01T03:00:00Z'}
        self.specification = {'scope': self.scope, 'reservation_ids': ['one', 'two'],
                              'policy': 'retain-full-allocation-no-refund-v1'}
        self.rows = [{'object_id': 'ap-test', 'environment': 'main', 'interval_start': '2024-01-01T01:00:00Z', 'cost': '1.0'}]
        self.closure = {'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': self.scope,
                        'running_sandbox_ids': [], 'resources': [
                            {'reservation_id': name, 'provider_id': 'sb-' + name, 'app_id': 'ap-test',
                             'kind': 'sandbox', 'returncode': 137, 'observed_tags': {'job': name},
                             'expected_tags': {'job': name}, 'finished_at': '2024-01-01T02:00:00+00:00'}
                            for name in ('one', 'two')]}

    def reconcile(self):
        return reconcile(self.ledger, self.specification, self.rows, self.closure)

    def test_close_without_refund_allows_new_admission(self):
        with self.assertRaises(BudgetRefused):
            self.ledger.reserve('new', 'modal_micro_usd', 1, int(time.time()) + 30)
        result = self.reconcile()
        self.assertEqual(result['observed_micro_usd'], 1_000_000)
        self.assertEqual(result['snapshot']['resources']['modal_micro_usd']['committed'], 20_000_000)
        self.assertFalse(result['snapshot']['expired_held'])
        self.ledger.reserve('new', 'modal_micro_usd', 1, int(time.time()) + 30)

    def test_telemetry_keeps_observed_and_retained_total(self):
        result = self.reconcile()
        totals = accounting_totals(result['snapshot'])['modal_micro_usd']
        self.assertEqual(totals, {'observed': 1_000_000, 'reserved': 19_000_000})
        self.rows[0]['cost'] = '21.0'
        result = self.reconcile()
        self.assertEqual(accounting_totals(result['snapshot'])['modal_micro_usd'],
                         {'observed': 21_000_000, 'reserved': 0})

    def test_replay_does_not_double_count(self):
        first = self.reconcile()
        second = self.reconcile()
        self.assertEqual(first, second)

    def test_lower_revised_or_missing_rows_do_not_refund(self):
        self.reconcile()
        self.rows[0]['cost'] = '0.1'
        self.assertEqual(self.reconcile()['observed_micro_usd'], 1_000_000)
        self.rows = []
        self.assertEqual(self.reconcile()['observed_micro_usd'], 1_000_000)

    def test_overage_is_charged_once_and_freezes(self):
        self.reconcile()
        self.rows[0]['cost'] = '21.0'
        result = self.reconcile()
        self.assertEqual(result['snapshot']['resources']['modal_micro_usd']['committed'], 21_000_000)
        self.assertTrue(result['snapshot']['campaign']['frozen'])
        self.assertEqual(self.reconcile(), result)

    def test_retained_member_cannot_be_refunded_as_job(self):
        self.reconcile()
        with self.assertRaises(LedgerConflict):
            self.ledger.settle('one', 1, 'unsupported-refund')

    def test_running_sandbox_refuses_without_mutation(self):
        self.closure['running_sandbox_ids'] = ['sb-one']
        before = self.ledger.snapshot()
        with self.assertRaises(ValueError):
            self.reconcile()
        self.assertEqual(before, self.ledger.snapshot())

    def test_tags_and_termination_required(self):
        self.closure['resources'][0]['returncode'] = None
        with self.assertRaises(ValueError):
            self.reconcile()
        self.closure['resources'][0]['returncode'] = 137
        self.closure['resources'][0]['observed_tags'] = {}
        with self.assertRaises(ValueError):
            self.reconcile()

    def test_stale_closure_rejected(self):
        self.closure['checked_at'] = '2024-01-01T03:00:00+00:00'
        with self.assertRaises(ValueError):
            self.reconcile()

    def test_historical_provider_row_cannot_overlap(self):
        row = normalize_report(self.rows, self.scope)[0]
        self.ledger.record_prior_usage(row['id'], 'modal_micro_usd', row['micro_usd'], 'prior-receipt')
        with self.assertRaises(LedgerConflict):
            self.reconcile()
        self.assertTrue(all(row['state'] == 'held' for row in self.ledger.snapshot()['reservations']))

    def test_reconciled_row_cannot_be_imported_as_history(self):
        self.reconcile()
        row = normalize_report(self.rows, self.scope)[0]
        with self.assertRaises(LedgerConflict):
            self.ledger.record_prior_usage(row['id'], 'modal_micro_usd', 1, 'duplicate')

    def test_other_group_cannot_take_member_or_period(self):
        self.reconcile()
        self.specification['reservation_ids'] = ['one']
        self.closure['resources'] = self.closure['resources'][:1]
        with self.assertRaises(LedgerConflict):
            self.reconcile()

    def test_provider_bindings_cannot_change_on_revision(self):
        self.reconcile()
        self.closure['resources'][0]['provider_id'] = 'sb-replacement'
        with self.assertRaisesRegex(LedgerConflict, 'identities cannot change'):
            self.reconcile()

    def test_per_hour_highwater_does_not_hide_other_hour_increase(self):
        self.reconcile()
        self.rows[0]['cost'] = '0.1'
        self.rows.append({**self.rows[0], 'interval_start': '2024-01-01T02:00:00Z', 'cost': '1.5'})
        self.assertEqual(self.reconcile()['observed_micro_usd'], 2_500_000)

    def test_closure_must_cover_every_reservation(self):
        self.closure['resources'] = self.closure['resources'][:1]
        with self.assertRaises(ValueError):
            self.reconcile()


if __name__ == '__main__':
    unittest.main()
