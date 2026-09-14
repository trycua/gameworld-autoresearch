"""Offline Modal training lifecycle tests with a fake provider and real ledger."""

import asyncio
from datetime import datetime, timezone
import unittest
from unittest.mock import patch, patch

import scripts.campaign_controller_check as fixtures
from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.modal_training import ModalTrainingLifecycle, compute_reservation, sandbox_options


class FakeModal:
    def __init__(self):
        self.sandbox = None
        self.creates = 0
        self.terminations = 0
        self.worker_calls = 0
        self.fail_worker = False
        self.lost_ack = False
        self.fail_termination = False
        self.environment_budget = "25"
        self.environment_id = "en-test"

    async def app_scope(self, workspace, environment, app):
        return {"workspace": workspace, "environment": environment, "environment_id": self.environment_id,
                "app": app, "app_id": "ap-test", "checked_at": datetime.now(timezone.utc).isoformat()}

    async def environment(self, workspace, name):
        return {"workspace": workspace, "name": name, "environment_id": self.environment_id,
                "restricted": True, "default_member_role": "no-access", "max_concurrent_gpus": 1,
                "max_concurrent_tasks": 2, "budget_dollars": self.environment_budget,
                "effective_limit_dollars": self.environment_budget, "usage_dollars": "0",
                "spend_limit_reached": False, "checked_at": datetime.now(timezone.utc).isoformat()}

    async def prices(self, workspace):
        return {"rates": {"gpu_hour_cost_l40s": "1.95", "cpu_hour_cost_sandbox": "0.1419",
                          "mem_gib_hour_cost_sandbox": "0.024"},
                "checked_at": datetime.now(timezone.utc).isoformat()}

    async def lookup(self, app, environment, name):
        return self.sandbox.copy() if self.sandbox else None

    async def inspect(self, identity):
        if not self.sandbox or self.sandbox["id"] != identity:
            raise LookupError("sandbox not found")
        return self.sandbox.copy()

    async def create(self, plan):
        self.creates += 1
        self.sandbox = {"id": "sb-test", "tags": plan["tags"], "returncode": None}
        if self.lost_ack:
            raise TimeoutError("lost acknowledgement")
        return self.sandbox.copy()

    async def run_worker(self, identity, plan, timeout):
        self.worker_calls += 1
        if self.fail_worker:
            raise TimeoutError("lost exec acknowledgement")
        return {"returncode": 0, "artifacts_exported": False}

    async def terminate(self, identity):
        self.terminations += 1
        if self.fail_termination:
            raise TimeoutError("still terminating")
        self.sandbox["returncode"] = -15


class ModalTrainingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ControllerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.fixture.admit(amount=10_000_000)
        self.backend = FakeModal()
        self.lifecycle = ModalTrainingLifecycle(self.controller, self.backend)
        registry_check = patch.object(self.lifecycle.training_registry, "authenticate", return_value={})
        registry_check.start()
        self.addCleanup(registry_check.stop)
        self.plan = self.run_async(self.lifecycle.prepare("job-one", workspace="test", app="test-app",
                                                          environment="gameworld-test", environment_id="en-test", image_id="im-prebuilt"))

    def run_async(self, call):
        return asyncio.run(call)

    def test_environment_drift_prevents_provider_create(self):
        self.backend.environment_budget = "100"
        with self.assertRaises(ValueError):
            self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.backend.creates, 0)
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "reserved")

    def test_replaced_environment_prevents_provider_create(self):
        self.backend.environment_id = "en-replaced"
        with self.assertRaises(ValueError):
            self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.backend.creates, 0)

    def test_environment_drift_blocks_worker_but_not_cleanup(self):
        self.run_async(self.lifecycle.start("job-one"))
        self.staged_fixture()
        self.backend.environment_budget = "100"
        with self.assertRaises(ValueError):
            self.run_async(self.lifecycle.run_worker("job-one"))
        self.assertEqual(self.backend.worker_calls, 0)
        self.run_async(self.lifecycle.terminate("job-one"))
        self.assertEqual(self.backend.terminations, 1)

    def test_compute_quote_uses_sandbox_rates_and_hard_limits(self):
        self.assertEqual(self.plan["quote"]["compute_estimate_micro_usd"], 547600)
        self.assertEqual(self.plan["quote"]["required_reservation_micro_usd"], 2095200)
        options = sandbox_options(self.plan)
        self.assertEqual(options["cpu"], (4, 4))
        self.assertEqual(options["memory"], (32768, 32768))
        self.assertEqual(options["timeout"], 600)
        self.assertTrue(options["block_network"])
        self.assertEqual(options["volumes"], {})
        self.assertEqual(options["secrets"], [])

    def test_start_reconnect_and_stop_retain_billing_hold(self):
        self.assertEqual(self.run_async(self.lifecycle.start("job-one")), "sb-test")
        self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.backend.creates, 1)
        receipt = self.run_async(self.lifecycle.terminate("job-one"))
        self.assertFalse(receipt["billing_reconciled"])
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot["jobs"][0]["state"], "cleanup_pending")
        self.assertEqual(snapshot["budget"]["reservations"][0]["state"], "held")
        self.assertEqual(snapshot["budget"]["resources"]["modal_micro_usd"]["committed"], 10000000)
        self.assertEqual(self.run_async(self.lifecycle.terminate("job-one")), receipt)
        self.assertEqual(self.backend.terminations, 1)

    def staged_fixture(self):
        with self.controller.ledger.transaction() as connection:
            connection.execute("INSERT INTO modal_training_transfers VALUES (?, ?, NULL)", ("job-one", "offline-fixture"))

    def test_worker_dispatch_is_once_even_after_lost_ack(self):
        self.staged_fixture()
        self.run_async(self.lifecycle.start("job-one"))
        self.backend.fail_worker = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.run_worker("job-one"))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.run_worker("job-one"))
        self.assertEqual(self.backend.worker_calls, 1)
        self.run_async(self.lifecycle.terminate("job-one"))

    def test_worker_success_is_not_artifact_or_billing_confirmation(self):
        self.staged_fixture()
        self.run_async(self.lifecycle.start("job-one"))
        result = self.run_async(self.lifecycle.run_worker("job-one"))
        self.assertEqual(result, {"returncode": 0, "artifacts_exported": False})
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "running")
        self.assertEqual(self.controller.snapshot()["budget"]["reservations"][0]["state"], "held")

    def test_lost_ack_adopts_same_sandbox(self):
        self.backend.lost_ack = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "dispatching")
        self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.backend.creates, 1)
        self.run_async(self.lifecycle.terminate("job-one"))

    def test_ambiguous_absence_never_recreates_or_refunds(self):
        self.controller.begin_dispatch("job-one")
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.start("job-one"))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.terminate("job-one"))
        self.assertEqual(self.backend.creates, 0)
        self.assertEqual(self.controller.snapshot()["budget"]["reservations"][0]["state"], "held")

    def test_collision_and_replacement_untouched(self):
        self.backend.sandbox = {"id": "sb-foreign", "tags": self.plan["tags"], "returncode": None}
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.start("job-one"))
        self.backend.sandbox = None
        self.run_async(self.lifecycle.start("job-one"))
        self.backend.sandbox["tags"] = {"foreign": "true"}
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.terminate("job-one"))
        self.assertEqual(self.backend.terminations, 0)

    def test_failed_termination_retains_cleanup_obligation(self):
        self.run_async(self.lifecycle.start("job-one"))
        self.backend.fail_termination = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.terminate("job-one"))
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleanup_pending")
        self.backend.fail_termination = False
        self.run_async(self.lifecycle.terminate("job-one"))

    def test_underfunded_job_cannot_prepare(self):
        self.controller.cancel_undispatched("job-one")
        self.fixture.admit("underfunded", amount=100)
        with self.assertRaises(BudgetRefused):
            self.run_async(self.lifecycle.prepare("underfunded", workspace="test", app="test-app",
                                                   environment="gameworld-test", environment_id="en-test", image_id="im-prebuilt"))
        self.assertEqual(self.backend.creates, 0)

    def test_frozen_campaign_cannot_dispatch(self):
        self.controller.ledger.freeze("operator stop")
        with self.assertRaises(BudgetRefused):
            self.run_async(self.lifecycle.start("job-one"))
        self.assertEqual(self.backend.creates, 0)

    def test_stale_quote_and_immutable_image(self):
        with patch("fps_bench.modal_training.time.time", return_value=datetime.now(timezone.utc).timestamp() + 301):
            with self.assertRaises(ValueError):
                self.run_async(self.lifecycle.start("job-one"))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.prepare("job-one", workspace="test", app="test-app",
                                                   environment="gameworld-test", environment_id="en-test", image_id="im-different"))
        self.assertEqual(self.backend.creates, 0)


if __name__ == "__main__":
    unittest.main()
