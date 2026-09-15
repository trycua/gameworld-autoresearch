"""Offline checks for operational handoffs and app-scoped conservative billing."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from fps_bench.evaluation_contract import canonical
from scripts.gameworld_campaign_operator import AppScopedReconciler, CampaignOperator
import scripts.gameworld_billing_check as billing_fixtures
import scripts.gameworld_runner_check as runner_fixtures


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = runner_fixtures.RunnerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runner = self.fixture.runner
        self.operator = CampaignOperator(self.runner)

    def add_unexpired_serving_bill(self, next_kind=None, known_scope=True):
        deadline = int(time.time()) + 3600
        self.runner.controller.ledger.reserve('job:previous-serving:modal_micro_usd',
                                              'modal_micro_usd', 1000000, deadline)
        with self.runner.controller.ledger.transaction() as connection:
            connection.execute("INSERT INTO jobs(id,candidate,kind,resource_group,specification,deadline,state) "
                               "VALUES ('previous-serving','baseline','serving','training','{}',?,'billing_pending')",
                               (deadline,))
            if known_scope:
                connection.execute('CREATE TABLE gameworld_serving_launches (job_id TEXT PRIMARY KEY, plan TEXT)')
                connection.execute('INSERT INTO gameworld_serving_launches VALUES (?,?)',
                                   ('previous-serving', canonical({'app_id': 'ap-serving'}).decode()))
            if next_kind:
                connection.execute('UPDATE gameworld_work_items SET kind=?', (next_kind,))

    def test_same_app_gpu_waits_before_unexpired_bill_can_strand_live_capacity(self):
        self.add_unexpired_serving_bill('serving')
        with patch.object(self.runner, 'run_once', new_callable=AsyncMock) as dispatch:
            result = asyncio.run(self.operator.cycle())
        dispatch.assert_not_awaited()
        self.assertEqual(result['status'], 'waiting-billing')
        self.assertEqual(result['reservations'], ['job:previous-serving:modal_micro_usd'])

    def test_other_app_gpu_is_not_blocked_by_unexpired_bill(self):
        self.add_unexpired_serving_bill('training')
        self.assertEqual(self.operator.billing_waits(), [])

    def test_desktop_work_is_not_blocked_by_unexpired_bill(self):
        self.add_unexpired_serving_bill()
        self.assertEqual(self.operator.billing_waits(), [])

    def test_unknown_previous_app_blocks_new_gpu(self):
        self.add_unexpired_serving_bill('serving', known_scope=False)
        self.assertEqual(self.operator.billing_waits(), ['job:previous-serving:modal_micro_usd'])

    def test_expired_hold_waits_without_dispatch_or_candidate_rejection(self):
        ledger = self.runner.controller.ledger
        ledger.reserve('old-training', 'modal_micro_usd', 10, int(time.time()) + 600)
        with ledger.transaction() as connection:
            connection.execute("UPDATE reservations SET expires_at=? WHERE id='old-training'",
                               (int(time.time()) - 1,))
        result = asyncio.run(self.operator.cycle())
        self.assertEqual(result['status'], 'waiting-billing')
        self.assertEqual(self.fixture.fleet.driver_attempts, 0)
        self.assertEqual(self.runner.coordinator.workflow(self.fixture.proposal['id'])['state'], 'building')
        self.assertEqual(self.runner.controller.snapshot()['budget']['resources']['modal_micro_usd']['committed'], 10)
        ledger.settle('old-training', 10, 'test-authenticated-reconciliation')
        result = asyncio.run(self.operator.cycle())
        self.assertEqual(result['status'], 'progress')
        self.assertEqual(self.fixture.fleet.driver_attempts, 1)

    def test_dataset_handoff_uses_existing_coordinator_action(self):
        coordinator = self.runner.coordinator
        with patch.object(coordinator, 'required_actions', return_value=[{
                'action': 'register-training-dataset', 'workflow': 'model-test'}]), \
                patch.object(coordinator, 'workflow', return_value={'action_id': 'model-action'}), \
                patch.object(coordinator, 'prepare_training_dataset', return_value={'dataset_sha256': 'a' * 64}) as prepare, \
                patch.object(self.runner, 'run_once', new_callable=AsyncMock) as dispatch:
            result = asyncio.run(self.operator.cycle())
        prepare.assert_called_once_with('model-action')
        dispatch.assert_not_awaited()
        self.assertEqual(result['status'], 'progress')


class ScopedBillingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = billing_fixtures.BillingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.backend = billing_fixtures.Backend()
        self.reconciler = AppScopedReconciler(
            self.controller, self.fixture.fixture.root / 'scoped-billing', self.backend, retry_seconds=0)

    def add_live_serving(self, app='ap-serving'):
        self.controller.ledger.reserve('job:live-serving:modal_micro_usd', 'modal_micro_usd',
                                       15_000_000, int(time.time()) + 3600)
        with self.controller.ledger.transaction() as connection:
            original = dict(connection.execute('SELECT * FROM jobs WHERE id=?', (self.fixture.job_id,)).fetchone())
            original.update(id='live-serving', kind='serving', state='running', result=None,
                            provider_id='sb-live')
            connection.execute(f"INSERT INTO jobs ({','.join(original)}) VALUES ({','.join('?' for _ in original)})",
                               list(original.values()))
            connection.execute('CREATE TABLE gameworld_serving_launches (job_id TEXT PRIMARY KEY, plan TEXT)')
            connection.execute('INSERT INTO gameworld_serving_launches VALUES (?,?)', (
                'live-serving', canonical({'workspace': 'test', 'environment': 'main', 'app_id': app}).decode()))

    def test_closed_training_app_reconciles_while_other_app_serves(self):
        self.add_live_serving()
        result = asyncio.run(self.reconciler.run_once(self.fixture.now))
        self.assertEqual(result['outcome'], 'complete')
        self.assertEqual(result['retained_micro_usd'], 10_000_000)
        self.assertEqual(self.backend.calls[0]['scope']['object_ids'], ['ap-billing'])
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot['budget']['resources']['modal_micro_usd']['committed'], 25_000_000)
        self.assertEqual(next(job for job in snapshot['jobs'] if job['id'] == 'live-serving')['state'], 'running')

    def test_live_resource_in_same_app_blocks_reconciliation(self):
        self.add_live_serving('ap-billing')
        self.assertIsNone(self.reconciler.plan(self.fixture.now))

    def test_unbound_resource_blocks_reconciliation(self):
        self.controller.ledger.reserve('unbound', 'modal_micro_usd', 1, int(time.time()) + 3600)
        self.assertIsNone(self.reconciler.plan(self.fixture.now))

    def test_open_billing_hour_is_never_reconciled(self):
        with self.controller.ledger.transaction() as connection:
            connection.execute('UPDATE modal_training_launches SET termination_receipt=?', (canonical({
                'sandbox_id': 'sb-billing', 'returncode': 0, 'checked_at': self.fixture.now.isoformat(),
                'billing_reconciled': False}).decode(),))
        self.assertIsNone(self.reconciler.plan(self.fixture.now))

    def test_running_provider_observation_is_rejected(self):
        self.add_live_serving()
        observe = self.backend.observe

        async def unexpectedly_running(plan):
            result = await observe(plan)
            result['closure']['running_sandbox_ids'] = ['sb-unexpected']
            return result

        self.backend.observe = unexpectedly_running
        result = asyncio.run(self.reconciler.run_once(self.fixture.now))
        self.assertEqual(result['outcome'], 'failed')
        reservation = next(row for row in self.controller.snapshot()['budget']['reservations']
                           if row['id'] == f'job:{self.fixture.job_id}:modal_micro_usd')
        self.assertEqual(reservation['state'], 'held')


if __name__ == '__main__':
    unittest.main()
