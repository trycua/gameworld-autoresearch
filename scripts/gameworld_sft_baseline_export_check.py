"""Offline train-only self-imitation export and privileged-state exclusion checks."""

import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_suite_episode import resolve_action, semantic_controls
from scripts.gameworld_sft_baseline_export import episode_sample, export


class BaselineExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.game = {'game_rules': 'Avoid obstacles.', 'game_roles': [{
            'name': 'player', 'prompt': {'role_section': 'Use the screenshot.'},
            'semantic_controls': [{'id': 'wait', 'description': 'Wait briefly.',
                                   'binding': {'action': 'wait', 'duration': 0.4}}]}]}
        self.task = {'task_prompt': 'Survive.'}
        image = io.BytesIO()
        Image.new('RGB', (8, 8)).save(image, format='PNG')
        self.image = image.getvalue()
        response = '{"tool_name":"wait","arguments":{}}'
        self.row = {'step': 0, 'observation': '000.png', 'observation_sha256': digest(self.image),
                    'response': response, 'action': resolve_action(response, semantic_controls(self.game)),
                    'invalid_action': None, 'execution': {'status': 'executed'},
                    'before': {'hidden': 'PRIVATE_SENTINEL'}, 'evaluation': {'hidden': 'PRIVATE_SENTINEL'}}

    def archive(self, identity):
        game, task = identity.split('--')
        manifest = {'driver_sha256': 'd' * 64, 'protocol': 'one-step-current-driver-compatibility-v1',
                    'config': {'catalog_manifest_sha256': 'c' * 64, 'game': game, 'task': task}}
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name, data in {'manifest.json': canonical(manifest),
                               'trajectory.jsonl': canonical(self.row), '000.png': self.image}.items():
                member = tarfile.TarInfo(identity + '/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        raw = buffer.getvalue()
        return raw, {'archive_sha256': digest(raw), 'summary': {
            'execution_status': 'executed', 'invalid_actions': 0, 'progress': 0.1}}

    def test_sample_contains_only_prompt_image_and_original_action(self):
        raw, receipt = self.archive('01_game--01_01')
        sample, name, image = episode_sample(
            '01_game--01_01', raw, receipt, self.game, self.task, 'd' * 64, 'c' * 64)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(sample))
        self.assertEqual(sample['completion'][0]['content'], self.row['response'])
        self.assertEqual(sample['messages'][1]['content'][1], {'type': 'image', 'image': name})
        self.assertEqual(image, self.image)
        with self.assertRaisesRegex(ValueError, 'archive differs'):
            episode_sample('01_game--01_01', raw + b'changed', receipt,
                           self.game, self.task, 'd' * 64, 'c' * 64)

    def test_export_never_selects_development_observations(self):
        baseline, gameworld, output = self.root / 'baseline', self.root / 'upstream', self.root / 'export'
        game_bytes, task_bytes = yaml.safe_dump(self.game).encode(), yaml.safe_dump(self.task).encode()
        for relative, data in {'catalog/games/01_game.yaml': game_bytes,
                               'catalog/tasks/01_game/01_01.yaml': task_bytes}.items():
            destination = gameworld / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        for identity in ('01_game--01_01', '01_game--01_03'):
            raw, receipt = self.archive(identity)
            destination = baseline / 'episodes' / identity
            destination.mkdir(parents=True)
            (destination / 'receipt.json').write_bytes(canonical(receipt))
            (destination / 'artifacts.tar.gz').write_bytes(raw)
        context = {'policy_sha256': 'a' * 64, 'catalog_manifest_sha256': 'c' * 64,
                   'splits': {'train': ['01_game--01_01']}, 'manifest': {'games': [{
                       'game': '01_game', 'game_spec_sha256': digest(game_bytes),
                       'tasks': [{'task': '01_01', 'task_spec_sha256': digest(task_bytes)}]}]}}
        contract = {'spec': {'policy_sha256': 'a' * 64, 'catalog_manifest_sha256': 'c' * 64,
                             'baseline_sha256': 'b' * 64, 'baseline_driver_sha256': 'd' * 64}}
        with patch('scripts.gameworld_sft_baseline_export.verify', return_value=contract), patch(
                'scripts.gameworld_sft_baseline_export.load_policy', return_value=({}, context)), patch(
                'scripts.gameworld_sft_baseline_export.load_baseline', return_value={'baseline_sha256': 'b' * 64}):
            result = export(baseline, gameworld, self.root / 'contract.json', 'f' * 64, output)
        self.assertEqual(result['samples'], 1)
        source = json.loads((output / 'source-receipt.json').read_bytes())
        self.assertEqual(source['tasks'], ['01_game--01_01'])
        self.assertFalse(source['evaluation_policy_contains_privileged_state'])
        self.assertNotIn('PRIVATE_SENTINEL', (output / 'dataset/samples.jsonl').read_text())
        self.assertNotIn('01_03', (output / 'dataset/samples.jsonl').read_text())


if __name__ == '__main__':
    unittest.main()
