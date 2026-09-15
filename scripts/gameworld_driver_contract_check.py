"""Check contract launcher setup without starting desktop processes."""

import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.gameworld_driver_contract import run


class DriverContractSetupTests(unittest.TestCase):
    def test_socket_module_is_not_shadowed_by_daemon_socket_path(self):
        with patch('scripts.gameworld_driver_contract.subprocess.Popen',
                   side_effect=RuntimeError('reached server launch')) as launch:
            with self.assertRaisesRegex(RuntimeError, 'reached server launch'):
                asyncio.run(run(Path('/unused-contract-output.json'), '/unused-driver'))
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0][1:3], ['-m', 'http.server'])


if __name__ == '__main__':
    unittest.main()
