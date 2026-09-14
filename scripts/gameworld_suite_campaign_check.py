"""Offline checks for the bounded all-catalog campaign launcher."""

import json
from pathlib import Path
import tempfile
import unittest

from fps_bench.gameworld_suite_catalog import load
from fps_bench.gameworld_suite_episode import CATALOG_MANIFEST_SHA256, SERVED_MODEL
from scripts.gameworld_suite_campaign import assignments, qwen_environment, validate_summary


ROOT = Path(__file__).resolve().parents[1]


class SuiteCampaignTests(unittest.TestCase):
    def test_assignments_cover_every_catalog_task(self):
        manifest, summary = load(ROOT / "configs/evaluation/gameworld-suite-v1.json")
        jobs = assignments(manifest, summary["manifest_sha256"], 42)
        self.assertEqual(len(jobs), 170)
        self.assertEqual(len({job["id"] for job in jobs}), 170)
        self.assertTrue(all(job["catalog_manifest_sha256"] == CATALOG_MANIFEST_SHA256 for job in jobs))

    def test_summary_validation(self):
        summary = {"status": "complete", "success": False, "steps": 1, "invalid_actions": 0,
                   "execution_status": "unsupported_current_driver", "progress": 0.25,
                   "usage": {"prompt_tokens": 10, "completion_tokens": 2}, "seconds": 1.5,
                   "evaluation": {}}
        self.assertEqual(validate_summary(summary), summary)
        with self.assertRaises(ValueError):
            validate_summary({**summary, "progress": 2})

    def test_qwen_environment_is_endpoint_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qwen.env"
            path.write_text("export QWEN_API_KEY=" + "x" * 32 + "\n"
                            "export QWEN_BASE_URL=https://cuaai--gameworld-qwen-baseline-serve.modal.run/v1\n")
            self.assertEqual(qwen_environment(path)["QWEN_BASE_URL"],
                             "https://cuaai--gameworld-qwen-baseline-serve.modal.run/v1")
            path.write_text("export QWEN_API_KEY=" + "x" * 32 + "\n"
                            "export QWEN_BASE_URL=https://example.com/v1\n")
            with self.assertRaises(ValueError):
                qwen_environment(path)

    def test_served_model_is_fixed(self):
        self.assertEqual(SERVED_MODEL, "qwen3-vl-2b-instruct-89644892e4d8")


if __name__ == "__main__":
    unittest.main()
