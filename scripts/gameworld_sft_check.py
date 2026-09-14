"""Offline authenticated GameWorld SFT training and serving vertical slice."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_modal import (
    GameWorldModalSDKBackend,
    GameWorldModalTrainingLifecycle,
    GameWorldTrainingArtifacts,
)
from fps_bench.gameworld_serving import GameWorldServingLifecycle
from fps_bench.gameworld_training import GameWorldTrainingRegistry
import scripts.gameworld_coordinator_check as coordinator_fixtures
import scripts.gameworld_modal_check as modal_fixtures
import scripts.gameworld_serving_check as serving_fixtures
from scripts.modal_training_check import FakeModal


class GameWorldSFTTests(unittest.TestCase):
    def setUp(self):
        self.fixture = coordinator_fixtures.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.coordinator = self.fixture.coordinator
        self.controller = self.coordinator.controller
        self.proposal = self.fixture.fixture.model_proposal("model-sft")
        self.proposal["experiment"]["objective"] = "sft"
        self.proposal["experiment"]["rollouts_per_task"] = 1
        self.proposal["experiment"]["sft_source_id"] = "vertical-sft-source"
        self.coordinator.register(self.proposal)
        self.coordinator.start_next("sft-action")
        self.coordinator.allocate_model_budget("sft-action", 5_000_000, 15_000_000)
        self.registry = GameWorldTrainingRegistry(
            self.controller, self.fixture.fixture.policy, self.fixture.fixture.catalog)
        self.coordinator.registry = self.registry
        self.dataset, self.dataset_sha256, self.source = self.build_dataset()
        self.source_path = self.fixture.root / "source-receipt.json"
        self.source_path.write_bytes(canonical(self.source))
        self.coordinator.attach_sft_dataset(
            "sft-action", self.dataset, self.dataset_sha256, self.source_path)
        self.training_job = self.coordinator.admit_ready(1)[0]["job_id"]

    def run_async(self, action):
        return asyncio.run(action)

    def build_dataset(self):
        task = self.proposal["experiment"]["training_tasks"][0]
        root = self.fixture.root / "sft-vertical-dataset"
        (root / "images").mkdir(parents=True)
        temporary = root / "image.png"
        Image.new("RGB", (16, 16), (2, 4, 8)).save(temporary)
        image = temporary.read_bytes()
        image_name = "images/" + digest(image) + ".png"
        temporary.rename(root / image_name)
        sample = {"id": task + ":teacher-1", "messages": [
            {"role": "system", "content": "play"},
            {"role": "user", "content": [{"type": "text", "text": "Choose a legal action."},
                                             {"type": "image", "image": image_name}]},
        ], "completion": [{"role": "assistant", "content": '{"tool_name":"wait","arguments":{}}'}]}
        samples = canonical(sample)
        (root / "samples.jsonl").write_bytes(samples)
        source = {"schema_version": 1, "kind": "teacher-policy", "tasks": [task],
                  "rights": "Synthetic test fixture", "artifact_sha256": "5" * 64,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "evaluation_policy_contains_privileged_state": False}
        manifest = {"schema_version": 1, "purpose": "train-only-action-imitation",
                    "contract_sha256": self.fixture.contract_hash, "samples": 1, "episodes": [],
                    "files": {"samples.jsonl": digest(samples), image_name: digest(image)},
                    "gameworld": {"schema_version": 1, "tasks": [task],
                                  "driver_sha256": "c" * 64,
                                  "source_receipt_sha256": digest(canonical(source))}}
        (root / "dataset.json").write_bytes(canonical(manifest))
        return root, digest(canonical(manifest)), source

    def complete_worker(self, files):
        policy = self.fixture.identity
        config, weights = b"{}", b"sft-adapter-weights"
        adapter = {"schema_version": 1, "objective": "sft", "base_model": policy["base_model"],
                   "base_revision": policy["base_revision"],
                   "processor_revision": policy["base_revision"],
                   "dataset_sha256": self.dataset_sha256,
                   "contract_sha256": self.fixture.contract_hash,
                   "files": {"adapter_config.json": digest(config),
                             "adapter_model.safetensors": digest(weights)},
                   "hyperparameters": {"steps": 2}, "versions": {"torch": "test"}}
        adapter_data = canonical(adapter)
        result = {"status": "complete", "objective": "sft", "dataset_sha256": self.dataset_sha256,
                  "contract_sha256": self.fixture.contract_hash, "steps": 2, "losses": [],
                  "adapter_manifest_sha256": digest(adapter_data)}
        result_data = canonical(result)
        completion = {"job_id": self.training_job, "campaign": "test-gameworld",
                      "experiment": self.training_job, "objective": "sft",
                      "contract_sha256": self.fixture.contract_hash,
                      "dataset_sha256": self.dataset_sha256, "result_sha256": digest(result_data),
                      "adapter_manifest_sha256": digest(adapter_data)}
        files.data.update({
            "/output/worker-finished.json": canonical(completion),
            "/output/training/result.json": result_data,
            "/output/training/adapter/adapter-manifest.json": adapter_data,
            "/output/training/adapter/adapter_config.json": config,
            "/output/training/adapter/adapter_model.safetensors": weights,
            "/output/training/loss.jsonl": b"",
            "/output/telemetry.sqlite": b"telemetry",
        })

    def test_authenticated_sft_exports_serves_and_queues_paired_evaluation(self):
        backend = FakeModal()
        lifecycle = GameWorldModalTrainingLifecycle(self.controller, backend, self.registry)
        self.run_async(lifecycle.prepare(
            self.training_job, workspace="test", app="test-app", environment="gameworld-test",
            environment_id="en-test", image_id="im-prebuilt"))
        self.run_async(lifecycle.start(self.training_job))
        files = modal_fixtures.Files()
        artifacts = GameWorldTrainingArtifacts(lifecycle, files)
        stage = self.run_async(artifacts.stage(self.training_job))
        self.assertEqual(stage["objective"], "sft")
        self.run_async(lifecycle.run_worker(self.training_job))
        self.complete_worker(files)
        output = self.fixture.root / "coordinator/modal" / self.training_job
        receipt = self.run_async(artifacts.export(self.training_job, output))
        self.assertEqual(receipt["dataset_sha256"], self.dataset_sha256)
        self.run_async(lifecycle.terminate(self.training_job))
        self.coordinator.advance()
        serving_job = self.coordinator.admit_ready(1)[0]["job_id"]
        serving = GameWorldServingLifecycle(
            self.controller, self.fixture.root / "coordinator/serving", serving_fixtures.Backend())
        plan = self.run_async(serving.prepare(
            serving_job, output, workspace="test", app="test-app", environment="gameworld-test",
            environment_id="en-test", image_id="im-serving", app_id="ap-test"))
        self.assertEqual(plan["objective"], "sft")
        served_model = self.coordinator._items(self.proposal["id"], "serving")[0]["assignment"]["served_model"]
        with patch("fps_bench.gameworld_serving.authenticated_request",
                   return_value={"data": [{"id": plan["parent_served_model"]}, {"id": served_model}]}):
            started = self.run_async(serving.start(serving_job, "x" * 32))
        self.assertEqual(started["candidate"]["model"]["adapter_sha256"], receipt["adapter_manifest_sha256"])
        self.coordinator.advance()
        self.assertEqual(len(self.coordinator._items(self.proposal["id"], "development")), 136)
        self.run_async(serving.terminate(serving_job))

    def test_sft_rejects_privileged_evaluation_policy_provenance(self):
        root = self.fixture.root / "unsafe-sft"
        shutil.copytree(self.dataset, root)
        source = {**self.source, "evaluation_policy_contains_privileged_state": True}
        manifest = json.loads((root / "dataset.json").read_bytes())
        manifest["gameworld"]["source_receipt_sha256"] = digest(canonical(source))
        (root / "dataset.json").write_bytes(canonical(manifest))
        with self.assertRaises(ValueError):
            self.registry.register_sft(
                "baseline", root, digest(canonical(manifest)),
                self.proposal["experiment"]["training_tasks"], source)

    def test_sdk_backend_runs_sft_worker_without_policy_or_secrets(self):
        backend = FakeModal()
        lifecycle = GameWorldModalTrainingLifecycle(self.controller, backend, self.registry)
        plan = self.run_async(lifecycle.prepare(
            self.training_job, workspace="test", app="test-app", environment="gameworld-test",
            environment_id="en-test", image_id="im-prebuilt"))
        process = SimpleNamespace(returncode=0, wait=SimpleNamespace(aio=AsyncMock(return_value=0)))
        sandbox = SimpleNamespace(exec=SimpleNamespace(aio=AsyncMock(return_value=process)))
        modal = SimpleNamespace(Sandbox=SimpleNamespace(from_id=SimpleNamespace(aio=AsyncMock(return_value=sandbox))))
        with patch.dict(sys.modules, {"modal": modal}):
            self.run_async(GameWorldModalSDKBackend().run_worker("sb-test", plan, 300))
        arguments = sandbox.exec.aio.await_args.args
        self.assertIn("--contract-sha256", arguments)
        self.assertNotIn("--policy-identity", arguments)
        self.assertEqual(sandbox.exec.aio.await_args.kwargs["secrets"], [])


if __name__ == "__main__":
    unittest.main()
