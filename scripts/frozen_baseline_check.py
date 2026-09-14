"""Artifact ingestion rejects traversal, links, duplicates and incomplete results."""

import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from frozen_baseline import archive_files, extract_artifacts, verify_episode, release_claim, ANCHOR, DRIVER
from fps_bench.evaluation_contract import canonical, digest


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_roundtrip(self):
        extract_artifacts(archive_files({'a.json': b'{}', 'b.png': b'image'}), self.root)
        self.assertEqual((self.root / 'b.png').read_bytes(), b'image')

    def test_traversal(self):
        with self.assertRaises(ValueError):
            extract_artifacts(archive_files({'../escape': b'bad'}), self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_link(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            info = tarfile.TarInfo('link')
            info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
            archive.addfile(info)
        with self.assertRaises(ValueError):
            extract_artifacts(data.getvalue(), self.root)

    def test_duplicate(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            for repeat in range(2):
                info = tarfile.TarInfo('duplicate')
                archive.addfile(info)
        with self.assertRaises(ValueError):
            extract_artifacts(data.getvalue(), self.root)

    def episode(self):
        contract = {'episode_template': {'max_steps': 60}, 'source_hashes': {'source.py': 'frozen'},
                    'spec': {'provenance': {'gameworld_revision': 'one', 'games_revision': 'two'}}}
        config = {'max_steps': 60, 'seed': 42}
        manifest = {'status': 'complete', 'contract_sha256': ANCHOR, 'config': config,
                    'config_sha256': digest(canonical(config)), 'driver_sha256': DRIVER,
                    'source': {'frozen_hashes': contract['source_hashes']}, **contract['spec']['provenance']}
        row = {'step': 0, 'observation': '000.png', 'observation_sha256': digest(b'png'), 'response': 'action', 'after': {'state': 'end'}}
        files = {'manifest.json': canonical(manifest), 'summary.json': canonical({'status': 'complete', 'success': True, 'steps': 1}),
                 'trajectory.jsonl': canonical(row), '000.png': b'png',
                 '000-response.json': canonical({'choices': [{'message': {'content': 'action'}}]}),
                 'final-state.json': canonical(row['after'])}
        for name, data in files.items():
            (self.root / name).write_bytes(data)
        return contract

    def test_episode_consistency(self):
        report = verify_episode(self.root, {'seed': 42}, self.episode())
        self.assertEqual(report['summary']['steps'], 1)
        self.assertIn('independent evaluator replay pending', report['verification'])

    def test_changed_screenshot(self):
        contract = self.episode()
        (self.root / '000.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Screenshot'):
            verify_episode(self.root, {'seed': 42}, contract)

    def test_wrong_seed(self):
        contract = self.episode()
        with self.assertRaisesRegex(ValueError, 'provenance'):
            verify_episode(self.root, {'seed': 43}, contract)


class ClaimReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_asynchronous_deletion_is_polled(self):
        handle, backend = AsyncMock(), AsyncMock()
        backend.find_claim.side_effect = [{'phase': 'Bound'}, None]
        with patch('frozen_baseline.asyncio.sleep', new_callable=AsyncMock):
            await release_claim(handle, 'pool', 'claim', backend)
        handle.release.assert_awaited_once()
        self.assertEqual(backend.find_claim.await_count, 2)

    async def test_unresolved_deletion_remains_failure(self):
        handle, backend = AsyncMock(), AsyncMock()
        backend.find_claim.return_value = {'phase': 'Bound'}
        with self.assertRaisesRegex(TimeoutError, 'obligation retained'):
            await release_claim(handle, 'pool', 'claim', backend, timeout_seconds=0)


if __name__ == '__main__':
    unittest.main()
