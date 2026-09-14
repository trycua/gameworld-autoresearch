"""Check anchored, no-overwrite external baseline custody."""

import json
from pathlib import Path
import stat
import tempfile
import unittest

from frozen_baseline_register import register
from fps_bench.evaluation_contract import digest


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        rows = []
        for number in range(16):
            episode = f'{number:024x}'
            artifact = self.source / episode / 'artifacts'
            artifact.mkdir(parents=True)
            (artifact / 'summary.json').write_bytes(b'{}')
            rows.append({'episode_id': episode, 'verification': 'frozen evaluator replay on trusted controller',
                         'artifact_sha256': {'summary.json': digest(b'{}')}})
        self.report = {'contract_sha256': 'f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9',
                       'baseline': {'status': 'complete'}, 'run': str(self.source), 'rows': rows}
        self.path = self.root / 'report.json'
        self.path.write_text(json.dumps(self.report))
        self.anchor = digest(self.path.read_bytes())
        self.destination = self.root / 'custody'

    def test_external_readonly_custody(self):
        receipt = register(self.path, self.anchor, self.destination)
        self.assertEqual(receipt['artifact_count'], 16)
        self.assertEqual(stat.S_IMODE((self.destination / 'report.json').stat().st_mode), 0o400)
        with self.assertRaises(FileExistsError):
            register(self.path, self.anchor, self.destination)

    def test_wrong_anchor_no_directory(self):
        with self.assertRaisesRegex(ValueError, 'anchor'):
            register(self.path, 'wrong', self.destination)
        self.assertFalse(self.destination.exists())

    def test_changed_artifact_has_no_registration(self):
        (self.source / ('0' * 24) / 'artifacts/summary.json').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            register(self.path, self.anchor, self.destination)
        self.assertFalse((self.destination / 'registration.json').exists())

    def test_candidate_workspace_refused(self):
        target = Path(__file__).resolve().parents[1] / 'forbidden-baseline-custody'
        with self.assertRaisesRegex(ValueError, 'outside'):
            register(self.path, self.anchor, target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
