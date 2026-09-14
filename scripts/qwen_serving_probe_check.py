"""CPU-only checks for the bounded serving worker's validation and cleanup."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('serving_worker', Path(__file__).with_name('qwen_serving_probe_worker.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class ServingWorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.input = self.root / 'input'
        self.input.mkdir()
        (self.input / 'adapter').mkdir()
        (self.input / 'adapter/adapter_model.safetensors').write_bytes(b'fixture')
        self.manifest = {'files': {'adapter_model.safetensors': hashlib.sha256(b'fixture').hexdigest()}}
        (self.input / 'adapter/adapter-manifest.json').write_text(json.dumps(self.manifest))
        (self.input / 'request.json').write_text(json.dumps({
            'model': 'base', 'revision': 'pinned', 'served_model': 'base-pinned', 'payload': {'messages': []}}))
        self.process = Mock()
        self.process.poll.return_value = None

    def run_worker(self, responses, version='0.13.0'):
        def local_path(value):
            if value in ('/input', '/output'):
                return self.root / value[1:]
            return Path(value)
        def response(*args, **kwargs):
            result = Mock()
            result.read.return_value = json.dumps(next(responses)).encode()
            context = Mock()
            context.__enter__ = Mock(return_value=result)
            context.__exit__ = Mock(return_value=False)
            return context
        with patch.object(worker, 'Path', side_effect=local_path), \
             patch.object(worker.importlib.metadata, 'version', return_value=version), \
             patch.object(worker.subprocess, 'Popen', return_value=self.process) as spawn, \
             patch.object(worker.urllib.request, 'urlopen', side_effect=response):
            worker.main()
            return spawn.call_args

    def test_base_and_static_adapter_requests(self):
        arguments = self.run_worker(iter([{'data': [{'id': 'base-pinned'}, {'id': 'trained'}]},
                                         {'choices': []}, {'choices': []}]))
        report = json.loads((self.root / 'output/result.json').read_bytes())
        self.assertEqual([item['model'] for item in report['results']], ['base-pinned', 'trained'])
        self.assertIn('--enable-lora', arguments.args[0])
        self.assertIn('127.0.0.1', arguments.args[0])
        self.process.terminate.assert_called_once()

    def test_missing_adapter_rejected_and_server_stopped(self):
        with self.assertRaisesRegex(ValueError, 'not registered'):
            self.run_worker(iter([{'data': [{'id': 'base-pinned'}]}]))
        self.process.terminate.assert_called_once()
        self.assertFalse((self.root / 'output/result.json').exists())

    def test_wrong_runtime_rejected_before_server(self):
        with self.assertRaisesRegex(ValueError, 'version mismatch'):
            self.run_worker(iter([]), version='0.14.0')
        self.process.terminate.assert_not_called()

    def test_corrupt_adapter_rejected_before_server(self):
        (self.input / 'adapter/adapter_model.safetensors').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'payload mismatch'):
            self.run_worker(iter([]))
        self.process.terminate.assert_not_called()

    def test_server_startup_exit_is_failure(self):
        self.process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'during startup'):
            self.run_worker(iter([]))
        self.process.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
