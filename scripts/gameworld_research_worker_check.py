"""Offline checks for campaign-integrated Pi research materialization."""

import asyncio
import json
from pathlib import Path
import unittest

from fps_bench.gameworld_research_worker import GameWorldResearchWorker, research_environment
import scripts.gameworld_coordinator_check as coordinator_fixtures


class Executor:
    def __init__(self, proposal=None, fail=False):
        self.proposal = proposal
        self.fail = fail
        self.calls = []

    async def run(self, kind, context_path, output_path, timeout):
        context = json.loads(Path(context_path).read_bytes())
        self.calls.append((kind, context, timeout))
        if self.fail:
            raise RuntimeError("synthetic research failure")
        if kind == "proposal":
            Path(output_path).write_text(json.dumps(self.proposal))
            return
        target = context["proposal"]["experiment"]["target_paths"][0]
        result = {
            "patch": (f"diff --git a/{target} b/{target}\n--- a/{target}\n+++ b/{target}\n"
                      "@@ -1 +1 @@\n-old\n+new\n"),
            "rationale": "Synthetic reversible input-delivery change.",
        }
        Path(output_path).write_text(json.dumps(result))


class ResearchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = coordinator_fixtures.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.coordinator = self.fixture.coordinator

    def run_async(self, action):
        return asyncio.run(action)

    def worker(self, executor, catalog=None):
        return GameWorldResearchWorker(
            self.coordinator, self.fixture.root / "coordinator/research", executor, catalog)

    def test_research_environment_drops_provider_credentials(self):
        environment = research_environment({
            "PATH": "/bin", "GAMEWORLD_RESEARCH_TOKEN": "r" * 32,
            "GAMEWORLD_SEARXNG_URL": "http://127.0.0.1:8080",
            "CUA_CLIENT_SECRET": "fleet", "MODAL_TOKEN_SECRET": "modal",
            "QWEN_API_KEY": "qwen", "GITHUB_TOKEN": "github",
        })
        self.assertEqual(environment["GAMEWORLD_RESEARCH_TOKEN"], "r" * 32)
        self.assertEqual(environment["GAMEWORLD_SEARXNG_URL"], "http://127.0.0.1:8080")
        for name in ("CUA_CLIENT_SECRET", "MODAL_TOKEN_SECRET", "QWEN_API_KEY", "GITHUB_TOKEN"):
            self.assertNotIn(name, environment)

    def test_worker_registers_validated_driver_proposal(self):
        proposal = self.fixture.fixture.driver_proposal("worker-driver")
        executor = Executor(proposal)
        event = self.run_async(self.worker(executor).propose())
        self.assertEqual(event["outcome"], "registered")
        self.assertEqual(event["proposal"], proposal["id"])
        self.assertEqual(self.coordinator.supervisor.next()["id"], proposal["id"])
        self.assertEqual(executor.calls[0][1]["recommended_track"], "driver")
        with self.coordinator.controller.ledger.transaction() as connection:
            attempt = dict(connection.execute("SELECT * FROM gameworld_research_attempts").fetchone())
        self.assertEqual(attempt["state"], "complete")
        self.assertIsNotNone(attempt["output_sha256"])

    def test_worker_materializes_allowlisted_driver_patch(self):
        proposal = self.fixture.fixture.driver_proposal("worker-patch")
        self.coordinator.register(proposal)
        self.coordinator.start_next("worker-action")
        executor = Executor()
        events = self.run_async(self.worker(executor).materialize_required())
        self.assertEqual(events[0]["outcome"], "attached")
        workflow = self.coordinator.workflow(proposal["id"])
        self.assertEqual(workflow["state"], "building")
        self.assertIn("patch_sha256", workflow["details"])
        self.assertEqual(executor.calls[0][0], "driver-patch")

    def test_worker_attaches_only_catalogued_sft_source(self):
        proposal = self.fixture.fixture.model_proposal("worker-sft")
        proposal["experiment"]["objective"] = "sft"
        proposal["experiment"]["rollouts_per_task"] = 1
        proposal["experiment"]["sft_source_id"] = "approved-sft"
        self.coordinator.register(proposal)
        self.coordinator.start_next("sft-worker-action")
        dataset = self.fixture.root / "approved-sft-dataset"
        dataset.mkdir()
        receipt = self.fixture.root / "approved-sft-source.json"
        receipt.write_text("{}")
        catalog = self.fixture.root / "sft-catalog.json"
        catalog.write_text(json.dumps({"schema_version": 1, "sources": [{
            "id": "approved-sft", "tasks": proposal["experiment"]["training_tasks"],
            "dataset_root": str(dataset), "dataset_sha256": "a" * 64,
            "source_receipt": str(receipt),
        }]}))
        calls = []
        self.coordinator.attach_sft_dataset = lambda *args: calls.append(args)
        worker = self.worker(Executor(), catalog)
        events = self.run_async(worker.materialize_required())
        self.assertEqual(events, [{"kind": "sft-dataset", "outcome": "attached",
                                   "workflow": proposal["id"], "source": "approved-sft"}])
        self.assertEqual(calls[0][0], "sft-worker-action")
        self.assertEqual(calls[0][1], dataset)

    def test_three_research_failures_stop_campaign(self):
        worker = self.worker(Executor(fail=True))
        for _ in range(3):
            event = self.run_async(worker.propose())
            self.assertEqual(event["outcome"], "failed")
        snapshot = self.coordinator.controller.snapshot()
        self.assertTrue(snapshot["controller"]["stopped"])
        self.assertTrue(snapshot["budget"]["campaign"]["frozen"])
        self.assertEqual(worker.consecutive_failures(), 3)


if __name__ == "__main__":
    unittest.main()
