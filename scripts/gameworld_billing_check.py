"""Offline checks for automatic GameWorld Modal billing reconciliation."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_billing import GameWorldModalReconciler, hour
import scripts.gameworld_coordinator_check as coordinator_fixtures


class Backend:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def observe(self, plan):
        self.calls.append(plan)
        if self.fail:
            raise RuntimeError("synthetic billing failure")
        resources = [{**resource, "returncode": 0,
                      "observed_tags": resource["expected_tags"]}
                     for resource in plan["resources"]]
        return {
            "rows": [{"object_id": plan["scope"]["object_ids"][0],
                      "environment": plan["scope"]["environment"],
                      "interval_start": plan["scope"]["start"], "cost": "0.001"}],
            "closure": {"scope": plan["scope"], "resources": resources,
                        "running_sandbox_ids": [],
                        "checked_at": datetime.now(timezone.utc).isoformat()},
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = coordinator_fixtures.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.coordinator = self.fixture.coordinator
        self.controller = self.coordinator.controller
        self.now = datetime.now(timezone.utc)
        self.finished = self.now - timedelta(hours=2)
        self.job_id = "billing-training"
        baseline = self.coordinator._candidate("baseline")
        task = self.controller.contract["public_splits"]["train"]["tasks"][0]
        assignment = {
            "split": "train", "tasks": [task["id"]], "dataset_sha256": "1" * 64,
            "objective": "sft", "policy_sha256": baseline["policy_sha256"],
            "driver_sha256": baseline["driver_sha256"], "steps": 1,
        }
        self.controller.admit_job(
            self.job_id, "baseline", "training", assignment,
            {"modal_micro_usd": 10_000_000}, 600)
        self.controller.begin_dispatch(self.job_id)
        self.controller.provider_started(self.job_id, "sb-billing")
        self.controller.record_result(
            self.job_id, {"status": "complete"}, digest(b"billing-result"))
        self.controller.provider_cleanup_confirmed(self.job_id, "modal-sandbox-terminated:test")
        plan = {
            "workspace": "test", "environment": "main", "app_id": "ap-billing",
            "tags": {"campaign": "test-gameworld", "job": self.job_id, "identity": "a" * 64},
        }
        receipt = {"sandbox_id": "sb-billing", "returncode": 0,
                   "checked_at": self.finished.isoformat(), "billing_reconciled": False}
        with self.controller.ledger.transaction() as connection:
            connection.execute(
                "CREATE TABLE modal_training_launches (job_id TEXT PRIMARY KEY,plan TEXT NOT NULL,"
                "sandbox_id TEXT,termination_receipt TEXT)")
            connection.execute(
                "INSERT INTO modal_training_launches VALUES (?,?,?,?)",
                (self.job_id, canonical(plan).decode(), "sb-billing", canonical(receipt).decode()))
            reservation = f"job:{self.job_id}:modal_micro_usd"
            for event in connection.execute("SELECT sequence,payload FROM events WHERE kind='reserved'"):
                if json.loads(event["payload"])["id"] == reservation:
                    connection.execute("UPDATE events SET timestamp=? WHERE sequence=?",
                                       (int((self.finished - timedelta(minutes=30)).timestamp()),
                                        event["sequence"]))

    def run_async(self, action):
        return asyncio.run(action)

    def reconciler(self, backend=None):
        return GameWorldModalReconciler(
            self.controller, self.fixture.root / "coordinator/billing", backend or Backend(),
            retry_seconds=0)

    def test_closed_hour_is_reconciled_without_refund_and_job_closes(self):
        backend = Backend()
        result = self.run_async(self.reconciler(backend).run_once(self.now))
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["jobs"], [self.job_id])
        self.assertEqual(result["retained_micro_usd"], 10_000_000)
        snapshot = self.controller.snapshot()
        job = next(job for job in snapshot["jobs"] if job["id"] == self.job_id)
        self.assertEqual(job["state"], "cleaned")
        reservation = next(row for row in snapshot["budget"]["reservations"]
                           if row["id"] == f"job:{self.job_id}:modal_micro_usd")
        self.assertEqual(reservation["state"], "reconciled_retained")
        self.assertEqual(snapshot["budget"]["resources"]["modal_micro_usd"]["committed"], 10_000_000)
        self.assertEqual(len(backend.calls), 1)

    def test_current_hour_and_overlapping_active_hold_wait(self):
        reconciler = self.reconciler()
        self.assertIsNotNone(reconciler.plan(self.now))
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE modal_training_launches SET termination_receipt=? WHERE job_id=?", (
                canonical({"sandbox_id": "sb-billing", "returncode": 0,
                           "checked_at": self.now.isoformat(), "billing_reconciled": False}).decode(),
                self.job_id))
        self.assertIsNone(reconciler.plan(self.now))
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE modal_training_launches SET termination_receipt=? WHERE job_id=?", (
                canonical({"sandbox_id": "sb-billing", "returncode": 0,
                           "checked_at": self.finished.isoformat(), "billing_reconciled": False}).decode(),
                self.job_id))
        self.controller.ledger.reserve("other-modal", "modal_micro_usd", 1,
                                       int((self.now + timedelta(hours=1)).timestamp()))
        with self.controller.ledger.transaction() as connection:
            for event in connection.execute("SELECT sequence,payload FROM events WHERE kind='reserved'"):
                if json.loads(event["payload"])["id"] == "other-modal":
                    connection.execute("UPDATE events SET timestamp=? WHERE sequence=?",
                                       (int(hour(self.finished).timestamp()), event["sequence"]))
        self.assertIsNone(reconciler.plan(self.now))

    def test_crash_after_ledger_reconciliation_recovers_job_state(self):
        reconciler = self.reconciler()
        retain = self.controller.retain_reconciled_jobs
        self.controller.retain_reconciled_jobs = lambda *_args: (_ for _ in ()).throw(
            RuntimeError("synthetic controller crash"))
        first = self.run_async(reconciler.run_once(self.now))
        self.assertEqual(first["outcome"], "failed")
        self.controller.retain_reconciled_jobs = retain
        second = self.run_async(reconciler.run_once(self.now))
        self.assertEqual(second, {"outcome": "recovered", "jobs": [self.job_id]})
        job = next(job for job in self.controller.snapshot()["jobs"] if job["id"] == self.job_id)
        self.assertEqual(job["state"], "cleaned")

    def test_three_provider_failures_stop_campaign(self):
        reconciler = self.reconciler(Backend(fail=True))
        for _ in range(3):
            self.assertEqual(self.run_async(reconciler.run_once(self.now))["outcome"], "failed")
        snapshot = self.controller.snapshot()
        self.assertTrue(snapshot["controller"]["stopped"])
        self.assertTrue(snapshot["budget"]["campaign"]["frozen"])

    def test_provider_failure_uses_retry_backoff(self):
        backend = Backend(fail=True)
        reconciler = GameWorldModalReconciler(
            self.controller, self.fixture.root / "coordinator/billing-backoff", backend)
        self.assertEqual(self.run_async(reconciler.run_once(self.now))["outcome"], "failed")
        self.assertIsNone(self.run_async(reconciler.run_once(self.now)))
        self.assertEqual(len(backend.calls), 1)


if __name__ == "__main__":
    unittest.main()
