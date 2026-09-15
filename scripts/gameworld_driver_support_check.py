"""Offline integrity and routing checks for build-only support repairs."""

import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from scripts.gameworld_driver_support import (
    DriverSupportBackend, FILES, HELPER, OLD_HELPER, TEST_SOURCE, UPSTREAM, bundle, install, sha256,
)


class SupportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'image'
        self.inputs = Path(temporary.name) / 'inputs'
        self.inputs.mkdir()
        source = Path(__file__).resolve().parents[1]
        self.original = (source / HELPER).read_bytes().replace(b'socket_path', b'socket')
        self.assertEqual(sha256(self.original), OLD_HELPER)
        for name, data in {
            'cua-driver/UPSTREAM_REF': (UPSTREAM + '\n').encode(),
            TEST_SOURCE: (source / TEST_SOURCE).read_bytes(), HELPER: self.original,
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, data in bundle(source).items():
            (self.inputs / name).write_bytes(data)

    def test_exact_repair_and_idempotent_receipt(self):
        result = install(self.root, self.inputs)
        self.assertEqual(result, install(self.root, self.inputs))
        for name, expected in FILES.items():
            self.assertEqual(sha256((self.root / name).read_bytes()), expected)
        self.assertEqual(result['scope'], 'driver-build-test-support-only')

    def test_rejects_changed_helper_before_any_mutation(self):
        (self.root / HELPER).write_bytes(b'unknown helper')
        with self.assertRaises(ValueError):
            install(self.root, self.inputs)
        self.assertFalse((self.root / 'cua-driver/compat-fixtures').exists())

    def test_rejects_changed_payload_before_any_mutation(self):
        (self.inputs / 'driver-support-1').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            install(self.root, self.inputs)
        self.assertEqual((self.root / HELPER).read_bytes(), self.original)
        self.assertFalse((self.root / 'cua-driver/compat-fixtures').exists())

    def test_rejects_different_upstream_or_test_source(self):
        for name in ('cua-driver/UPSTREAM_REF', TEST_SOURCE):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                install(self.root, self.inputs)
            path.write_bytes(original)

    def test_rejects_symlink_fixture_directory(self):
        (self.root / 'cua-driver/compat-fixtures').symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaises(ValueError):
            install(self.root, self.inputs)
        self.assertEqual((self.root / HELPER).read_bytes(), self.original)

    def test_rejects_changed_receipt_before_any_mutation(self):
        (self.inputs / 'driver-support-receipt.json').write_text(json.dumps({'scope': 'changed'}))
        with self.assertRaises(ValueError):
            install(self.root, self.inputs)
        self.assertFalse((self.root / 'cua-driver/compat-fixtures').exists())

    def test_evaluation_staging_does_not_receive_support_overlay(self):
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock()))
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.stage', new_callable=AsyncMock) as stage:
            files = {'config.json': b'{}'}
            asyncio.run(DriverSupportBackend().stage(sandbox, '/tmp/episode', files))
        stage.assert_awaited_once_with(sandbox, '/tmp/episode', files)
        sandbox.shell.run.assert_not_awaited()

    def test_evaluation_collection_has_no_extra_remote_operation(self):
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock()))
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.collect', new_callable=AsyncMock) as collect:
            asyncio.run(DriverSupportBackend().collect(sandbox, '/tmp/episode', Path('/output'), 1024))
        collect.assert_awaited_once_with(sandbox, '/tmp/episode', Path('/output'), 1024)
        sandbox.shell.run.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
