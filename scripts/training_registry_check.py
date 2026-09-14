"""Controller-bound data authentication tests; synthetic rollout bytes, no provider calls."""

import asyncio
import copy
import json
import unittest

from fps_bench.campaign_controller import CampaignController
from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_training import ModalTrainingLifecycle
from fps_bench.training_registry import TrainingRegistry
from scripts.modal_training_check import FakeModal
import scripts.training_data_check as fixtures


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.data = fixtures.TrainingDataTests()
        self.data.setUp()
        self.addCleanup(self.data.doCleanups)
        self.home = self.data.fixture.home
        self.controller = CampaignController(self.home / 'campaign.sqlite',
            self.data.fixture.custody / 'contract.json', self.data.hash)
        self.controller.initialize('registry-fixture')
        template = self.data.contract['episode_template']
        self.candidate = {'id': 'baseline', 'parent': None, 'change_class': 'baseline',
            'hypothesis': 'synthetic registry fixture', 'contract_hash': self.data.hash,
            'image': self.data.contract['spec']['provenance']['image'], 'driver_sha256': 'a' * 64,
            'model': {'base_model': template['model'], 'base_revision': template['revision'],
                'processor_revision': template['revision'], 'adapter_sha256': None,
                'served_model': template['served_model']}}
        self.controller.register_candidate(self.candidate)
        self.registry = TrainingRegistry(self.controller)
        self.assignment = {'split': 'train', 'seed': 42, 'repeat': 0}
        self.controller.admit_job('train-42', 'baseline', 'evaluation', self.assignment,
                                  {'modal_micro_usd': 10000000}, 600)

    def complete(self, receipt=None):
        receipt = receipt or self.data.receipt
        self.controller.begin_dispatch('train-42')
        self.controller.provider_started('train-42', 'fake-authenticated-provider')
        self.controller.record_result('train-42', {**self.assignment, 'candidate': 'baseline',
            'contract_sha256': self.data.hash, 'status': 'complete'}, digest(canonical(receipt)))

    def register(self):
        self.complete()
        self.registry.register_episode('train-42', self.data.root, self.data.receipt)
        exported = self.registry.export(['train-42'], self.data.output)
        self.controller.admit_job('training', 'baseline', 'training',
            {'split': 'train', 'seeds': [42], 'dataset_sha256': exported['dataset_sha256']},
            {'modal_micro_usd': 10000000}, 600)
        return exported

    def test_registered_dataset_authenticates_and_prepares(self):
        exported = self.register()
        self.assertEqual(self.registry.authenticate('training')['dataset_sha256'], exported['dataset_sha256'])
        backend = FakeModal()
        lifecycle = ModalTrainingLifecycle(self.controller, backend)
        asyncio.run(lifecycle.prepare('training', workspace='test', app='test-app',
            environment='gameworld-test', environment_id='en-test', image_id='im-prebuilt'))
        asyncio.run(lifecycle.start('training'))
        self.assertEqual(backend.creates, 1)
        self.assertNotIn('MUST_NOT_LEAK', (self.data.output / 'samples.jsonl').read_text())

    def test_caller_hash_without_registry_cannot_prepare(self):
        self.controller.admit_job('training', 'baseline', 'training',
            {'split': 'train', 'seeds': [42], 'dataset_sha256': 'd' * 64},
            {'modal_micro_usd': 10000000}, 600)
        backend = FakeModal()
        lifecycle = ModalTrainingLifecycle(self.controller, backend)
        with self.assertRaises(LedgerConflict):
            asyncio.run(lifecycle.prepare('training', workspace='test', app='test-app',
                environment='gameworld-test', environment_id='en-test', image_id='im-prebuilt'))
        self.assertEqual(backend.creates, 0)

    def test_unacknowledged_job_cannot_register(self):
        with self.assertRaises(LedgerConflict):
            self.registry.register_episode('train-42', self.data.root, self.data.receipt)

    def test_result_hash_must_anchor_receipt(self):
        self.complete({**self.data.receipt, 'served_model': 'other'})
        with self.assertRaises(LedgerConflict):
            self.registry.register_episode('train-42', self.data.root, self.data.receipt)

    def test_candidate_identity_cannot_be_self_attested(self):
        receipt = {**self.data.receipt, 'driver_sha256': 'b' * 64}
        self.complete(receipt)
        with self.assertRaises(LedgerConflict):
            self.registry.register_episode('train-42', self.data.root, receipt)

    def test_development_cannot_be_relabelled_train(self):
        self.complete()
        receipt = {**self.data.receipt, 'split': 'development'}
        with self.assertRaises(LedgerConflict):
            self.registry.register_episode('train-42', self.data.root, receipt)

    def test_unregistered_export_and_duplicates_refused(self):
        with self.assertRaises(LedgerConflict):
            self.registry.export(['train-42'], self.data.output)
        with self.assertRaises(ValueError):
            self.registry.export(['train-42', 'train-42'], self.data.output)
        self.assertFalse(self.data.output.exists())

    def test_tampered_rollout_cannot_export(self):
        self.complete()
        self.registry.register_episode('train-42', self.data.root, self.data.receipt)
        (self.data.root / 'trajectory.jsonl').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.registry.export(['train-42'], self.data.output)

    def test_tampered_dataset_refused_before_dispatch(self):
        self.register()
        backend = FakeModal()
        lifecycle = ModalTrainingLifecycle(self.controller, backend)
        asyncio.run(lifecycle.prepare('training', workspace='test', app='test-app',
            environment='gameworld-test', environment_id='en-test', image_id='im-prebuilt'))
        target = self.data.output / 'samples.jsonl'
        target.chmod(0o600)
        target.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            asyncio.run(lifecycle.start('training'))
        self.assertEqual(backend.creates, 0)

    def test_registered_custody_cannot_change(self):
        self.register()
        self.registry.register_episode('train-42', self.data.root, self.data.receipt)
        receipt = copy.deepcopy(self.data.receipt)
        receipt['episode_id'] = 'different'
        with self.assertRaises(LedgerConflict):
            self.registry.register_episode('train-42', self.data.root, receipt)

    def test_lost_rollout_provenance_refuses_training(self):
        self.register()
        with self.controller.ledger.transaction() as connection:
            connection.execute('DELETE FROM training_episode_receipts')
        with self.assertRaises(LedgerConflict):
            self.registry.authenticate('training')

    def test_reopen_preserves_registration(self):
        self.register()
        reopened = TrainingRegistry(self.controller)
        self.assertEqual(reopened.authenticate('training')['jobs'], ['train-42'])


if __name__ == '__main__':
    unittest.main()
