"""App-scoped lifecycle checks without workspace-manager methods or real spend."""

import asyncio
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.modal_scope import validate_app_scope, check_scope
from fps_bench.modal_training import sandbox_options
import scripts.modal_training_check as fixtures


class AppScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ModalTrainingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.lifecycle = self.fixture.lifecycle
        self.backend = self.fixture.backend
        self.controller.cancel_undispatched("job-one")
        self.controller.admit_job("app-job", "baseline", "training",
                                  {"split": "train", "seeds": [42], "dataset_sha256": "d" * 64},
                                  {"modal_micro_usd": 10_000_000}, 600)
        self.backend.environment = AsyncMock(side_effect=AssertionError("Must not call privileged environment guard"))
        self.plan = asyncio.run(self.lifecycle.prepare(
            "app-job", workspace="test", app="gameworld-training", environment="main", environment_id="en-test",
            image_id="im-test", isolation_policy="app-scoped", app_id="ap-test"))

    def test_app_scope_keeps_resource_and_network_constraints(self):
        options = sandbox_options(self.plan)
        self.assertEqual(options["gpu"], "L40S")
        self.assertEqual(options["cpu"], (4, 4))
        self.assertEqual(options["memory"], (32768, 32768))
        self.assertEqual(options["timeout"], 600)
        self.assertTrue(options["block_network"])
        self.assertFalse(options["include_oidc_identity_token"])
        self.assertEqual((options["secrets"], options["volumes"]), ([], {}))
        asyncio.run(self.lifecycle.start("app-job"))
        self.assertEqual(self.backend.creates, 1)
        self.assertEqual(sum(hold["state"] == "held" for hold in self.controller.snapshot()["budget"]["reservations"]), 1)
        self.backend.environment.assert_not_awaited()

    def test_app_identity_changes_refuse_before_dispatch(self):
        original = asyncio.run(self.backend.app_scope("test", "main", "gameworld-training"))
        for field, value in (("app_id", "ap-replaced"), ("environment_id", "en-replaced"),
                             ("environment", "other"), ("workspace", "other")):
            self.backend.app_scope = AsyncMock(return_value={**original, field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                asyncio.run(self.lifecycle.start("app-job"))
        self.assertEqual(self.backend.creates, 0)

    def test_missing_app_id_stale_scope_and_unknown_mode_refused(self):
        observed = asyncio.run(self.backend.app_scope("test", "main", "gameworld-training"))
        with self.assertRaises(ValueError):
            validate_app_scope(observed, {**self.plan, "app_id": None})
        with self.assertRaises(ValueError):
            validate_app_scope({**observed, "checked_at": (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()}, self.plan)
        with self.assertRaises(ValueError):
            asyncio.run(check_scope(self.backend, {**self.plan, "isolation_policy": "unguarded"}))

    def test_admitted_policy_cannot_be_switched(self):
        with self.assertRaises(LedgerConflict):
            asyncio.run(self.lifecycle.prepare("app-job", workspace="test", app="gameworld-different", environment="main",
                                              environment_id="en-test", image_id="im-test",
                                              isolation_policy="app-scoped", app_id="ap-test"))

    def test_scope_drift_does_not_disable_cleanup_or_refund_hold(self):
        asyncio.run(self.lifecycle.start("app-job"))
        self.backend.app_scope = AsyncMock(side_effect=ValueError("scope unavailable"))
        asyncio.run(self.lifecycle.terminate("app-job"))
        self.assertEqual(self.backend.terminations, 1)
        job = next(job for job in self.controller.snapshot()["jobs"] if job["id"] == "app-job")
        self.assertEqual(job["state"], "cleanup_pending")
        holds = self.controller.snapshot()["budget"]["reservations"]
        self.assertTrue(any(hold["state"] == "held" for hold in holds))


if __name__ == "__main__":
    unittest.main()
