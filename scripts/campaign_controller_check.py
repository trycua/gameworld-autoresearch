"""Offline state-machine integration checks, with no real provider dispatch."""

import copy
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fps_bench.campaign_controller import CampaignController
from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, schedule

ROOT = Path(__file__).resolve().parents[1]


def contend(arguments):
    database, contract, expected_hash, index = arguments
    controller = CampaignController(database, contract, expected_hash)
    try:
        controller.admit_job(f"build-{index}", "baseline", "driver_build", {}, {}, 600)
        return True
    except BudgetRefused:
        return False


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        template = json.loads((ROOT / "configs/qwen-gameworld-baseline.json").read_bytes())
        del template["seed"]
        spec = json.loads((ROOT / "configs/evaluation/gameworld-2048-v2.json").read_bytes())
        private = {"nonce": "offline-fixture", "splits": {
            "confirmation": {"seeds": list(range(2001, 2025)), "repeats": 1},
            "sealed": {"seeds": list(range(3001, 3033)), "repeats": 1}}}
        self.contract = {"spec": spec, "episode_template": template, "public_splits": {
            "development": {"seeds": list(range(1001, 1009)), "repeats": 2},
            "train": {"seeds": [42], "repeats": 1}}, "private_split_commitment": digest(canonical(private))}
        self.contract_path = self.home / "contract.json"
        self.contract_path.write_bytes(canonical(self.contract))
        self.private_path = self.home / "private.json"
        self.private_path.write_bytes(canonical(private))
        self.hash = digest(canonical(self.contract))
        self.database = self.home / "controller.sqlite"
        self.controller = CampaignController(self.database, self.contract_path, self.hash, self.private_path)
        self.controller.initialize("offline-controller")
        self.baseline = {"id": "baseline", "parent": None, "change_class": "baseline", "hypothesis": "pristine baseline",
                         "contract_hash": self.hash, "image": spec["provenance"]["image"], "driver_sha256": "a" * 64,
                         "model": {"base_model": template["model"], "base_revision": template["revision"],
                                   "processor_revision": template["revision"], "adapter_sha256": None,
                                   "served_model": template["served_model"]}}
        self.controller.register_candidate(self.baseline)
        self.candidate = {**copy.deepcopy(self.baseline), "id": "candidate", "parent": "baseline", "change_class": "driver",
                          "hypothesis": "offline changed driver fixture", "driver_sha256": "b" * 64, "patch_sha256": "c" * 64}
        self.controller.register_candidate(self.candidate)

    def admit(self, job="job-one", kind="training", candidate="baseline", amount=100):
        reservations = {} if kind == "driver_build" else {
            "litellm_tokens" if kind == "research" else "modal_micro_usd": amount}
        assignment = {"split": "train", "seeds": [42], "dataset_sha256": "d" * 64} if kind == "training" else {}
        return self.controller.admit_job(job, candidate, kind, assignment, reservations, 600)

    def finish(self, job="job-one", result=None, actual=40):
        self.controller.begin_dispatch(job)
        self.controller.provider_started(job, "fake-provider:" + job)
        self.controller.record_result(job, result or {"status": "complete"}, "d" * 64)
        self.controller.cleanup_confirmed(job, "fake-validated-receipt:" + job, {"modal_micro_usd": actual})

    def test_manifest_immutability_and_driver_model_separation(self):
        self.controller.register_candidate(self.candidate)
        changed = {**self.candidate, "hypothesis": "changed"}
        with self.assertRaises(LedgerConflict):
            self.controller.register_candidate(changed)
        changed = copy.deepcopy(self.candidate)
        changed["id"] = "mixed-candidate"
        changed["model"]["served_model"] = "different"
        with self.assertRaises(ValueError):
            self.controller.register_candidate(changed)

    def test_model_candidate_requires_adapter_and_fixed_driver(self):
        model = {**copy.deepcopy(self.baseline), "id": "model-candidate", "parent": "baseline", "change_class": "model"}
        model["model"]["served_model"] = "adapter-1"
        with self.assertRaises(ValueError):
            self.controller.register_candidate(model)
        model["model"]["adapter_sha256"] = "f" * 64
        self.controller.register_candidate(model)

    def test_parallel_builds_share_two_desktop_slots(self):
        with ProcessPoolExecutor(max_workers=8) as executor:
            accepted = list(executor.map(contend, [(str(self.database), str(self.contract_path), self.hash, index)
                                                   for index in range(12)]))
        self.assertEqual(sum(accepted), 2)

    def test_training_limit_includes_cleanup_pending(self):
        self.admit()
        self.controller.begin_dispatch("job-one")
        self.controller.provider_started("job-one", "fake-provider")
        self.controller.record_result("job-one", {"status": "complete"}, "d" * 64)
        with self.assertRaises(BudgetRefused):
            self.admit("job-two")
        self.controller.cleanup_confirmed("job-one", "fake-receipt", {"modal_micro_usd": 40})
        self.admit("job-two")

    def test_job_and_reservation_rollback_together(self):
        original = self.controller.ledger._event
        def crash(connection, kind, payload):
            if kind == "job_admitted":
                raise RuntimeError("simulated transaction crash")
            return original(connection, kind, payload)
        with patch.object(self.controller.ledger, "_event", side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.admit()
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot["jobs"], [])
        self.assertEqual(snapshot["budget"]["reservations"], [])

    def test_budget_refusal_never_creates_job(self):
        with self.assertRaises(BudgetRefused):
            self.admit(amount=1_800_000_001)
        self.assertEqual(self.controller.snapshot()["jobs"], [])

    def test_admission_idempotency_is_not_dispatch_permission(self):
        self.admit()
        self.admit()
        self.controller.begin_dispatch("job-one")
        self.assertEqual(self.admit()["state"], "dispatching")
        with self.assertRaises(LedgerConflict):
            self.controller.begin_dispatch("job-one")
        with self.assertRaises(LedgerConflict):
            self.admit(amount=101)

    def test_restart_exposes_ambiguous_submission_without_relaunch(self):
        self.admit()
        self.controller.begin_dispatch("job-one")
        reopened = CampaignController(self.database, self.contract_path, self.hash)
        reopened.initialize("offline-controller")
        self.assertEqual(reopened.recovery_actions()[0]["action"], "reconcile_ambiguous_submission")
        with self.assertRaises(LedgerConflict):
            reopened.cancel_undispatched("job-one")
        with self.assertRaises(LedgerConflict):
            reopened.begin_dispatch("job-one")

    def test_undispatched_cancellation_refunds_once(self):
        self.admit()
        self.controller.cancel_undispatched("job-one")
        self.controller.cancel_undispatched("job-one")
        self.assertEqual(self.controller.snapshot()["budget"]["resources"]["modal_micro_usd"]["committed"], 0)

    def test_stop_preserves_cleanup_and_blocks_new_work(self):
        self.admit()
        self.controller.begin_dispatch("job-one")
        self.controller.provider_started("job-one", "fake-provider")
        self.controller.stop("offline stop test")
        self.assertEqual(self.controller.recovery_actions()[0]["action"], "cancel_and_reconcile")
        with self.assertRaises(BudgetRefused):
            self.admit("job-two", kind="research")
        self.controller.cleanup_confirmed("job-one", "fake-stop-receipt", {"modal_micro_usd": 40})
        self.assertEqual(self.controller.recovery_actions(), [])

    def test_cleanup_is_atomic_with_all_resource_settlements(self):
        self.controller.admit_job("both", "baseline", "research", {}, {"modal_micro_usd": 100, "litellm_tokens": 100}, 600)
        self.controller.begin_dispatch("both")
        with self.assertRaises(ValueError):
            self.controller.cleanup_confirmed("both", "fake-receipt", {"modal_micro_usd": 40, "litellm_tokens": -1})
        self.assertTrue(all(row["state"] == "held" for row in self.controller.snapshot()["budget"]["reservations"]))
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "dispatching")

    def test_expired_and_mismatched_deadlines_fail_closed(self):
        self.admit()
        with self.controller.ledger.transaction() as connection:
            deadline = connection.execute("SELECT deadline FROM jobs").fetchone()[0]
        with patch("time.time", return_value=deadline + 1):
            with self.assertRaises(BudgetRefused):
                self.controller.begin_dispatch("job-one")
            self.assertEqual(self.controller.recovery_actions()[0]["action"], "cancel_undispatched")
        with self.assertRaises(LedgerConflict):
            self.controller.initialize("offline-controller", duration_seconds=3600)

    def test_training_refuses_development_and_private_seeds(self):
        for seed in (1001, 2001, 3001, True):
            with self.assertRaises(ValueError):
                self.controller.admit_job("leaked-training", "baseline", "training",
                                          {"split": "train", "seeds": [seed], "dataset_sha256": "d" * 64},
                                          {"modal_micro_usd": 100}, 600)
        self.assertEqual(self.controller.snapshot()["jobs"], [])

    def test_telemetry_records_settled_and_reserved_separately(self):
        self.controller.ledger.record_prior_usage("historical", "modal_micro_usd", 200, "provider-row")
        self.admit()
        self.finish()
        self.admit("job-two")
        class Recorder:
            campaign = "offline-controller"
            def record(self, event_id, service, attributes, values):
                self.values = values
        recorder = Recorder()
        self.assertTrue(self.controller.emit_telemetry(recorder, "accounting-one"))
        self.assertEqual(recorder.values["gameworld_modal_spend"], 240 / 1_000_000)
        self.assertEqual(recorder.values["gameworld_modal_reserved"], 100 / 1_000_000)
        self.assertEqual(recorder.values["gameworld_active_training_jobs"], 0)
        self.assertEqual(recorder.values["gameworld_training_slots_reserved"], 1)
        recorder.campaign = "wrong-campaign"
        self.assertFalse(self.controller.emit_telemetry(recorder, "accounting-two"))

    def test_fresh_private_split_work_is_disabled_without_access_gate(self):
        with self.assertRaises(BudgetRefused):
            self.controller.admit_job("private-job", "candidate", "evaluation",
                                      {"split": "confirmation", "seed": 2001, "repeat": 0}, {"modal_micro_usd": 100}, 600)

    def test_development_round_retains_champion_and_nominates_only(self):
        self.run_development(candidate_wins=True)
        result = self.controller.decide_development("candidate")
        self.assertEqual(result["decision"], "nominate")
        self.assertEqual(self.controller.decide_development("candidate"), result)
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot["controller"]["champion"], "baseline")
        self.assertEqual(next(row for row in snapshot["candidates"] if row["id"] == "candidate")["state"], "nominated")
        self.assertEqual(snapshot["recovery"], [])
        self.assertEqual(len(snapshot["jobs"]), 32)

    def test_losing_candidate_rejected_without_champion_mutation(self):
        self.run_development(candidate_wins=False)
        self.assertEqual(self.controller.decide_development("candidate")["decision"], "no_improvement")
        self.assertEqual(self.controller.snapshot()["controller"]["champion"], "baseline")
        with self.assertRaises(BudgetRefused):
            self.admit("more-work", candidate="candidate")

    def run_development(self, candidate_wins):
        for repeat in range(2):
            for seed in range(1001, 1009):
                for candidate in ("baseline", "candidate"):
                    job = f"eval-{candidate}-{seed}-{repeat}"
                    assignment = {"split": "development", "seed": seed, "repeat": repeat}
                    self.controller.admit_job(job, candidate, "evaluation", assignment, {"modal_micro_usd": 100}, 600)
                    success = candidate_wins if candidate == "candidate" else not candidate_wins
                    self.finish(job, {**assignment, "candidate": candidate, "contract_sha256": self.hash,
                                      "status": "complete", "success": success, "steps": 60,
                                      "invalid_actions": 0, "seconds": 100}, actual=40)


class GameWorldControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.tasks = [
            {"id": f"0{index}_game--0{index}_03", "game": f"0{index}_game",
             "task": f"0{index}_03", "seed": 42}
            for index in range(1, 5)
        ]
        train = [{"id": "01_game--01_01", "game": "01_game", "task": "01_01", "seed": 42}]
        spec = {"suite_id": "gameworld-task-controller", "assignment_kind": "gameworld-task",
                "provenance": {"image": "ghcr.io/example/gameworld@sha256:" + "a" * 64},
                "rules": {"familywise_alpha": 0.05, "maximum_confirmations": 2,
                          "maximum_invalid_action_rate_increase": 0.05,
                          "maximum_median_latency_ratio": 1.5, "minimum_absolute_improvement": 0.25}}
        template = {"model": "Qwen/Qwen3-VL-2B-Instruct", "revision": "b" * 40,
                    "served_model": "qwen-baseline", "max_steps": 60}
        self.contract = {"spec": spec, "episode_template": template, "public_splits": {
            "train": {"tasks": train, "repeats": 1},
            "development": {"tasks": self.tasks, "repeats": 1},
        }}
        self.contract_path = self.home / "contract.json"
        self.contract_path.write_bytes(canonical(self.contract))
        self.hash = digest(canonical(self.contract))
        self.controller = CampaignController(self.home / "controller.sqlite", self.contract_path, self.hash)
        self.controller.initialize("gameworld-controller")
        self.baseline = {"id": "baseline", "parent": None, "change_class": "baseline",
                         "hypothesis": "baseline", "contract_hash": self.hash,
                         "image": spec["provenance"]["image"], "driver_sha256": "c" * 64,
                         "policy_sha256": "d" * 64,
                         "model": {"base_model": template["model"], "base_revision": template["revision"],
                                   "processor_revision": template["revision"], "adapter_sha256": None,
                                   "served_model": template["served_model"]}}
        self.controller.register_candidate(self.baseline)

    def complete(self, job, candidate, assignment, success):
        self.controller.begin_dispatch(job)
        self.controller.provider_started(job, "provider:" + job)
        result = {**assignment, "candidate": candidate, "contract_sha256": self.hash,
                  "status": "complete", "success": success, "steps": 10,
                  "invalid_actions": 0, "seconds": 5.0}
        self.controller.record_result(job, result, "e" * 64)
        self.controller.cleanup_confirmed(job, "receipt:" + job, {"modal_micro_usd": 10})

    def test_task_jobs_and_delayed_billing_release_concurrency(self):
        assignment = {"split": "development", "task_id": self.tasks[0]["id"],
                      "game": self.tasks[0]["game"], "task": self.tasks[0]["task"],
                      "seed": 42, "repeat": 0}
        self.controller.admit_job("task-eval", "baseline", "evaluation", assignment,
                                  {"modal_micro_usd": 100}, 600)
        self.controller.begin_dispatch("task-eval")
        self.controller.provider_started("task-eval", "fleet:claim")
        self.controller.record_result("task-eval", {**assignment, "candidate": "baseline",
                                      "contract_sha256": self.hash, "status": "complete", "success": False,
                                      "steps": 10, "invalid_actions": 0, "seconds": 5.0}, "e" * 64)
        self.controller.provider_cleanup_confirmed("task-eval", "fleet-released")
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "billing_pending")
        probe = {"pool": "test-pool", "operation": "warm-driver-probe"}
        self.controller.admit_job("build-one", "baseline", "driver_build", probe, {}, 600)
        self.controller.admit_job("build-two", "baseline", "driver_build", probe, {}, 600)
        with self.assertRaises(BudgetRefused):
            self.controller.admit_job("build-three", "baseline", "driver_build", probe, {}, 600)
        self.controller.settle_job("task-eval", {"modal_micro_usd": 40}, "modal-row-1")
        self.controller.settle_job("task-eval", {"modal_micro_usd": 40}, "modal-row-1")
        with self.assertRaises(LedgerConflict):
            self.controller.settle_job("task-eval", {"modal_micro_usd": 41}, "modal-row-1")
        job = next(row for row in self.controller.snapshot()["jobs"] if row["id"] == "task-eval")
        self.assertEqual(job["state"], "cleaned")

    def test_rollout_and_training_bind_source_candidate_identity(self):
        task = self.contract["public_splits"]["train"]["tasks"][0]
        rollout = {"split": "train", "task_id": task["id"], "game": task["game"], "task": task["task"],
                   "seed": task["seed"], "repeat": 0, "group_id": "group-one", "members": 2,
                   "max_steps": 4, "policy_sha256": self.baseline["policy_sha256"],
                   "driver_sha256": self.baseline["driver_sha256"]}
        self.controller.admit_job("rollout-one", "baseline", "rollout", rollout,
                                  {"modal_micro_usd": 100}, 600)
        changed = {**rollout, "policy_sha256": "f" * 64}
        with self.assertRaises(ValueError):
            self.controller.admit_job("rollout-bad", "baseline", "rollout", changed,
                                      {"modal_micro_usd": 100}, 600)
        training = {"split": "train", "tasks": [task["id"]], "dataset_sha256": "1" * 64,
                    "objective": "grpo", "policy_sha256": self.baseline["policy_sha256"],
                    "driver_sha256": self.baseline["driver_sha256"], "steps": 2}
        self.controller.admit_job("training-one", "baseline", "training", training,
                                  {"modal_micro_usd": 100}, 600)

    def test_joint_registration_and_factorial_decision(self):
        driver = {**copy.deepcopy(self.baseline), "id": "driver-candidate", "parent": "baseline",
                  "change_class": "driver", "driver_sha256": "2" * 64, "patch_sha256": "3" * 64}
        model = {**copy.deepcopy(self.baseline), "id": "model-candidate", "parent": "baseline",
                 "change_class": "model", "policy_sha256": "4" * 64}
        model["model"]["adapter_sha256"] = "5" * 64
        model["model"]["served_model"] = "qwen-model-candidate"
        self.controller.register_candidate(driver)
        self.controller.register_candidate(model)
        joint = {**copy.deepcopy(driver), "id": "joint-candidate", "change_class": "joint",
                 "model": copy.deepcopy(model["model"]), "policy_sha256": model["policy_sha256"],
                 "components": {"driver": driver["id"], "model": model["id"]}}
        with self.assertRaises(LedgerConflict):
            self.controller.register_candidate(joint)
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE candidates SET state='nominated' WHERE id IN (?,?)",
                               (driver["id"], model["id"]))
        self.controller.register_candidate(joint)
        candidates = ["baseline", driver["id"], model["id"], joint["id"]]
        for index, run in enumerate(schedule(self.contract, "development", candidates, 7)):
            candidate = run["candidate"]
            task_index = int(run["task_id"][:2])
            success = (candidate == joint["id"]
                       or candidate == driver["id"] and task_index == 1
                       or candidate == model["id"] and task_index == 2)
            assignment = {key: run[key] for key in ("split", "task_id", "game", "task", "seed", "repeat")}
            job = f"factorial-{index}"
            self.controller.admit_job(job, candidate, "evaluation", assignment,
                                      {"modal_micro_usd": 100}, 600)
            self.complete(job, candidate, assignment, success)
        result = self.controller.decide_factorial(joint["id"])
        self.assertEqual(result["decision"], "nominate_joint")
        candidate = next(row for row in self.controller.snapshot()["candidates"] if row["id"] == joint["id"])
        self.assertEqual(candidate["state"], "nominated")


if __name__ == "__main__":
    unittest.main()
