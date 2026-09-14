"""Cleanup-only watchdog tests with durable controller state and fake providers."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from fps_bench.campaign_watchdog import CampaignWatchdog
import scripts.campaign_controller_check as controller_fixtures
import scripts.gameworld_serving_check as serving_fixtures
import scripts.modal_training_check as fixtures


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ModalTrainingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.lifecycle = self.fixture.lifecycle
        self.backend = self.fixture.backend
        self.watchdog = CampaignWatchdog(self.controller, modal=self.lifecycle)

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def expire(self):
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE jobs SET deadline=?", (int(time.time()) - 1,))

    def test_no_dispatch_or_cleanup_before_deadline(self):
        self.assertEqual(self.run_async(self.watchdog.tick()), [])
        self.assertEqual(self.backend.creates, 0)
        self.assertEqual(self.backend.terminations, 0)

    def test_expired_undispatched_job_is_cancelled_without_provider(self):
        self.expire()
        events = self.run_async(self.watchdog.tick())
        self.assertEqual(events[0]["outcome"], "cancelled_undispatched")
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleaned")
        self.assertEqual(self.backend.creates, 0)
        self.assertEqual(self.run_async(self.watchdog.tick()), [])

    def test_stopped_campaign_terminates_but_keeps_budget_hold(self):
        self.run_async(self.lifecycle.start("job-one"))
        self.controller.stop("offline watchdog test")
        events = self.run_async(self.watchdog.tick())
        self.assertEqual(events[0]["outcome"], "terminated_billing_pending")
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot["jobs"][0]["state"], "billing_pending")
        self.assertEqual(snapshot["budget"]["reservations"][0]["state"], "held")
        reopened = CampaignWatchdog(self.controller, modal=self.lifecycle)
        self.run_async(reopened.tick())
        self.assertEqual(self.backend.terminations, 1)
        self.assertEqual(self.backend.worker_calls, 0)

    def test_expired_lost_create_ack_is_found_and_stopped_not_recreated(self):
        self.backend.lost_ack = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.lifecycle.start("job-one"))
        self.expire()
        events = self.run_async(self.watchdog.tick())
        self.assertEqual(events[0]["outcome"], "terminated_billing_pending")
        self.assertEqual(self.backend.creates, 1)
        self.assertEqual(self.backend.terminations, 1)

    def test_absent_ambiguous_create_is_not_refunded(self):
        self.controller.begin_dispatch("job-one")
        self.expire()
        events = self.run_async(self.watchdog.tick())
        self.assertEqual(events[0]["outcome"], "unresolved")
        self.assertEqual(self.backend.creates, 0)
        self.assertEqual(self.controller.snapshot()["budget"]["reservations"][0]["state"], "held")

    def test_failure_retries_without_redispatch_or_refund(self):
        self.run_async(self.lifecycle.start("job-one"))
        self.expire()
        self.backend.fail_termination = True
        self.assertEqual(self.run_async(self.watchdog.tick())[0]["outcome"], "unresolved")
        self.assertEqual(self.controller.snapshot()["budget"]["reservations"][0]["state"], "held")
        self.backend.fail_termination = False
        self.assertEqual(self.run_async(self.watchdog.tick())[0]["outcome"], "terminated_billing_pending")
        self.assertEqual(self.backend.creates, 1)

    def test_hung_cleanup_does_not_block_other_job_cancellation(self):
        async def hung(identity):
            await asyncio.sleep(10)
        self.run_async(self.lifecycle.start("job-one"))
        self.controller.admit_job("research", "baseline", "research", {}, {"litellm_tokens": 100}, 600)
        self.backend.terminate = hung
        self.expire()
        self.watchdog.operation_timeout = 0.05
        events = self.run_async(self.watchdog.tick())
        by_job = {event["job_id"]: event for event in events}
        self.assertEqual(by_job["job-one"]["error_type"], "TimeoutError")
        self.assertEqual(by_job["research"]["outcome"], "cancelled_undispatched")

    def test_mismatched_provider_identity_is_not_deleted(self):
        self.run_async(self.lifecycle.start("job-one"))
        self.backend.sandbox["tags"] = {"campaign": "somebody-else"}
        self.expire()
        self.assertEqual(self.run_async(self.watchdog.tick())[0]["outcome"], "unresolved")
        self.assertEqual(self.backend.terminations, 0)

    def test_unsupported_dispatched_job_keeps_hold_and_reports_failure(self):
        self.controller.admit_job("research", "baseline", "research", {}, {"litellm_tokens": 100}, 600)
        self.controller.begin_dispatch("research")
        self.controller.provider_started("research", "research-test")
        self.expire()
        events = self.run_async(self.watchdog.tick())
        by_job = {event["job_id"]: event for event in events}
        self.assertEqual(by_job["research"]["outcome"], "unresolved")
        snapshot = self.controller.snapshot()
        hold = next(row for row in snapshot["budget"]["reservations"] if row["resource"] == "litellm_tokens")
        self.assertEqual(hold["state"], "held")

    def test_gameworld_evaluation_claim_is_released(self):
        fixture = controller_fixtures.GameWorldControllerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        task = fixture.tasks[0]
        assignment = {"split": "development", "task_id": task["id"], "game": task["game"],
                      "task": task["task"], "seed": task["seed"], "repeat": 0,
                      "comparison": "watchdog-evaluation"}
        fixture.controller.admit_job("evaluation", "baseline", "evaluation", assignment, {}, 600)
        fixture.controller.begin_dispatch("evaluation")
        fixture.controller.provider_started("evaluation", "fleet:test/evaluation")
        fixture.controller.stop("watchdog evaluation test")

        class Fleet:
            async def release(self, job_id):
                fixture.controller.provider_cleanup_confirmed(job_id, "fleet-release:" + job_id)

        watchdog = CampaignWatchdog(fixture.controller, fleet_factory=lambda job: Fleet())
        event = self.run_async(watchdog.tick())[0]
        self.assertEqual(event["outcome"], "claim_released")
        self.assertEqual(fixture.controller.snapshot()["jobs"][0]["state"], "cleaned")

    def test_live_candidate_serving_is_terminated(self):
        fixture = serving_fixtures.ServingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with patch("fps_bench.gameworld_serving.authenticated_request",
                   return_value={"data": [{"id": "model-candidate"}]}):
            self.run_async(fixture.lifecycle.start("serving-one", "x" * 32))
        fixture.training.controller.stop("watchdog serving test")
        watchdog = CampaignWatchdog(
            fixture.training.controller, modal=fixture.training.lifecycle, serving=fixture.lifecycle)
        events = {event["job_id"]: event for event in self.run_async(watchdog.tick())}
        self.assertEqual(events["serving-one"]["outcome"], "serving_terminated_billing_pending")
        serving = next(job for job in fixture.training.controller.snapshot()["jobs"]
                       if job["id"] == "serving-one")
        self.assertEqual(serving["state"], "billing_pending")

    def test_independent_process_recovers_expired_local_job(self):
        self.expire()
        environment = {"PATH": os.environ["PATH"], "PYTHONPATH": str(Path.cwd())}
        command = [sys.executable, "-m", "fps_bench.campaign_watchdog", "--once",
                   "--database", str(self.controller.ledger.path),
                   "--contract", str(self.controller.contract_path),
                   "--contract-sha256", self.controller.contract_hash]
        result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["outcomes"][0]["outcome"], "cancelled_undispatched")
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleaned")
        again = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=15)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["outcomes"], [])


if __name__ == "__main__":
    unittest.main()
