"""Offline checks for authorized wall-clock and same-policy capacity changes."""

import asyncio
import copy
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.gameworld_serving import GameWorldServingLifecycle
from scripts.gameworld_capacity_operations import CapacityCoordinator, extend_deadline, pause_expiring_serving, replace_expired_serving, ReplacementController
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
        for authorization, seconds in [('', 43200), ('authorized', 64801), ('authorized', 21600)]:
            with self.assertRaises(ValueError):
                extend_deadline(self.controller, authorization, seconds)

    def test_followup_extension_retains_previous_audit_and_budget(self):
        first = extend_deadline(self.controller, 'authorized operational continuation')
        before = self.controller.snapshot()
        second = extend_deadline(self.controller, 'authorized operational continuation', 64800)
        self.assertEqual(second['previous_deadline'], first['deadline'])
        self.assertEqual(second['original_duration'], first['original_duration'])
        self.assertEqual(self.controller.snapshot()['budget']['resources'], before['budget']['resources'])
        with self.controller.ledger.transaction() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM gameworld_operational_extensions').fetchone()[0], 2)


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


class EpisodeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = gameworld_coordinator_check.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.test_grpo_routes_rollout_dataset_training_serving_and_pairing()
        self.coordinator = self.fixture.coordinator
        self.controller = self.coordinator.controller
        self.workflow = self.coordinator.workflow('model-action')
        self.job = self.workflow['details']['serving_job']
        self.runner = SimpleNamespace(controller=self.controller, coordinator=self.coordinator,
                                      cleanup_serving_job=AsyncMock(), modal_config={})
        extend_deadline(self.controller, 'authorized replacement')
        with self.controller.ledger.transaction() as connection:
            connection.execute('UPDATE jobs SET deadline=? WHERE id=?', (int(time.time()) + 600, self.job))

    def test_pauses_at_boundary_then_waits_for_unexpired_bill(self):
        async def cleanup(job):
            self.controller.provider_cleanup_confirmed(job, 'boundary-provider-cleanup')
        self.runner.cleanup_serving_job.side_effect = cleanup
        result = asyncio.run(pause_expiring_serving(self.runner))
        self.assertEqual(result['job_id'], self.job)
        from scripts.gameworld_campaign_operator import CampaignOperator
        waits = CampaignOperator(self.runner).billing_waits()
        self.assertIn(f'job:{self.job}:modal_micro_usd', waits)
        self.assertEqual(len(self.coordinator._items(self.workflow['proposal_id'], 'development')), 136)

    def test_never_interrupts_an_admitted_episode(self):
        self.coordinator.admit_ready(1)
        self.assertIsNone(asyncio.run(pause_expiring_serving(self.runner)))
        self.runner.cleanup_serving_job.assert_not_awaited()

    def test_does_not_pause_with_sufficient_capacity(self):
        with self.controller.ledger.transaction() as connection:
            connection.execute('UPDATE jobs SET deadline=? WHERE id=?', (int(time.time()) + 10800, self.job))
        self.assertIsNone(asyncio.run(pause_expiring_serving(self.runner)))
        self.runner.cleanup_serving_job.assert_not_awaited()


class DriverEpisodeBoundaryTests(EpisodeBoundaryTests):
    def setUp(self):
        self.fixture = gameworld_coordinator_check.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.test_driver_patch_routes_to_paired_full_gameworld_evaluation()
        self.coordinator = self.fixture.coordinator
        self.coordinator.__class__ = CapacityCoordinator
        self.controller = self.coordinator.controller
        self.workflow = self.coordinator.workflow('driver-action')
        self.job = self.workflow['details']['source_serving_job']
        self.runner = SimpleNamespace(controller=self.controller, coordinator=self.coordinator,
                                      cleanup_serving_job=AsyncMock(), modal_config={})
        extend_deadline(self.controller, 'authorized replacement')
        with self.controller.ledger.transaction() as connection:
            connection.execute('UPDATE jobs SET deadline=? WHERE id=?', (int(time.time()) + 600, self.job))

    def test_source_replacement_keeps_driver_manifest_and_queue(self):
        from fps_bench.gameworld_runner import GameWorldProviderRunner
        self.controller.provider_cleanup_confirmed(self.job, 'source-stopped')
        self.controller.settle_job(self.job, {'modal_micro_usd': 1000}, 'source-test-bill')
        original = self.coordinator._candidate(self.workflow['candidate_id'])
        backend = gameworld_serving_check.Backend()
        lifecycle = GameWorldServingLifecycle(self.controller, self.coordinator.state_root / 'serving', backend)
        config = {**gameworld_runner_check.MODAL, 'environment': 'gameworld-test',
                  'environment_id': 'en-test', 'serving_app': 'gameworld-test-serving', 'serving_app_id': 'ap-test'}
        runner = GameWorldProviderRunner(self.coordinator, config, {'QWEN_API_KEY': 'x' * 32},
                                        serving_lifecycle=lifecycle)
        with patch('fps_bench.gameworld_serving.authenticated_request',
                   return_value={'data': [{'id': original['model']['served_model']}]}):
            result = asyncio.run(replace_expired_serving(runner))
            self.assertIsNone(asyncio.run(replace_expired_serving(runner)))
        self.assertEqual(result['policy_sha256'], original['policy_sha256'])
        self.assertEqual(self.coordinator._candidate(self.workflow['candidate_id']), original)
        current = self.coordinator.workflow('driver-action')
        self.assertEqual(current['details']['source_serving_job'], result['job_id'])
        phase = current['details']['source_serving_phase']
        item = self.coordinator._items(current['proposal_id'], phase)[0]
        self.assertEqual(item['job_id'], result['job_id'])
        self.assertEqual(item['state'], 'live')
        with self.controller.ledger.transaction() as connection:
            self.assertEqual(connection.execute('SELECT job_id FROM gameworld_work_items WHERE id=?', (item['id'],)).fetchone()[0], self.job)
        self.assertEqual(len(self.coordinator._items(current['proposal_id'], 'development')), 136)


if __name__ == '__main__':
    unittest.main()
