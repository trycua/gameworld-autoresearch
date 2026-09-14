"""Offline custody checks for the dedicated LiteLLM research key."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fps_bench.research_gateway import MODELS
from scripts.litellm_research_key import create, verify


class KeyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "litellm-key.json"
        self.alias = "gameworld-autoresearch-test"
        self.response = {"key": "sk-" + "x" * 40, "key_alias": self.alias,
                         "models": list(MODELS), "expires": "2026-09-21T00:00:00Z"}

    def test_create_keeps_secret_only_in_mode_0600_custody(self):
        with patch("scripts.litellm_research_key.api_request", return_value=self.response):
            result = create(self.path, self.alias, "7d", "admin-" + "z" * 40)
        self.assertNotIn("key", result)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        manifest = json.loads(self.path.read_bytes())
        self.assertEqual(manifest["key"], self.response["key"])
        with patch("scripts.litellm_research_key.api_request", return_value=self.response):
            with self.assertRaises(FileExistsError):
                create(self.path, self.alias, "7d", "admin-" + "z" * 40)

    def test_verify_authenticates_alias_models_and_block_state(self):
        with patch("scripts.litellm_research_key.api_request", return_value=self.response):
            create(self.path, self.alias, "7d", "admin-" + "z" * 40)
        responses = [
            {"data": [{"id": model} for model in MODELS]},
            {"total_count": 1, "keys": [{"key_alias": self.alias, "models": list(MODELS),
                                          "blocked": False, "expires": self.response["expires"],
                                          "max_parallel_requests": 4, "key_name": "sk-..." + "x" * 4}]},
        ]
        with patch("scripts.litellm_research_key.api_request", side_effect=responses):
            result = verify(self.path, "admin-" + "z" * 40)
        self.assertTrue(result["verified"])
        for change in [{"blocked": True}, {"expires": "2026-09-22T00:00:00Z"}]:
            changed = [responses[0], {"total_count": 1, "keys": [
                {**responses[1]["keys"][0], **change}] }]
            with self.subTest(change=change):
                with patch("scripts.litellm_research_key.api_request", side_effect=changed):
                    with self.assertRaises(ValueError):
                        verify(self.path, "admin-" + "z" * 40)

    def test_repository_secret_custody_is_refused(self):
        path = Path(__file__).resolve().parents[1] / "litellm-key.json"
        with self.assertRaises(ValueError):
            create(path, self.alias, "7d", "admin-" + "z" * 40)


if __name__ == "__main__":
    unittest.main()
