"""Offline checks for authorized wall-clock and same-policy capacity changes."""

import asyncio
import copy
import json
import unittest
from unittest.mock import patch

from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.gameworld_serving import GameWorldServingLifecycle
from scripts.gameworld_capacity_operations import CapacityCoordinator, extend_deadline, ReplacementController
from scripts import gameworld_runner_check, gameworld_serving_check, gameworld_coordinator_check


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = gameworld_runner_check.RunnerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.runner.controller

    def test_extension_is_audited_idempotent_and_preserves_budget_and_jobs(self):
        before = self.controller.snapshot()
        receipt = extend_deadline(self.controller, 'User authorized extension and replacement')
        self.assertEqual(receipt, extend_deadline(self.controller, 'User authorized extension and replacement'))
        after = self.controller.snapshot()
        self.assertEqual(after['controller']['deadline'], before['controller']['created'] + 43200)
        self.assertEqual(after['controller']['duration'], before['controller']['duration'])
        self.assertEqual(before['budget']['resources'], after['budget']['resources'])
        self.assertEqual(before['jobs'], after['jobs'])
        self.assertEqual(before['candidates'], after['candidates'])
        with self.controller.ledger.transaction() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM gameworld_operational_extensions').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT deadline FROM gameworld_research').fetchone()[0], receipt['deadline'])
        self.controller.initialize(before['budget']['campaign']['id'])

    def test_stopped_campaign_cannot_be_revived(self):
        self.controller.stop('test')
        with self.assertRaises(BudgetRefused):
            extend_deadline(self.controller, 'authorized')

    def test_authorization_and_bound_required(self):
        for authorization, seconds in [('', 43200), ('authorized', 43201), ('authorized', 21600)]:
            with self.assertRaises(ValueError):
                extend_deadline(self.controller, authorization, seconds)


class ReplacementIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = gameworld_serving_check.ServingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.training.controller
        self.auth = patch('fps_bench.gameworld_serving.authenticated_request',
                          return_value={'data': [{'id': 'qwen-baseline'}, {'id': 'model-candidate'}]})
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.original = asyncio.run(self.fixture.lifecycle.start('serving-one', 'x' * 32))
        asyncio.run(self.fixture.lifecycle.terminate('serving-one'))
        self.controller.settle_job('serving-one', {'modal_micro_usd': 1000}, 'test-bill')

    def test_replacement_keeps_manifest_and_policy_but_changes_endpoint(self):
        with self.controller.ledger.transaction() as connection:
            spec = json.loads(self.controller._job(connection, 'serving-one')['specification'])
            original_manifest = self.controller._candidate(connection, 'model-candidate')['manifest']
        self.controller.admit_job('serving-two', spec['candidate'], 'serving', spec['assignment'],
                                  spec['reservations'], spec['timeout_seconds'])
        backend = gameworld_serving_check.Backend()
        original_create = backend.create

        async def create(plan):
            await original_create(plan)
            backend.sandbox.update(id='sb-replacement', endpoint='https://replacement.example/v1')
            return backend.sandbox.copy()

        backend.create = create
        facade = ReplacementController(self.controller, 'serving-two')
        lifecycle = GameWorldServingLifecycle(facade, self.fixture.training.home / 'replacement', backend)
        asyncio.run(lifecycle.prepare('serving-two', self.fixture.output, workspace='test', app='test-app',
                                     environment='gameworld-test', environment_id='en-test',
                                     image_id='im-serving', app_id='ap-test'))
        result = asyncio.run(lifecycle.start('serving-two', 'x' * 32))
        asyncio.run(lifecycle.start('serving-two', 'x' * 32))
        self.assertEqual(backend.starts, 1)
        self.assertEqual(self.original['candidate']['policy_sha256'], result['candidate']['policy_sha256'])
        self.assertNotEqual(self.original['candidate']['deployment'], result['candidate']['deployment'])
        with self.controller.ledger.transaction() as connection:
            self.assertEqual(self.controller._candidate(connection, 'model-candidate')['manifest'], original_manifest)
        for key in ('driver_sha256', 'policy_sha256', 'training_job', 'hypothesis'):
            changed = copy.deepcopy(result['candidate'])
            changed[key] = 'altered'
            with self.assertRaises(LedgerConflict):
                facade.register_candidate(changed)
        changed = copy.deepcopy(result['candidate'])
        changed['deployment']['sandbox_id'] = 'sb-forged'
        with self.assertRaises(LedgerConflict):
            facade.register_candidate(changed)


class CapacityViewTests(unittest.TestCase):
    def test_cleanup_tracks_replacement_without_rewriting_original_work_item(self):
        fixture = gameworld_coordinator_check.CoordinatorTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.test_grpo_routes_rollout_dataset_training_serving_and_pairing()
        coordinator = fixture.coordinator
        coordinator.__class__ = CapacityCoordinator
        workflow = coordinator.workflow('model-action')
        old = coordinator._items(workflow['proposal_id'], 'serving')[0]
        with coordinator.controller.ledger.transaction() as connection:
            job = dict(coordinator.controller._job(connection, old['job_id']))
            job['id'] = 'replacement-test'
            connection.execute(f"INSERT INTO jobs ({','.join(job)}) VALUES ({','.join('?' for _ in job)})", list(job.values()))
        coordinator._set_workflow(workflow['proposal_id'], details={**workflow['details'], 'serving_job': job['id']})
        self.assertEqual(coordinator._items(workflow['proposal_id'], 'serving')[0]['state'], 'live')
        with coordinator.controller.ledger.transaction() as connection:
            connection.execute("UPDATE jobs SET state='cleaned' WHERE id=?", (job['id'],))
            self.assertEqual(connection.execute('SELECT job_id FROM gameworld_work_items WHERE id=?', (old['id'],)).fetchone()[0], old['job_id'])
        self.assertEqual(coordinator._items(workflow['proposal_id'], 'serving')[0]['state'], 'complete')
        self.assertEqual(len(coordinator._items(workflow['proposal_id'], 'development')), 136)


if __name__ == '__main__':
    unittest.main()
