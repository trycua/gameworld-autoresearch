"""Offline train-to-serve lifecycle checks for immutable GameWorld adapters."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_serving import GameWorldServingLifecycle, compute_reservation
from scripts.gameworld_modal_check import GameWorldModalTests


class Backend:
    def __init__(self):
        self.sandbox = None
        self.starts = 0

    async def app_scope(self, workspace, environment, app):
        return {"workspace": workspace, "environment": environment, "environment_id": "en-test",
                "app": app, "app_id": "ap-test", "checked_at": datetime.now(timezone.utc).isoformat()}

    async def environment(self, workspace, name):
        return {"workspace": workspace, "name": name, "environment_id": "en-test", "restricted": True,
                "default_member_role": "no-access", "max_concurrent_gpus": 1, "max_concurrent_tasks": 2,
                "budget_dollars": "25", "effective_limit_dollars": "25", "usage_dollars": "0",
                "spend_limit_reached": False, "checked_at": datetime.now(timezone.utc).isoformat()}

    async def prices(self, workspace):
        return {"rates": {"gpu_hour_cost_l4": "0.8", "cpu_hour_cost_sandbox": "0.1",
                          "mem_gib_hour_cost_sandbox": "0.01"},
                "checked_at": datetime.now(timezone.utc).isoformat()}

    async def lookup(self, app, environment, name):
        return None if self.sandbox is None else self.sandbox.copy()

    async def inspect(self, sandbox_id):
        return self.sandbox.copy()

    async def create(self, plan):
        self.sandbox = {"id": "sb-serving", "tags": plan["tags"], "returncode": None,
                        "endpoint": "https://candidate.example/v1"}
        return self.sandbox.copy()

    async def stage(self, sandbox_id, adapter, manifest):
        return {"adapter-manifest.json": digest((Path(adapter) / "adapter-manifest.json").read_bytes()),
                **{name: digest((Path(adapter) / name).read_bytes()) for name in manifest["files"]}}

    async def start_server(self, sandbox_id, plan, api_key):
        self.starts += 1
        return self.sandbox.copy()

    async def terminate(self, sandbox_id):
        self.sandbox["returncode"] = -15


class ServingTests(unittest.TestCase):
    def setUp(self):
        self.training = GameWorldModalTests()
        self.training.setUp()
        self.addCleanup(self.training.doCleanups)
        self.training.run_async(self.training.artifacts.stage("training-one"))
        self.training.run_async(self.training.lifecycle.run_worker("training-one"))
        self.training.complete_worker()
        self.output = self.training.home / "training-export"
        self.training.run_async(self.training.artifacts.export("training-one", self.output))
        self.training.run_async(self.training.lifecycle.terminate("training-one"))
        adapter = json.loads((self.output / "bundle.json").read_bytes())["adapter_manifest_sha256"]
        assignment = {"training_job": "training-one", "adapter_sha256": adapter,
                      "served_model": "model-candidate", "hypothesis": "Grouped rewards improve action choice.",
                      "comparison": "model-proposal-one",
                      "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                                     "response_format": "unconstrained-json-text"}}
        self.training.controller.admit_job("serving-one", "baseline", "serving", assignment,
                                           {"modal_micro_usd": 10_000_000}, 600)
        self.backend = Backend()
        self.lifecycle = GameWorldServingLifecycle(
            self.training.controller, self.training.home / "serving", self.backend)
        self.run_async(self.lifecycle.prepare(
            "serving-one", self.output, workspace="test", app="test-app",
            environment="gameworld-test", environment_id="en-test", image_id="im-serving", app_id="ap-test"))

    def run_async(self, action):
        return asyncio.run(action)

    def test_candidate_endpoint_is_immutable_and_cleanup_retains_billing(self):
        with patch("fps_bench.gameworld_serving.authenticated_request",
                   return_value={"data": [{"id": "model-candidate"}]}):
            first = self.run_async(self.lifecycle.start("serving-one", "x" * 32))
            second = self.run_async(self.lifecycle.start("serving-one", "x" * 32))
        self.assertEqual(first["policy_identity"], second["policy_identity"])
        self.assertEqual(self.backend.starts, 1)
        candidate = next(row for row in self.training.controller.snapshot()["candidates"]
                         if row["id"] == "model-candidate")
        self.assertEqual(candidate["state"], "materialized")
        self.assertEqual(first["policy_identity"]["deployment"]["sandbox_id"], "sb-serving")
        self.run_async(self.lifecycle.terminate("serving-one"))
        job = next(row for row in self.training.controller.snapshot()["jobs"] if row["id"] == "serving-one")
        self.assertEqual(job["state"], "billing_pending")
        self.training.controller.settle_job("serving-one", {"modal_micro_usd": 1000}, "serving-bill")

    def test_serving_quote_is_bounded(self):
        rates = self.run_async(self.backend.prices("test"))
        quote = compute_reservation(rates["rates"], 600, rates["checked_at"])
        self.assertGreater(quote["required_reservation_micro_usd"], 1_000_000)
        with self.assertRaises(ValueError):
            compute_reservation(rates["rates"], 60, rates["checked_at"])


if __name__ == "__main__":
    unittest.main()
