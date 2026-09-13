"""Offline checks for the GameWorld visual pilot contract."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.gameworld_protocol import model_messages, parse_action


class ProtocolTests(unittest.TestCase):
    def test_arrows(self):
        for key in ("up", "down", "left", "right"):
            self.assertEqual(parse_action(json.dumps({"action": "key", "key": key}))["key"], key)

    def test_reject_extra_fields_and_unsupported_actions(self):
        for action in ({"action": "key", "key": "w"}, {"action": "wait"},
                       {"action": "key", "key": "up", "state": {}}, [], None,
                       {"action": "key", "key": {}}):
            with self.assertRaises(ValueError):
                parse_action(json.dumps(action))

    def test_only_four_previous_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            image.write_bytes(b"image-test")
            payload = model_messages(image, [f"response-{index}" for index in range(6)])
        text = json.dumps(payload)
        self.assertNotIn("response-0", text)
        self.assertNotIn("response-1", text)
        for index in range(2, 6):
            self.assertIn(f"response-{index}", text)
        self.assertIn("data:image/png;base64,", text)
        self.assertNotIn("evaluator", text)


class DriverResponseTests(unittest.TestCase):
    def test_status_is_text_not_json(self):
        from fps_bench.gameworld_baseline import driver_command

        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b"Cua Driver daemon is running\n", b"")
        with patch("asyncio.create_subprocess_exec", return_value=process):
            result = asyncio.run(driver_command("driver", "/tmp/socket", "status"))
        self.assertEqual(result, {"status": "ready"})

    def test_tool_errors_fail_the_run(self):
        from fps_bench.gameworld_baseline import driver_command

        process = AsyncMock()
        process.returncode = 0
        process.communicate.return_value = (b'{"isError":true}', b"")
        with patch("asyncio.create_subprocess_exec", return_value=process):
            with self.assertRaises(RuntimeError):
                asyncio.run(driver_command("driver", "/tmp/socket", "call", "press_key", "{}"))


unittest.main()
