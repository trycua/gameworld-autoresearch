"""Offline train-to-serve lifecycle checks for immutable GameWorld adapters."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_grpo import policy_digest
from fps_bench.gameworld_serving import GameWorldServingLifecycle, ModalServingBackend, compute_reservation
import scripts.gameworld_coordinator_check as coordinator_fixtures
from scripts.gameworld_modal_check import GameWorldModalTests


class Backend:
    def __init__(self):
        self.sandbox = None
        self.starts = 0
        self.stages = 0
        self.stage_targets = []

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

    async def stage(self, sandbox_id, adapter, manifest, target):
        self.stages += 1
        self.stage_targets.append(target)
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
        with self.training.controller.ledger.transaction() as connection:
            baseline = json.loads(self.training.controller._candidate(connection, "baseline")["manifest"])
        assignment = {"training_job": "training-one", "adapter_sha256": adapter,
                      "served_model": "model-candidate", "hypothesis": "Grouped rewards improve action choice.",
                      "comparison": "model-proposal-one",
                      "parent_policy_sha256": baseline["policy_sha256"],
                      "parent_adapter_sha256": baseline["model"]["adapter_sha256"],
                      "parent_served_model": baseline["model"]["served_model"],
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
                   return_value={"data": [{"id": "qwen-baseline"}, {"id": "model-candidate"}]}):
            first = self.run_async(self.lifecycle.start("serving-one", "x" * 32))
            second = self.run_async(self.lifecycle.start("serving-one", "x" * 32))
        self.assertEqual(first["policy_identity"], second["policy_identity"])
        self.assertEqual(self.backend.starts, 1)
        candidate = next(row for row in self.training.controller.snapshot()["candidates"]
                         if row["id"] == "model-candidate")
        self.assertEqual(candidate["state"], "materialized")
        self.assertEqual(first["policy_identity"]["deployment"]["sandbox_id"], "sb-serving")
        parent_policy = json.loads(Path(first["parent_policy_path"]).read_bytes())
        with self.training.controller.ledger.transaction() as connection:
            baseline = json.loads(self.training.controller._candidate(connection, "baseline")["manifest"])
        self.assertEqual(policy_digest(parent_policy), baseline["policy_sha256"])
        self.assertEqual(parent_policy["deployment"], first["policy_identity"]["deployment"])
        self.run_async(self.lifecycle.terminate("serving-one"))
        job = next(row for row in self.training.controller.snapshot()["jobs"] if row["id"] == "serving-one")
        self.assertEqual(job["state"], "billing_pending")
        self.training.controller.settle_job("serving-one", {"modal_micro_usd": 1000}, "serving-bill")

    def test_serving_quote_is_bounded(self):
        rates = self.run_async(self.backend.prices("test"))
        quote = compute_reservation(rates["rates"], 600, rates["checked_at"])
        self.assertGreater(quote["required_reservation_micro_usd"], 1_000_000)
        full = compute_reservation(rates["rates"], 10800, rates["checked_at"])
        self.assertGreater(full["required_reservation_micro_usd"], quote["required_reservation_micro_usd"])
        self.assertLessEqual(full["required_reservation_micro_usd"], 15_000_000)
        with self.assertRaises(ValueError):
            compute_reservation(rates["rates"], 10801, rates["checked_at"])
        with self.assertRaises(ValueError):
            compute_reservation(rates["rates"], 60, rates["checked_at"])


class BaselineServingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = coordinator_fixtures.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.coordinator.controller
        baseline = self.fixture.coordinator._candidate("baseline")
        identity = json.loads(self.fixture.policy_path.read_bytes())
        assignment = {"mode": "source", "policy_sha256": baseline["policy_sha256"],
                      "adapter_sha256": None,
                      "served_model": baseline["model"]["served_model"],
                      "generation": identity["generation"]}
        self.controller.admit_job("baseline-serving", "baseline", "serving", assignment,
                                  {"modal_micro_usd": 10_000_000}, 600)
        self.backend = Backend()
        self.lifecycle = GameWorldServingLifecycle(
            self.controller, self.fixture.root / "baseline-serving", self.backend)
        self.run_async(self.lifecycle.prepare_source(
            "baseline-serving", self.fixture.policy_path, workspace="test", app="test-app",
            environment="gameworld-test", environment_id="en-test", image_id="im-serving", app_id="ap-test"))

    def run_async(self, action):
        return asyncio.run(action)

    def test_baseline_server_is_budgeted_and_policy_stable(self):
        with patch("fps_bench.gameworld_serving.authenticated_request",
                   return_value={"data": [{"id": "qwen-baseline"}]}):
            result = self.run_async(self.lifecycle.start("baseline-serving", "x" * 32))
        baseline = self.fixture.coordinator._candidate("baseline")
        self.assertIsNone(result["candidate"])
        self.assertEqual(self.backend.stages, 0)
        self.assertEqual(policy_digest(result["policy_identity"]), baseline["policy_sha256"])
        job = next(row for row in self.controller.snapshot()["jobs"] if row["id"] == "baseline-serving")
        self.assertEqual(job["state"], "cleanup_pending")
        self.run_async(self.lifecycle.terminate("baseline-serving"))
        job = next(row for row in self.controller.snapshot()["jobs"] if row["id"] == "baseline-serving")
        self.assertEqual(job["state"], "billing_pending")
        self.controller.settle_job("baseline-serving", {"modal_micro_usd": 1000}, "baseline-serving-bill")

    def test_adapted_source_policy_stages_its_parent_adapter(self):
        self.controller.cancel_undispatched("baseline-serving")
        baseline = self.fixture.coordinator._candidate("baseline")
        adapter = self.fixture.root / "adapted-source"
        adapter.mkdir()
        config, weights = b"{}", b"parent-weights"
        (adapter / "adapter_config.json").write_bytes(config)
        (adapter / "adapter_model.safetensors").write_bytes(weights)
        manifest = {"schema_version": 1, "objective": "grpo",
                    "base_model": self.fixture.identity["base_model"],
                    "base_revision": self.fixture.identity["base_revision"],
                    "files": {"adapter_config.json": digest(config),
                              "adapter_model.safetensors": digest(weights)}}
        adapter_sha256 = digest(canonical(manifest))
        (adapter / "adapter-manifest.json").write_bytes(canonical(manifest))
        identity = {**self.fixture.identity, "adapter_sha256": adapter_sha256,
                    "served_model": "adapted-parent"}
        identity_path = self.fixture.root / "adapted-source-policy.json"
        identity_path.write_bytes(canonical(identity))
        candidate = {**json.loads(json.dumps(baseline)), "id": "adapted-parent", "parent": "baseline",
                     "change_class": "model", "hypothesis": "adapted source fixture",
                     "comparison": "adapted-source-comparison", "policy_sha256": policy_digest(identity)}
        candidate["model"]["adapter_sha256"] = adapter_sha256
        candidate["model"]["served_model"] = candidate["id"]
        self.controller.register_candidate(candidate)
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE candidates SET state='retired' WHERE id='baseline'")
            connection.execute("UPDATE candidates SET state='champion' WHERE id=?", (candidate["id"],))
            connection.execute("UPDATE controller SET champion=?", (candidate["id"],))
        assignment = {"mode": "source", "policy_sha256": candidate["policy_sha256"],
                      "adapter_sha256": adapter_sha256, "served_model": candidate["id"],
                      "generation": identity["generation"]}
        self.controller.admit_job("adapted-source-serving", candidate["id"], "serving", assignment,
                                  {"modal_micro_usd": 10_000_000}, 600)
        backend = Backend()
        lifecycle = GameWorldServingLifecycle(
            self.controller, self.fixture.root / "adapted-source-serving", backend)
        self.run_async(lifecycle.prepare_source(
            "adapted-source-serving", identity_path, adapter, workspace="test", app="test-app",
            environment="gameworld-test", environment_id="en-test", image_id="im-serving", app_id="ap-test"))
        with patch("fps_bench.gameworld_serving.authenticated_request",
                   return_value={"data": [{"id": candidate["id"]}]}):
            result = self.run_async(lifecycle.start("adapted-source-serving", "x" * 32))
        self.assertEqual(backend.stage_targets, ["parent-adapter"])
        self.assertEqual(result["policy_identity"]["adapter_sha256"], adapter_sha256)
        self.assertIsNone(result["parent_policy_path"])

    def test_known_pre_submission_refusal_is_closed_only_after_absence_check(self):
        self.controller.begin_dispatch("baseline-serving")
        self.lifecycle.record_submission_error("baseline-serving", {
            "error_type": "InvalidError",
            "message": "Cannot specify open ports when `block_network` is enabled",
        })
        result = self.run_async(self.lifecycle.reconcile_refused_create("baseline-serving"))
        self.assertEqual(result["status"], "refused")
        job = next(row for row in self.controller.snapshot()["jobs"] if row["id"] == "baseline-serving")
        self.assertEqual(job["state"], "cleaned")
        self.assertIsNone(job["provider_id"])


class ModalServingCreateTests(unittest.TestCase):
    def test_encrypted_port_uses_empty_outbound_allowlist(self):
        checked_at = datetime.now(timezone.utc).isoformat()
        rates = {"gpu_hour_cost_l4": "0.8", "cpu_hour_cost_sandbox": "0.1",
                 "mem_gib_hour_cost_sandbox": "0.01"}
        app = SimpleNamespace(app_id="ap-test")
        sandbox = SimpleNamespace(object_id="sb-test")
        volume = SimpleNamespace(with_mount_options=lambda **kwargs: "cache-volume")
        modal = SimpleNamespace(
            App=SimpleNamespace(lookup=SimpleNamespace(aio=AsyncMock(return_value=app))),
            Image=SimpleNamespace(from_id=lambda image_id: "serving-image"),
            Volume=SimpleNamespace(from_name=lambda *args, **kwargs: volume),
            Sandbox=SimpleNamespace(create=SimpleNamespace(aio=AsyncMock(return_value=sandbox))),
        )
        backend = ModalServingBackend()
        backend.app_scope = AsyncMock(return_value={
            "workspace": "test", "environment": "main", "environment_id": "en-test",
            "app": "gameworld-serving", "app_id": "ap-test", "checked_at": checked_at})
        backend.prices = AsyncMock(return_value={"rates": rates, "checked_at": checked_at})
        backend.inspect = AsyncMock(return_value={"id": "sb-test", "tags": {}, "returncode": None,
                                                   "endpoint": "https://candidate.example/v1"})
        plan = {"workspace": "test", "environment": "main", "environment_id": "en-test",
                "app": "gameworld-serving", "app_id": "ap-test", "isolation_policy": "app-scoped",
                "image_id": "im-serving", "name": "gw-serve-test", "tags": {}, "seconds": 600,
                "quote": compute_reservation(rates, 600, checked_at)}
        with patch.dict(sys.modules, {"modal": modal}):
            asyncio.run(backend.create(plan))
        options = modal.Sandbox.create.aio.await_args.kwargs
        self.assertEqual(options["encrypted_ports"], [8000])
        self.assertEqual(options["outbound_cidr_allowlist"], [])
        self.assertNotIn("block_network", options)


class ModalServerCommandTests(unittest.TestCase):
    def test_dual_lora_server_advertises_parent_and_child(self):
        stream = lambda: SimpleNamespace(read=SimpleNamespace(aio=AsyncMock(return_value=b"")))
        process = SimpleNamespace(stdout=stream(), stderr=stream(),
                                  wait=SimpleNamespace(aio=AsyncMock(return_value=0)))
        sandbox = SimpleNamespace(exec=SimpleNamespace(aio=AsyncMock(return_value=process)))
        modal = SimpleNamespace(Sandbox=SimpleNamespace(
            from_id=SimpleNamespace(aio=AsyncMock(return_value=sandbox))))
        backend = ModalServingBackend()
        backend.inspect = AsyncMock(return_value={"id": "sb-test", "tags": {}, "returncode": None,
                                                   "endpoint": "https://candidate.example/v1"})
        plan = {"base_model": "Qwen/Qwen3-VL-2B-Instruct", "base_revision": "a" * 40,
                "raw_base_served_model": "base-qwen", "parent_adapter_sha256": "b" * 64,
                "parent_served_model": "model-parent", "mode": "adapter",
                "served_model": "model-child", "advertised_models": ["model-parent", "model-child"]}
        models = {"data": [{"id": "model-parent"}, {"id": "model-child"}]}
        with patch.dict(sys.modules, {"modal": modal}), patch(
                "fps_bench.gameworld_serving.authenticated_request", return_value=models):
            asyncio.run(backend.start_server("sb-test", plan, "x" * 32))
        shell = sandbox.exec.aio.await_args.args[2]
        self.assertIn("mkdir -p /output", shell)
        self.assertIn("--max-loras 2", shell)
        self.assertIn("model-parent=/input/parent-adapter", shell)
        self.assertIn("model-child=/input/adapter", shell)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            runnable = shell.replace("/output", str(output)).replace("nohup vllm", "nohup true")
            delayed_mkdir = 'mkdir() { sleep 0.2; command mkdir "$@"; }; '
            completed = subprocess.run(["bash", "-c", delayed_mkdir + runnable],
                                       capture_output=True, text=True, timeout=5)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output / "server.pid").read_text().strip().isdigit())


if __name__ == "__main__":
    unittest.main()
