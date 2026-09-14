"""Tests for independent replay and baseline completeness/cluster accounting."""

import asyncio
from pathlib import Path
import sys
import unittest

from frozen_baseline_report import baseline_statistics, ANCHOR


class BaselineReportTests(unittest.TestCase):
    def setUp(self):
        self.contract = {'public_splits': {'development': {'seeds': list(range(8)), 'repeats': 2}}}
        self.rows = [{'seed': seed, 'repeat': repeat, 'candidate': 'baseline', 'split': 'development',
                      'contract_sha256': ANCHOR, 'status': 'complete', 'success': seed < 4,
                      'seconds': 5.0, 'steps': 3, 'invalid_actions': 0,
                      'usage': {'prompt_tokens': 10, 'completion_tokens': 2}}
                     for seed in range(8) for repeat in range(2)]

    def test_seed_clusters_not_repetitions(self):
        result = baseline_statistics(self.rows, self.contract)
        self.assertEqual(result['episodes'], 16)
        self.assertEqual(result['independent_seed_clusters'], 8)
        self.assertEqual(result['success_rate'], 0.5)
        self.assertLess(result['success_rate_95pct_hoeffding'][0], 0.03)
        self.assertGreater(result['success_rate_95pct_hoeffding'][1], 0.97)

    def test_missing_has_no_rate(self):
        result = baseline_statistics(self.rows[:-1], self.contract)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIsNone(result['success_rate'])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            baseline_statistics(self.rows + self.rows[:1], self.contract)

    def test_wrong_split_rejected(self):
        self.rows[0]['split'] = 'train'
        with self.assertRaises(ValueError):
            baseline_statistics(self.rows, self.contract)

    def test_infrastructure_failure_not_game_failure(self):
        self.rows[0]['status'] = 'failed'
        with self.assertRaises(ValueError):
            baseline_statistics(self.rows, self.contract)


if __name__ == '__main__':
    unittest.main()
