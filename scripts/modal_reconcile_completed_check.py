"""Offline checks for trusted multi-app Modal reconciliation inputs."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.modal_reconcile_completed import validate_image_import_completion, validate_plan_scopes


class CompletedReconciliationInputTests(unittest.TestCase):
    def test_multiple_app_scopes_must_match_plan_exactly(self):
        scopes = [
            {'workspace': 'test', 'environment': 'main', 'app_id': 'ap-training'},
            {'workspace': 'test', 'environment': 'main', 'app_id': 'ap-serving'},
        ]
        plan = {'scope': {'workspace': 'test', 'environment': 'main',
                          'object_ids': ['ap-serving', 'ap-training']}}
        self.assertEqual(validate_plan_scopes(plan, scopes), ['ap-serving', 'ap-training'])
        with self.assertRaises(ValueError):
            validate_plan_scopes({**plan, 'scope': {**plan['scope'], 'object_ids': ['ap-training']}}, scopes)
        with self.assertRaises(ValueError):
            validate_plan_scopes(plan, [scopes[0], {**scopes[1], 'environment': 'other'}])

    def test_image_completion_time_is_ledger_owned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.sqlite'
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            connection.execute('CREATE TABLE events(timestamp INTEGER,kind TEXT,payload TEXT)')
            timestamp = 1789400000
            connection.execute('INSERT INTO events VALUES (?,?,?)', (
                timestamp, 'image_import_completed', json.dumps({'id': 'image-import:test'})))
            connection.commit()
            finished = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            self.assertEqual(validate_image_import_completion(
                connection, 'image-import:test', finished), timestamp)
            with self.assertRaises(ValueError):
                validate_image_import_completion(
                    connection, 'image-import:test', datetime.fromtimestamp(timestamp + 1, timezone.utc).isoformat())
            connection.close()


if __name__ == '__main__':
    unittest.main()
