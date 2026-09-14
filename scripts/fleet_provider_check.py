"""Offline Fleet lifecycle checks: fake SDK, real durable controller transitions."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import scripts.campaign_controller_check as fixtures
from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.fleet_provider import FleetLifecycle, FleetSDKBackend


class FakeBackend:
    def __init__(self, image):
        self.image = image
        self.claim = None
        self.create_calls = 0
        self.delete_calls = 0
        self.raise_after_create = False
        self.fail_delete = False
        self.min_pool = 0
        self.pool_ttl = 21600
        self.pool_created_at = datetime.now(timezone.utc).isoformat()
        self.template_name = "test-pool-template"

    async def inspect_pool(self, name):
        return {"pool": name, "namespace": name, "template_name": self.template_name,
                "runtime": "RuntimeKind.GVISOR", "image": self.image,
                "min_pool_size": self.min_pool, "max_pool_size": 20, "cpu": 4, "memory": "16384Mi",
                "created_at": self.pool_created_at, "ttl_seconds": self.pool_ttl,
                "replicas": int(self.claim is not None), "ready_replicas": int(self.claim is not None),
                "claims": [self.claim["name"]] if self.claim else []}

    async def find_claim(self, pool, name):
        return self.claim.copy() if self.claim else None

    async def create_claim(self, pool, name, ttl):
        self.create_calls += 1
        self.claim = {"pool": pool, "warmpool": "default", "template_name": self.template_name,
                      "namespace": pool, "name": name,
                      "created_at": datetime.now(timezone.utc).isoformat(), "ttl_seconds": ttl,
                      "phase": "Bound", "sandbox_name": "test-sandbox"}
        if self.raise_after_create:
            raise TimeoutError("simulated lost create acknowledgement")

    async def connect(self, reference, timeout):
        return {"connected": reference["claim"], "timeout": timeout}

    async def release(self, reference):
        self.delete_calls += 1
        if self.fail_delete:
            raise TimeoutError("simulated failed deletion")
        self.claim = None


class SDKMappingTests(unittest.TestCase):
    def test_claim_status_maps_bound_sandbox_without_runtime_fields(self):
        claim = SimpleNamespace(
            spec=SimpleNamespace(warmpool="default", sandbox_template_ref=SimpleNamespace(name="test-pool-template"),
                                 ttl_seconds_after_created=600),
            metadata=SimpleNamespace(namespace="test-pool", name="test-claim", creation_timestamp="2026-09-13T00:00:00Z"),
            status=SimpleNamespace(phase="Bound", sandbox=SimpleNamespace(name="test-sandbox")))
        client = SimpleNamespace(get_claim=AsyncMock(return_value=claim), close=AsyncMock())
        pool_type = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(resource=object())))
        modules = {"cua_sandbox": SimpleNamespace(Pool=pool_type),
                   "cua_sandbox.transport": SimpleNamespace(),
                   "cua_sandbox.transport.fleet_cloud": SimpleNamespace(_FleetClient=lambda: client)}
        with patch.dict("sys.modules", modules):
            result = asyncio.run(FleetSDKBackend().find_claim("test-pool", "test-claim"))
        self.assertEqual(result["pool"], "test-pool")
        self.assertEqual(result["warmpool"], "default")
        self.assertEqual(result["template_name"], "test-pool-template")
        self.assertEqual(result["phase"], "Bound")
        self.assertEqual(result["sandbox_name"], "test-sandbox")
        self.assertNotIn("runtime", result)
        client.close.assert_awaited_once()


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ControllerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.backend = FakeBackend(self.controller.contract["spec"]["provenance"]["image"])
        self.output = self.fixture.home / "fleet-output"
        self.output.mkdir()
        self.lifecycle = FleetLifecycle(self.controller, "test-pool", self.output, self.backend)
        self.controller.admit_job("probe", "baseline", "driver_build",
                                  {"pool": "test-pool", "operation": "warm-driver-probe"}, {}, 600)

    def run_async(self, action):
        return asyncio.run(action)

    def test_claim_release_and_zero_are_separate_verified_states(self):
        connected = self.run_async(self.lifecycle.acquire("probe"))
        self.assertTrue(connected["connected"].startswith("gw-"))
        self.assertEqual(self.backend.claim["ttl_seconds"], 600)
        self.assertFalse(self.run_async(self.lifecycle.wait_zero(0))["scaled_to_zero"])
        receipt = self.run_async(self.lifecycle.release("probe"))
        self.assertTrue(receipt["claim_absent"])
        self.assertTrue(self.run_async(self.lifecycle.wait_zero(0))["scaled_to_zero"])
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleaned")

    def test_reconnect_never_creates_second_claim(self):
        self.run_async(self.lifecycle.acquire("probe"))
        self.run_async(self.lifecycle.acquire("probe"))
        self.assertEqual(self.backend.create_calls, 1)

    def test_lost_create_ack_reconciles_existing_claim(self):
        self.backend.raise_after_create = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.acquire("probe"))
        self.assertEqual(self.controller.recovery_actions()[0]["action"], "reconcile_ambiguous_submission")
        self.run_async(self.lifecycle.acquire("probe"))
        self.assertEqual(self.backend.create_calls, 1)
        self.run_async(self.lifecycle.release("probe"))

    def test_missing_ambiguous_submission_is_not_recreated_or_refunded(self):
        self.controller.begin_dispatch("probe")
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.acquire("probe"))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(self.backend.create_calls, 0)
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "dispatching")

    def test_claim_collision_before_dispatch_is_untouched(self):
        _, reference = self.lifecycle.identity("probe")
        self.run_async(self.backend.create_claim("test-pool", reference["claim"], 600))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.acquire("probe"))
        self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(self.backend.delete_calls, 0)
        self.assertIsNotNone(self.backend.claim)

    def test_replaced_claim_is_not_deleted(self):
        self.run_async(self.lifecycle.acquire("probe"))
        self.backend.claim["created_at"] = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + 1, timezone.utc).isoformat()
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(self.backend.delete_calls, 0)

    def test_failed_delete_keeps_cleanup_pending(self):
        self.run_async(self.lifecycle.acquire("probe"))
        self.backend.fail_delete = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(self.controller.recovery_actions()[0]["action"], "export_artifacts_and_cleanup")
        self.backend.fail_delete = False
        self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(self.controller.recovery_actions(), [])

    def test_pool_drift_prevents_claim_creation(self):
        self.backend.min_pool = 1
        with self.assertRaises(ValueError):
            self.run_async(self.lifecycle.acquire("probe"))
        self.assertEqual(self.backend.create_calls, 0)

    def test_non_terraform_template_prevents_claim_creation(self):
        self.backend.template_name = "legacy-template"
        with self.assertRaises(ValueError):
            self.run_async(self.lifecycle.acquire("probe"))
        self.assertEqual(self.backend.create_calls, 0)

    def test_non_expiring_pool_passes_preflight(self):
        self.backend.pool_ttl = None
        observed = self.run_async(self.lifecycle.preflight(1800))
        self.assertIsNone(observed["ttl_seconds"])

    def test_pool_expiring_before_cleanup_fails_preflight(self):
        self.backend.pool_ttl = 60
        with self.assertRaisesRegex(ValueError, "Pool expires"):
            self.run_async(self.lifecycle.preflight(1800))

    def test_repeat_release_is_idempotent(self):
        self.run_async(self.lifecycle.acquire("probe"))
        first = self.run_async(self.lifecycle.release("probe"))
        second = self.run_async(self.lifecycle.release("probe"))
        self.assertEqual(first, second)
        self.assertEqual(self.backend.delete_calls, 1)

    def test_modal_backed_desktop_release_retains_billing_hold(self):
        task_fixture = fixtures.GameWorldControllerTests()
        task_fixture.setUp()
        self.addCleanup(task_fixture.doCleanups)
        controller = task_fixture.controller
        task = task_fixture.tasks[0]
        assignment = {"split": "development", "task_id": task["id"], "game": task["game"],
                      "task": task["task"], "seed": task["seed"], "repeat": 0,
                      "comparison": "provider-cleanup"}
        controller.admit_job("evaluation", "baseline", "evaluation", assignment,
                             {}, 600)
        backend = FakeBackend(controller.contract["spec"]["provenance"]["image"])
        lifecycle = FleetLifecycle(controller, "test-pool", task_fixture.home / "fleet", backend)
        lifecycle.output.mkdir()
        self.run_async(lifecycle.acquire("evaluation"))
        controller.record_result("evaluation", {**assignment, "candidate": "baseline",
                                 "contract_sha256": task_fixture.hash, "status": "complete", "success": False,
                                 "steps": 10, "invalid_actions": 0, "seconds": 5.0}, "e" * 64)
        self.run_async(lifecycle.release("evaluation"))
        job = controller.snapshot()["jobs"][0]
        self.assertEqual(job["state"], "cleaned")
        self.assertEqual(controller.recovery_actions(), [])


if __name__ == "__main__":
    unittest.main()
