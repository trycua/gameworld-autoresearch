"""Offline integration checks for authenticated GameWorld Modal GRPO execution."""

import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import scripts.campaign_controller_check as fixtures
from fps_bench.campaign_controller import CampaignController
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_grpo import policy_digest, reward_components
from fps_bench.gameworld_modal import GameWorldModalSDKBackend, GameWorldTrainingArtifacts
from fps_bench.gameworld_research import load_policy
from fps_bench.modal_training import ModalTrainingLifecycle
from scripts.modal_training_check import FakeModal


class Registry:
    def __init__(self, authenticated, worker):
        self.authenticated, self.worker = authenticated, worker

    def authenticate(self, job_id):
        return self.authenticated

    def worker_plan(self, job_id, authenticated=None):
        return self.worker


class Files:
    def __init__(self):
        self.data = {}
        self.roots = set()

    async def begin_stage(self, roots=("/dataset",)):
        if self.roots:
            raise ValueError("staging already exists")
        self.roots.update(roots)

    async def write(self, name, data, root="/dataset"):
        self.data[root.rstrip("/") + "/" + name] = data

    async def read(self, path, limit=512 * 1024 * 1024):
        data = self.data[path]
        if len(data) > limit:
            raise ValueError("oversized fixture")
        return data


class GameWorldModalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        source = fixtures.GameWorldControllerTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.policy, context = load_policy()
        self.identity = {"base_model": self.policy["model"]["base_model"],
                         "base_revision": self.policy["model"]["base_revision"], "adapter_sha256": None,
                         "served_model": "qwen-baseline",
                         "deployment": {"app_id": "ap-Test", "function_id": "fu-Test", "image_id": "im-Test",
                                        "endpoint_sha256": "a" * 64},
                         "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                                        "response_format": "unconstrained-json-text"}}
        contract = copy.deepcopy(source.contract)
        contract["episode_template"].update(
            model=self.identity["base_model"], revision=self.identity["base_revision"],
            served_model=self.identity["served_model"])
        train_id = context["splits"]["train"][0]
        train = {**context["assignments"][train_id], "seed": 42}
        contract["public_splits"]["train"]["tasks"] = [train]
        contract_path = self.home / "contract.json"
        contract_path.write_bytes(canonical(contract))
        self.contract_hash = digest(canonical(contract))
        self.controller = CampaignController(self.home / "campaign.sqlite", contract_path, self.contract_hash)
        self.controller.initialize("gameworld-modal")
        baseline = copy.deepcopy(source.baseline)
        baseline["contract_hash"] = self.contract_hash
        baseline["policy_sha256"] = policy_digest(self.identity)
        baseline["model"].update(
            base_model=self.identity["base_model"], base_revision=self.identity["base_revision"],
            processor_revision=self.identity["base_revision"], served_model=self.identity["served_model"])
        self.controller.register_candidate(baseline)
        self.dataset = self.home / "dataset"
        (self.dataset / "images").mkdir(parents=True)
        (self.dataset / "trajectories").mkdir()
        files, members = {}, []
        for index, progress in enumerate((0.0, 0.25)):
            image = f"image-{index}".encode()
            image_name = f"images/{digest(image)}.png"
            (self.dataset / image_name).write_bytes(image)
            response = '{"tool_name":"wait","arguments":{}}'
            row = {"step": 0, "messages": [{"role": "system", "content": "play"},
                   {"role": "user", "content": [{"type": "text", "text": "act"},
                                                  {"type": "image", "image": image_name}]}],
                   "response": response, "observation": image_name, "observation_sha256": digest(image),
                   "action": {"tool_name": "wait", "arguments": {}}, "invalid_action": None}
            trajectory = f"trajectories/trajectory-{index}.jsonl"
            trajectory_data = canonical(row)
            (self.dataset / trajectory).write_bytes(trajectory_data)
            summary = {"steps": 1, "success": False, "progress": progress,
                       "invalid_actions": 0, "driver_errors": 0}
            reward = reward_components(summary, self.policy["model"]["grpo"])
            files.update({image_name: digest(image), trajectory: digest(trajectory_data)})
            members.append({"id": f"trajectory-{index}", "trajectory": trajectory,
                            "trajectory_sha256": digest(trajectory_data), **summary,
                            "reward_components": reward, "reward": reward["total"]})
        manifest = {"schema_version": 1, "purpose": "gameworld-interactive-grpo-v1",
                    "catalog_manifest_sha256": context["catalog_manifest_sha256"], "policy": self.identity,
                    "driver_sha256": baseline["driver_sha256"], "reward": self.policy["model"]["grpo"],
                    "groups": [{"id": "group-one", "game": train["game"], "task": train["task"],
                                "seed": train["seed"], "initial_state_sha256": "b" * 64,
                                "members": members}], "files": files}
        (self.dataset / "rollouts.json").write_bytes(canonical(manifest))
        self.dataset_hash = digest(canonical(manifest))
        assignment = {"split": "train", "tasks": [train["id"]], "dataset_sha256": self.dataset_hash,
                      "objective": "grpo", "policy_sha256": baseline["policy_sha256"],
                      "driver_sha256": baseline["driver_sha256"], "steps": 2}
        self.controller.admit_job("training-one", "baseline", "training", assignment,
                                  {"modal_micro_usd": 10_000_000}, 600)
        authenticated = {"dataset_sha256": self.dataset_hash, "root": str(self.dataset),
                         "jobs": ["rollout-one"], "manifest": manifest, "policy": self.identity}
        worker = {"kind": "gameworld-grpo", "objective": "grpo", "steps": 2,
                  "dataset_sha256": self.dataset_hash, "tasks": [train["id"]],
                  "policy_sha256": baseline["policy_sha256"],
                  "driver_sha256": baseline["driver_sha256"], "parent_adapter_sha256": None}
        self.backend = FakeModal()
        self.lifecycle = ModalTrainingLifecycle(self.controller, self.backend, Registry(authenticated, worker))
        self.run_async(self.lifecycle.prepare("training-one", workspace="test", app="test-app",
                                              environment="gameworld-test", environment_id="en-test",
                                              image_id="im-prebuilt"))
        self.run_async(self.lifecycle.start("training-one"))
        self.files = Files()
        self.artifacts = GameWorldTrainingArtifacts(self.lifecycle, self.files)

    def run_async(self, action):
        return asyncio.run(action)

    def complete_worker(self):
        config, weights = b"{}", b"adapter-weights"
        adapter_manifest = {"schema_version": 1, "objective": "grpo",
                            "base_model": self.identity["base_model"],
                            "base_revision": self.identity["base_revision"],
                            "processor_revision": self.identity["base_revision"],
                            "parent_adapter_sha256": None, "rollout_dataset_sha256": self.dataset_hash,
                            "driver_sha256": self.lifecycle.stored("training-one")[2]["worker"]["driver_sha256"],
                            "files": {"adapter_config.json": digest(config),
                                      "adapter_model.safetensors": digest(weights)},
                            "hyperparameters": {"steps": 2}, "versions": {"torch": "test"}}
        adapter_data = canonical(adapter_manifest)
        result = {"status": "complete", "objective": "grpo", "steps": 2,
                  "rollout_dataset_sha256": self.dataset_hash,
                  "adapter_manifest_sha256": digest(adapter_data), "losses": []}
        result_data = canonical(result)
        completion = {"job_id": "training-one", "campaign": "gameworld-modal",
                      "experiment": "training-one", "objective": "grpo",
                      "contract_sha256": self.contract_hash, "dataset_sha256": self.dataset_hash,
                      "result_sha256": digest(result_data),
                      "adapter_manifest_sha256": digest(adapter_data)}
        self.files.data.update({
            "/output/worker-finished.json": canonical(completion),
            "/output/training/result.json": result_data,
            "/output/training/adapter/adapter-manifest.json": adapter_data,
            "/output/training/adapter/adapter_config.json": config,
            "/output/training/adapter/adapter_model.safetensors": weights,
            "/output/training/loss.jsonl": b"",
            "/output/telemetry.sqlite": b"telemetry",
        })

    def test_authenticated_stage_export_cleanup_and_billing(self):
        plan = self.lifecycle.stored("training-one")[2]
        self.assertEqual(plan["worker"]["kind"], "gameworld-grpo")
        stage = self.run_async(self.artifacts.stage("training-one"))
        self.assertEqual(stage["dataset_sha256"], self.dataset_hash)
        self.run_async(self.lifecycle.run_worker("training-one"))
        self.complete_worker()
        receipt = self.run_async(self.artifacts.export("training-one", self.home / "export"))
        self.assertEqual(receipt["dataset_sha256"], self.dataset_hash)
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleanup_pending")
        self.run_async(self.lifecycle.terminate("training-one"))
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "billing_pending")
        self.controller.settle_job("training-one", {"modal_micro_usd": 1000}, "modal-billing-row")
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleaned")

    def test_worker_cannot_run_before_verified_stage(self):
        with self.assertRaises(Exception):
            self.run_async(self.lifecycle.run_worker("training-one"))

    def test_sdk_backend_runs_the_gameworld_worker_without_secrets(self):
        process = SimpleNamespace(returncode=0, wait=SimpleNamespace(aio=AsyncMock(return_value=0)))
        sandbox = SimpleNamespace(exec=SimpleNamespace(aio=AsyncMock(return_value=process)))
        modal = SimpleNamespace(Sandbox=SimpleNamespace(from_id=SimpleNamespace(aio=AsyncMock(return_value=sandbox))))
        plan = self.lifecycle.stored("training-one")[2]
        with patch.dict(sys.modules, {"modal": modal}):
            result = self.run_async(GameWorldModalSDKBackend().run_worker("sb-test", plan, 300))
        self.assertEqual(result["returncode"], 0)
        arguments = sandbox.exec.aio.await_args.args
        self.assertIn("scripts.gameworld_model_worker", arguments)
        self.assertIn("--evaluation-contract-sha256", arguments)
        self.assertEqual(sandbox.exec.aio.await_args.kwargs["secrets"], [])


if __name__ == "__main__":
    unittest.main()
