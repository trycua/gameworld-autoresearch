"""Offline integrity and routing checks for build-only support repairs."""

import asyncio
import json
import shlex
import subprocess
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

    def test_large_driver_chunks_reassemble_identical_bytes(self):
        driver = b'x' * (17 * 1024 * 1024)
        remote = str(self.inputs)
        files = {'candidate.json': json.dumps({'driver_sha256': sha256(driver)}).encode(),
                 'cua-driver': driver, 'assignment.json': b'{}'}

        async def stage(sandbox, root, staged):
            self.assertNotIn('cua-driver', staged)
            for name, data in staged.items():
                self.assertLessEqual(len(data), 16 * 1024 * 1024)
                (Path(root) / name).write_bytes(data)

        async def run(command, timeout):
            result = subprocess.run(shlex.split(command), capture_output=True)
            return SimpleNamespace(success=result.returncode == 0)

        sandbox = SimpleNamespace(shell=SimpleNamespace(run=run))
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.stage', side_effect=stage):
            backend = DriverSupportBackend()
            asyncio.run(backend.stage(sandbox, remote, files))
        self.assertEqual((self.inputs / 'cua-driver').read_bytes(), driver)
        self.assertEqual(json.loads((self.inputs / 'driver-transfer.json').read_text())['sha256'], sha256(driver))
        self.assertFalse(list(self.inputs.glob('driver-transfer-*')))
        self.assertIn(remote, backend.transfer_roots)

    def test_large_driver_rejects_mismatched_identity_before_upload(self):
        files = {'candidate.json': b'{"driver_sha256":"wrong"}', 'cua-driver': b'x' * (17 * 1024 * 1024)}
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.stage', new_callable=AsyncMock) as stage:
            with self.assertRaisesRegex(ValueError, 'identity'):
                asyncio.run(DriverSupportBackend().stage(None, '/tmp/episode', files))
        stage.assert_not_awaited()

    def test_large_rollout_driver_uses_admitted_identity(self):
        driver = b'x' * (17 * 1024 * 1024)
        files = {'config.json': json.dumps({'driver_sha256': sha256(driver)}).encode(), 'cua-driver': driver}
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(success=True))))
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.stage', new_callable=AsyncMock) as stage:
            asyncio.run(DriverSupportBackend().stage(sandbox, '/tmp/rollout', files))
        self.assertNotIn('cua-driver', stage.call_args.args[2])
        sandbox.shell.run.assert_awaited_once()

    def test_failed_assembly_is_not_marked_transferred(self):
        driver = b'x' * (17 * 1024 * 1024)
        files = {'candidate.json': json.dumps({'driver_sha256': sha256(driver)}).encode(), 'cua-driver': driver}
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(success=False))))
        backend = DriverSupportBackend()
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.stage', new_callable=AsyncMock):
            with self.assertRaisesRegex(RuntimeError, 'integrity'):
                asyncio.run(backend.stage(sandbox, '/tmp/episode', files))
        self.assertFalse(backend.transfer_roots)

    def test_transfer_receipt_stays_outside_evaluator_inventory(self):
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(success=True))))
        backend = DriverSupportBackend()
        backend.transfer_roots.add('/tmp/episode')
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.collect', new_callable=AsyncMock):
            asyncio.run(backend.collect(sandbox, '/tmp/episode', Path('/output'), 1024))
        self.assertIn('/output/transport/driver-transfer.json', sandbox.shell.run.call_args.args[0])

    def test_evaluation_collection_has_no_extra_remote_operation(self):
        sandbox = SimpleNamespace(shell=SimpleNamespace(run=AsyncMock()))
        with patch('fps_bench.gameworld_fleet.FleetSandboxBackend.collect', new_callable=AsyncMock) as collect:
            asyncio.run(DriverSupportBackend().collect(sandbox, '/tmp/episode', Path('/output'), 1024))
        collect.assert_awaited_once_with(sandbox, '/tmp/episode', Path('/output'), 1024)
        sandbox.shell.run.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
