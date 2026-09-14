"""Controller-owned provenance bindings for train-only datasets, not candidate attestations."""

import json
from pathlib import Path

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.training_data import episode_records, export_dataset, verify_dataset


class TrainingRegistry:
    def __init__(self, controller):
        self.controller = controller
        with controller.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS training_episode_receipts "
                               "(job_id TEXT PRIMARY KEY REFERENCES jobs(id), root TEXT NOT NULL, receipt TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS training_datasets "
                               "(sha256 TEXT PRIMARY KEY, root TEXT NOT NULL, jobs TEXT NOT NULL, manifest TEXT NOT NULL)")

    def _binding(self, connection, job_id, receipt):
        job = self.controller._job(connection, job_id)
        if (job['kind'] != 'evaluation' or job['state'] not in ('cleanup_pending', 'cleaned')
                or not job['provider_id'] or not job['result']):
            raise LedgerConflict('An acknowledged completed rollout job is required')
        assignment = json.loads(job['specification'])['assignment']
        result = json.loads(job['result'])
        candidate = json.loads(self.controller._candidate(connection, job['candidate'])['manifest'])
        if (assignment['split'] != 'train' or receipt['split'] != 'train'
                or receipt['seed'] != assignment['seed'] or receipt['episode_id'] != job_id
                or receipt['contract_sha256'] != self.controller.contract_hash
                or receipt['driver_sha256'] != candidate['driver_sha256']
                or receipt['served_model'] != candidate['model']['served_model']
                or result['result'].get('status') != 'complete'
                or result['artifact_sha256'] != digest(canonical(receipt))):
            raise LedgerConflict('Receipt does not match the controller rollout result and candidate')
        return job

    def register_episode(self, job_id, root, receipt):
        root = str(Path(root).absolute())
        with self.controller.ledger.transaction() as connection:
            self._binding(connection, job_id, receipt)
            episode_records(root, receipt, self.controller.contract, self.controller.contract_hash)
            encoded = canonical(receipt).decode()
            existing = connection.execute('SELECT * FROM training_episode_receipts WHERE job_id=?', (job_id,)).fetchone()
            if existing:
                if existing['root'] != root or existing['receipt'] != encoded:
                    raise LedgerConflict('Registered episode custody is immutable')
                return
            connection.execute('INSERT INTO training_episode_receipts VALUES (?,?,?)', (job_id, root, encoded))
            self.controller.ledger._event(connection, 'training_episode_registered',
                                          {'job_id': job_id, 'receipt_sha256': digest(canonical(receipt))})

    def export(self, job_ids, output):
        if not isinstance(job_ids, list) or not job_ids or job_ids != sorted(set(job_ids)):
            raise ValueError('Sorted unique rollout job IDs required')
        with self.controller.ledger.transaction() as connection:
            episodes = []
            for job_id in job_ids:
                row = connection.execute('SELECT * FROM training_episode_receipts WHERE job_id=?', (job_id,)).fetchone()
                if row is None:
                    raise LedgerConflict('Rollout receipt is not registered')
                receipt = json.loads(row['receipt'])
                self._binding(connection, job_id, receipt)
                episodes.append((row['root'], receipt))
            exported = export_dataset(self.controller.contract_path, self.controller.contract_hash, episodes, output)
            manifest, _ = verify_dataset(output, exported['dataset_sha256'], self.controller.contract_hash)
            root = str(Path(output).absolute())
            connection.execute('INSERT INTO training_datasets VALUES (?,?,?,?)',
                               (exported['dataset_sha256'], root, canonical(job_ids).decode(), canonical(manifest).decode()))
            self.controller.ledger._event(connection, 'training_dataset_registered',
                                          {**exported, 'jobs': job_ids})
            return exported

    def authenticate(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = self.controller._job(connection, job_id)
            if job['kind'] != 'training':
                raise LedgerConflict('Training job required')
            assignment = json.loads(job['specification'])['assignment']
            row = connection.execute('SELECT * FROM training_datasets WHERE sha256=?',
                                     (assignment['dataset_sha256'],)).fetchone()
            if row is None:
                raise LedgerConflict('Training dataset is not controller-registered')
            manifest, _ = verify_dataset(row['root'], row['sha256'], self.controller.contract_hash)
            if canonical(manifest).decode() != row['manifest']:
                raise LedgerConflict('Registered dataset manifest changed')
            if assignment['split'] != 'train' or sorted(assignment['seeds']) != sorted(item['seed'] for item in manifest['episodes']):
                raise LedgerConflict('Training assignment differs from registered dataset')
            episodes = []
            for rollout_id in json.loads(row['jobs']):
                episode = connection.execute('SELECT * FROM training_episode_receipts WHERE job_id=?', (rollout_id,)).fetchone()
                if episode is None:
                    raise LedgerConflict('Registered dataset lost its rollout provenance')
                receipt = json.loads(episode['receipt'])
                rollout = self._binding(connection, rollout_id, receipt)
                if rollout['candidate'] != job['candidate']:
                    raise LedgerConflict('Training data must come from the assigned source candidate')
                _, _, metadata = episode_records(episode['root'], receipt, self.controller.contract, self.controller.contract_hash)
                episodes.append(metadata)
            if episodes != manifest['episodes']:
                raise LedgerConflict('Dataset episode inventory differs from registered rollouts')
            return {'dataset_sha256': row['sha256'], 'root': row['root'], 'jobs': json.loads(row['jobs'])}
