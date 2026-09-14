"""Check report anchoring and per-episode versus complete-baseline telemetry."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import frozen_baseline_telemetry as exporter


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.telemetry = Mock()
        self.telemetry.flush.return_value = {'metrics': True, 'logs': True}

    def emit(self, count, complete=False, wrong_hash=False):
        rows = []
        for number in range(count):
            episode = 'episode-' + str(number)
            artifact = self.root / episode / 'artifacts'
            artifact.mkdir(parents=True)
            raw = b'{"finished_at":"2026-09-14T01:00:00+00:00"}'
            (artifact / 'manifest.json').write_bytes(raw)
            rows.append({'episode_id': episode, 'verification': 'frozen evaluator replay on trusted controller',
                         'candidate': 'baseline', 'split': 'development', 'success': False, 'seconds': 2.0,
                         'evaluation': {'metrics': {'progress_current': 0.5}},
                         'artifact_sha256': {'manifest.json': hashlib.sha256(raw).hexdigest()}})
        report = {'contract_sha256': 'f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9',
                  'run': str(self.root), 'rows': rows,
                  'baseline': {'status': 'complete' if complete else 'incomplete', 'episodes': count,
                               'success_rate': 0.0, 'median_seconds': 2.0}}
        path = self.root / 'report.json'
        path.write_text(json.dumps(report))
        anchor = 'wrong' if wrong_hash else hashlib.sha256(path.read_bytes()).hexdigest()
        with patch.object(exporter, 'ResearchTelemetry', return_value=self.telemetry), \
             patch('sys.argv', ['exporter', '--report', str(path), '--report-sha256', anchor,
                                '--outbox', str(self.root / 'outbox.sqlite')]), contextlib.redirect_stdout(io.StringIO()):
            exporter.main()

    def test_partial_does_not_emit_aggregate(self):
        self.emit(2)
        self.telemetry.record.assert_not_called()
        self.telemetry.flush.assert_not_called()

    def test_complete_emits_aggregate(self):
        self.emit(16, complete=True)
        self.assertEqual(self.telemetry.record.call_count, 1)
        record = self.telemetry.record.call_args
        self.assertEqual(record.args[2]['experiment'], 'baseline-qwen-v1')
        self.assertEqual(record.args[3]['gameworld_eval_completed_episodes'], 16)
        self.assertEqual(record.args[3]['gameworld_eval_mean_progress'], 0.5)

    def test_wrong_report_anchor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'anchor'):
            self.emit(1, wrong_hash=True)
        self.telemetry.record.assert_not_called()

    def test_incomplete_cannot_claim_complete(self):
        with self.assertRaisesRegex(ValueError, '16 episodes'):
            self.emit(1, complete=True)
        self.telemetry.flush.assert_not_called()


if __name__ == '__main__':
    unittest.main()
