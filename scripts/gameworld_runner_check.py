"""Offline provider-runner routing and resume checks."""

import asyncio
import copy
import json
from pathlib import Path
import unittest

from fps_bench.evaluation_contract import digest
from fps_bench.gameworld_runner import GameWorldProviderRunner
import scripts.gameworld_coordinator_check as coordinator_fixtures


MODAL = {
    "workspace": "test", "environment": "main", "environment_id": "en-test",
    "training_app": "training", "training_app_id": "ap-training", "training_image_id": "im-training",
    "serving_app": "serving", "serving_app_id": "ap-serving", "serving_image_id": "im-serving",
}


class FleetLifecycle:
    def __init__(self, controller):
        self.controller = controller
        self.releases = 0

    async def release(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
        if job["state"] == "reserved":
            self.controller.cancel_undispatched(job_id)
        elif job["state"] != "cleaned":
            self.controller.provider_cleanup_confirmed(job_id, "fleet-release:" + job_id)
        self.releases += 1


class FleetExecutor:
    def __init__(self, coordinator, lifecycle):
        self.coordinator = coordinator
        self.controller = coordinator.controller
        self.lifecycle = lifecycle
        self.driver_attempts = 0
        self.evaluations = []
        self.fail = False

    def start(self, job_id):
        with self.controller.ledger.transaction() as connection:
            state = self.controller._job(connection, job_id)["state"]
        if state == "reserved":
            self.controller.begin_dispatch(job_id)
            state = "dispatching"
        if state == "dispatching":
            self.controller.provider_started(job_id, "fleet:test/" + job_id)

    async def driver_candidate(self, job_id, proposal_path, patch_path):
        self.driver_attempts += 1
        self.start(job_id)
        if self.fail:
            raise RuntimeError("synthetic provider failure")
        proposal = json.loads(Path(proposal_path).read_bytes())
        root = self.coordinator.state_root / "fleet" / job_id
        root.mkdir(parents=True, exist_ok=True)
        binary = b"candidate-driver"
        driver_path = root / "cua-driver"
        driver_path.write_bytes(binary)
        baseline = self.coordinator._candidate("baseline")
        candidate = {**copy.deepcopy(baseline), "id": proposal["id"] + "-candidate", "parent": "baseline",
                     "change_class": "driver", "hypothesis": proposal["hypothesis"],
                     "comparison": proposal["id"], "driver_sha256": digest(binary),
                     "patch_sha256": digest(Path(patch_path).read_bytes()), "artifact_root": str(root)}
        self.controller.register_candidate(candidate)
        result = {"status": "complete", "candidate_id": candidate["id"],
                  "driver_sha256": candidate["driver_sha256"]}
        self.controller.record_result(job_id, result, "e" * 64)
        await self.lifecycle.release(job_id)
        return result

    async def evaluate(self, job_id, policy_path, qwen, driver):
        self.start(job_id)
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
            assignment = json.loads(job["specification"])["assignment"]
        self.evaluations.append({"candidate": job["candidate"], "driver": None if driver is None else str(driver),
                                 "policy": str(policy_path), "endpoint": qwen["QWEN_BASE_URL"]})
        result = {**assignment, "candidate": job["candidate"],
                  "contract_sha256": self.controller.contract_hash, "status": "complete",
                  "success": job["candidate"] != "baseline", "steps": 1,
                  "invalid_actions": 0, "seconds": 1.0}
        self.controller.record_result(job_id, result, "f" * 64)
        await self.lifecycle.release(job_id)
        return result

    async def rollout(self, job_id, policy_path, qwen, driver):
        raise AssertionError("Driver runner check must not dispatch rollouts")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = coordinator_fixtures.CoordinatorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.coordinator = self.fixture.coordinator
        self.proposal = self.fixture.fixture.driver_proposal()
        self.coordinator.register(self.proposal)
        self.coordinator.start_next("driver-action")
        target = self.proposal["experiment"]["target_paths"][0]
        self.patch = self.fixture.root / "runner.patch"
        self.patch.write_text(
            f"diff --git a/{target} b/{target}\n--- a/{target}\n+++ b/{target}\n@@ -1 +1 @@\n-old\n+new\n")
        self.coordinator.attach_driver_patch("driver-action", self.patch)
        self.lifecycle = FleetLifecycle(self.coordinator.controller)
        self.fleet = FleetExecutor(self.coordinator, self.lifecycle)
        self.runner = GameWorldProviderRunner(
            self.coordinator, MODAL,
            {"QWEN_BASE_URL": "https://baseline.example/v1", "QWEN_API_KEY": "x" * 32},
            fleet_lifecycle=self.lifecycle, fleet_executor=self.fleet)
        recovery = self.coordinator.supervisor.recovery_actions()[0]
        self.assertEqual(recovery["action"], "resume-coordinator-workflow")
        self.assertEqual(recovery["deadline"], self.coordinator.supervisor.snapshot()["supervisor"]["deadline"])

    def run_async(self, action):
        return asyncio.run(action)

    def test_runner_builds_then_dispatches_paired_baseline_and_candidate(self):
        first = self.run_async(self.runner.run_once(2))
        self.assertEqual(first["dispatch"][0]["kind"], "driver_build")
        self.assertEqual(self.fleet.driver_attempts, 1)
        self.assertEqual(self.coordinator.workflow(self.proposal["id"])["state"], "evaluating")
        second = self.run_async(self.runner.run_once(2))
        self.assertEqual(len(second["dispatch"]), 2)
        self.assertEqual({row["candidate"] for row in self.fleet.evaluations},
                         {"baseline", "driver-input-candidate"})
        candidate = next(row for row in self.fleet.evaluations if row["candidate"] != "baseline")
        baseline = next(row for row in self.fleet.evaluations if row["candidate"] == "baseline")
        self.assertIsNotNone(candidate["driver"])
        self.assertIsNone(baseline["driver"])
        self.assertEqual({row["endpoint"] for row in self.fleet.evaluations},
                         {"https://baseline.example/v1"})

    def test_runner_resumes_dispatching_build_without_second_admission(self):
        admitted = self.coordinator.admit_ready(1)[0]["job_id"]
        self.coordinator.controller.begin_dispatch(admitted)
        result = self.run_async(self.runner.run_once(1))
        self.assertEqual(result["admitted"], [])
        self.assertEqual(result["dispatch"][0]["outcome"], "complete")
        self.assertEqual(self.fleet.driver_attempts, 1)
        self.assertEqual(self.lifecycle.releases, 1)
        self.assertEqual(self.coordinator.workflow(self.proposal["id"])["state"], "evaluating")

    def test_runner_materializes_patch_before_same_cycle_dispatch(self):
        fixture = coordinator_fixtures.CoordinatorTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        coordinator = fixture.coordinator
        proposal = fixture.fixture.driver_proposal("runner-research-patch")
        coordinator.register(proposal)
        coordinator.start_next("runner-research-action")

        class Research:
            async def materialize_required(inner_self):
                target = proposal["experiment"]["target_paths"][0]
                patch = fixture.root / "research.patch"
                patch.write_text(
                    f"diff --git a/{target} b/{target}\n--- a/{target}\n+++ b/{target}\n"
                    "@@ -1 +1 @@\n-old\n+new\n")
                coordinator.attach_driver_patch("runner-research-action", patch)
                return [{"kind": "driver-patch", "outcome": "attached"}]

        lifecycle = FleetLifecycle(coordinator.controller)
        fleet = FleetExecutor(coordinator, lifecycle)
        runner = GameWorldProviderRunner(
            coordinator, MODAL,
            {"QWEN_BASE_URL": "https://baseline.example/v1", "QWEN_API_KEY": "x" * 32},
            fleet_lifecycle=lifecycle, fleet_executor=fleet, research_worker=Research())
        result = self.run_async(runner.run_once(1))
        self.assertEqual(result["research"][0]["outcome"], "attached")
        self.assertEqual(result["dispatch"][0]["kind"], "driver_build")
        self.assertEqual(fleet.driver_attempts, 1)

    def test_research_stop_rechecks_gate_before_admission(self):
        class Research:
            async def materialize_required(inner_self):
                self.coordinator.controller.stop("synthetic research stop")
                return [{"kind": "driver-patch", "outcome": "failed"}]

        runner = GameWorldProviderRunner(
            self.coordinator, MODAL,
            {"QWEN_BASE_URL": "https://baseline.example/v1", "QWEN_API_KEY": "x" * 32},
            fleet_lifecycle=self.lifecycle, fleet_executor=self.fleet, research_worker=Research())
        result = self.run_async(runner.run_once(1))
        self.assertEqual(result["admitted"], [])
        self.assertEqual(result["dispatch"], [])
        self.assertEqual(self.fleet.driver_attempts, 0)

    def test_billing_stop_rechecks_gate_before_admission(self):
        class Billing:
            async def run_once(inner_self):
                self.coordinator.controller.stop("synthetic billing stop")
                return {"outcome": "failed"}

        runner = GameWorldProviderRunner(
            self.coordinator, MODAL,
            {"QWEN_BASE_URL": "https://baseline.example/v1", "QWEN_API_KEY": "x" * 32},
            fleet_lifecycle=self.lifecycle, fleet_executor=self.fleet,
            billing_reconciler=Billing())
        result = self.run_async(runner.run_once(1))
        self.assertEqual(result["billing"], {"outcome": "failed"})
        self.assertEqual(result["admitted"], [])
        self.assertEqual(result["dispatch"], [])
        self.assertEqual(self.fleet.driver_attempts, 0)

    def test_runner_emits_budget_and_candidate_evaluation_metrics(self):
        class Telemetry:
            campaign = "test-gameworld"

            def __init__(self):
                self.rows = []

            def record(self, *args, **kwargs):
                self.rows.append((args, kwargs))
                return True

            def flush(self):
                return {"metrics": True, "logs": True}

        telemetry = Telemetry()
        self.coordinator.supervisor.telemetry = telemetry
        self.run_async(self.runner.run_once(2))
        self.run_async(self.runner.run_once(2))
        workflow = self.coordinator.workflow(self.proposal["id"])
        self.coordinator.emit_evaluation(
            workflow, workflow["candidate_id"], {"decision": "nominate"}, "paired")
        services = [row[0][1] for row in telemetry.rows]
        self.assertIn("gameworld-research", services)
        self.assertIn("gameworld-eval", services)
        evaluation = next(row[0][3] for row in telemetry.rows if row[0][1] == "gameworld-eval")
        self.assertEqual(evaluation["gameworld_eval_completed_episodes"], 2)
        self.assertEqual(evaluation["gameworld_eval_success_rate"], 1)

    def test_three_durable_provider_failures_stop_new_admission(self):
        for index in range(3):
            with self.coordinator.controller.ledger.transaction() as connection:
                self.coordinator.controller.ledger._event(connection, "gameworld_runner_dispatch", {
                    "job_id": f"failed-{index}", "kind": "driver_build",
                    "outcome": "failed", "error_type": "RuntimeError",
                })
        result = self.run_async(self.runner.run_once(1))
        snapshot = self.coordinator.controller.snapshot()
        self.assertTrue(snapshot["controller"]["stopped"])
        self.assertTrue(snapshot["budget"]["campaign"]["frozen"])
        self.assertEqual(result["admitted"], [])
        self.assertEqual(result["dispatch"], [])
        self.assertEqual(self.fleet.driver_attempts, 0)


if __name__ == "__main__":
    unittest.main()
