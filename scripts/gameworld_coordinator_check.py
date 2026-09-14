"""Offline checks for the durable GameWorld joint workflow coordinator."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_coordinator import GameWorldCoordinator
from fps_bench.gameworld_training import GameWorldTrainingRegistry
import scripts.gameworld_research_check as research_fixtures


class Registry:
    def __init__(self):
        self.registered = []

    def register_rollout(self, job_id, root, receipt):
        self.registered.append((job_id, str(root), receipt["job_id"]))

    def export(self, job_ids, output):
        Path(output).mkdir(parents=True)
        return {"dataset_sha256": "9" * 64, "root": str(Path(output).resolve()), "jobs": job_ids}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = research_fixtures.SupervisorTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        context = self.fixture.supervisor.context
        tasks = context["assignments"]
        split = lambda name: [{**tasks[identity], "seed": 42} for identity in context["splits"][name]]
        spec = {
            "suite_id": "gameworld-coordinator-check", "assignment_kind": "gameworld-task",
            "baseline_driver_sha256": "c" * 64,
            "provenance": {"image": "ghcr.io/example/gameworld@sha256:" + "a" * 64},
            "rules": {"familywise_alpha": 0.05, "maximum_confirmations": 2,
                      "maximum_invalid_action_rate_increase": 0.05,
                      "maximum_median_latency_ratio": 1.5, "minimum_absolute_improvement": 0.125,
                      "sealed_uses": 1},
        }
        model = self.fixture.supervisor.policy["model"]
        private = {"nonce": "coordinator-private-fixture", "splits": {
            "confirmation": {"tasks": split("confirmation"), "repeats": 1},
            "sealed": {"tasks": split("sealed"), "repeats": 1},
        }}
        self.contract = {
            "spec": spec,
            "episode_template": {"model": model["base_model"], "revision": model["base_revision"],
                                 "served_model": "qwen-baseline", "max_steps": 60},
            "public_splits": {"train": {"tasks": split("train"), "repeats": 1},
                              "development": {"tasks": split("development"), "repeats": 2}},
            "private_split_commitment": digest(canonical(private)),
        }
        self.contract_path = self.root / "contract.json"
        self.contract_path.write_bytes(canonical(self.contract))
        self.private_path = self.root / "private-splits.json"
        self.private_path.write_bytes(canonical(private))
        self.contract_hash = digest(canonical(self.contract))
        self.identity = {
            "base_model": model["base_model"], "base_revision": model["base_revision"],
            "adapter_sha256": None, "served_model": "qwen-baseline",
            "deployment": {"app_id": "ap-Test", "function_id": "fu-Test", "image_id": "im-Test",
                           "endpoint_sha256": "d" * 64},
            "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                           "response_format": "unconstrained-json-text"},
        }
        self.policy_path = self.root / "baseline-policy.json"
        self.policy_path.write_bytes(canonical(self.identity))
        self.registry = Registry()
        self.coordinator = GameWorldCoordinator(
            self.root / "campaign.sqlite", self.contract_path, self.contract_hash,
            self.fixture.baseline, self.root / "coordinator", self.fixture.policy,
            self.fixture.catalog, pool="test-pool", registry=self.registry,
            private_splits=self.private_path, verify_workspace=False)
        self.coordinator.initialize("test-gameworld", self.policy_path)

    def finish_job(self, job_id, result, cleanup=True):
        controller = self.coordinator.controller
        controller.begin_dispatch(job_id)
        controller.provider_started(job_id, "provider:" + job_id)
        controller.record_result(job_id, result, "e" * 64)
        if cleanup:
            controller.provider_cleanup_confirmed(job_id, "cleanup:" + job_id)

    def start_baseline_serving(self, proposal_id):
        workflow = self.coordinator.workflow(proposal_id)
        item = self.coordinator._items(proposal_id, workflow["details"]["baseline_serving_phase"])[0]
        admitted = self.coordinator.admit_ready(1)[0]["job_id"]
        self.assertEqual(admitted, item["job_id"])
        self.finish_job(admitted, {"status": "complete", "candidate_id": item["candidate"],
                                   "adapter_manifest_sha256": None,
                                   "policy_sha256": item["assignment"]["policy_sha256"]}, cleanup=False)
        return self.coordinator.advance()

    def stop_baseline_serving(self, proposal_id):
        workflow = self.coordinator.workflow(proposal_id)
        job_id = self.coordinator._items(
            proposal_id, workflow["details"]["baseline_serving_phase"])[0]["job_id"]
        self.coordinator.controller.provider_cleanup_confirmed(job_id, "cleanup:" + job_id)
        self.coordinator.controller.settle_job(
            job_id, {"modal_micro_usd": 0}, "billing:" + job_id)
        return self.coordinator.advance()

    def test_driver_patch_routes_to_paired_full_gameworld_evaluation(self):
        proposal = self.fixture.driver_proposal()
        self.coordinator.register(proposal)
        self.coordinator.start_next("driver-action")
        patch = self.root / "candidate.patch"
        target = proposal["experiment"]["target_paths"][0]
        patch.write_text(f"diff --git a/{target} b/{target}\n--- a/{target}\n+++ b/{target}\n@@ -1 +1 @@\n-old\n+new\n")
        self.coordinator.attach_driver_patch("driver-action", patch)
        build = self.coordinator.admit_ready(1)[0]["job_id"]
        baseline = self.coordinator._candidate("baseline")
        candidate = {**copy.deepcopy(baseline), "id": "driver-input-candidate", "parent": "baseline",
                     "change_class": "driver", "hypothesis": proposal["hypothesis"],
                     "comparison": proposal["id"], "driver_sha256": "1" * 64,
                     "patch_sha256": digest(patch.read_bytes())}
        self.coordinator.controller.register_candidate(candidate)
        self.finish_job(build, {"status": "complete", "candidate_id": candidate["id"],
                                "driver_sha256": candidate["driver_sha256"]})
        self.assertEqual(self.coordinator.advance(), [{
            "workflow": proposal["id"], "state": "starting_baseline_serving"}])
        self.assertEqual(self.start_baseline_serving(proposal["id"]), [{
            "workflow": proposal["id"], "state": "evaluating"}])
        items = self.coordinator._items(proposal["id"], "development")
        self.assertEqual(len(items), 136)
        self.assertEqual(sum(item["candidate"] == "baseline" for item in items), 68)
        self.assertEqual({item["assignment"]["comparison"] for item in items}, {proposal["id"]})
        reopened = GameWorldCoordinator(
            self.root / "campaign.sqlite", self.contract_path, self.contract_hash,
            self.fixture.baseline, self.root / "coordinator", self.fixture.policy,
            self.fixture.catalog, pool="test-pool", registry=self.registry,
            private_splits=self.private_path, verify_workspace=False)
        reopened.initialize("test-gameworld", self.policy_path)
        self.assertEqual(reopened.workflow(proposal["id"])["candidate_id"], candidate["id"])
        self.assertEqual(len(reopened._items(proposal["id"], "development")), 136)

    def test_production_initialization_rejects_nonfrozen_coordinator_source(self):
        with self.assertRaises(ValueError):
            GameWorldCoordinator(
                self.root / "other.sqlite", self.contract_path, self.contract_hash,
                self.fixture.baseline, self.root / "other-coordinator", self.fixture.policy,
                self.fixture.catalog, pool="test-pool", registry=self.registry,
                private_splits=self.private_path)

    def test_grpo_routes_rollout_dataset_training_serving_and_pairing(self):
        proposal = self.fixture.model_proposal()
        self.coordinator.register(proposal)
        self.coordinator.start_next("model-action")
        self.assertEqual(len(self.coordinator._items(proposal["id"], "baseline-serving-rollout")), 1)
        self.start_baseline_serving(proposal["id"])
        self.assertEqual(len(self.coordinator._items(proposal["id"], "rollout")), 1)
        self.assertEqual(self.coordinator.workflow(proposal["id"])["details"]["modal_allocation"], {
            "training_micro_usd": 5_000_000, "serving_micro_usd": 10_000_000,
        })
        self.coordinator.allocate_model_budget("model-action", 5_000_000, 10_000_000)
        rollout = self.coordinator.admit_ready(1)[0]["job_id"]
        artifact = self.root / "coordinator/fleet" / rollout
        artifact.mkdir(parents=True)
        (artifact / "artifact-receipt.json").write_bytes(canonical({"job_id": rollout}))
        assignment = self.coordinator._items(proposal["id"], "rollout")[0]["assignment"]
        self.finish_job(rollout, {**assignment, "candidate": "baseline",
                                  "contract_sha256": self.contract_hash, "status": "complete",
                                  "dataset_sha256": "8" * 64})
        self.coordinator.advance()
        self.assertEqual(self.coordinator.workflow(proposal["id"])["state"],
                         "awaiting_baseline_serving_stop")
        self.stop_baseline_serving(proposal["id"])
        self.assertEqual(self.coordinator.workflow(proposal["id"])["state"], "awaiting_dataset")
        self.coordinator.prepare_training_dataset("model-action")
        training = self.coordinator.admit_ready(1)[0]["job_id"]
        adapter = "7" * 64
        self.finish_job(training, {"status": "complete", "objective": "grpo",
                                   "adapter_manifest_sha256": adapter})
        self.coordinator.advance()
        workflow = self.coordinator.workflow(proposal["id"])
        self.assertEqual(workflow["state"], "serving")
        serving = self.coordinator.admit_ready(1)[0]["job_id"]
        served_model = self.coordinator._items(proposal["id"], "serving")[0]["assignment"]["served_model"]
        baseline = self.coordinator._candidate("baseline")
        candidate = {**copy.deepcopy(baseline), "id": served_model, "parent": "baseline",
                     "change_class": "model", "hypothesis": proposal["hypothesis"],
                     "comparison": proposal["id"], "policy_sha256": "6" * 64}
        candidate["model"]["adapter_sha256"] = adapter
        candidate["model"]["served_model"] = served_model
        self.coordinator.controller.register_candidate(candidate)
        self.finish_job(serving, {"status": "complete", "candidate_id": served_model,
                                  "adapter_manifest_sha256": adapter, "policy_sha256": "6" * 64}, cleanup=False)
        self.coordinator.advance()
        items = self.coordinator._items(proposal["id"], "development")
        self.assertEqual(self.coordinator.workflow(proposal["id"])["state"], "evaluating")
        self.assertEqual(len(items), 136)
        self.assertEqual({item["candidate"] for item in items}, {"baseline", served_model})
        self.assertEqual(self.coordinator.controller.snapshot()["budget"]["resources"]["modal_micro_usd"]["committed"],
                         15_000_000)

    def test_sft_attaches_authenticated_dataset_without_invalid_grpo_rollout(self):
        proposal = self.fixture.model_proposal("model-sft")
        proposal["experiment"]["objective"] = "sft"
        proposal["experiment"]["rollouts_per_task"] = 1
        proposal["experiment"]["sft_source_id"] = "test-sft-source"
        self.coordinator.register(proposal)
        self.coordinator.start_next("sft-action")
        self.assertEqual(self.coordinator._items(proposal["id"]), [])
        self.assertEqual(self.coordinator.required_actions()[0]["action"], "attach-authenticated-sft-dataset")
        self.coordinator.allocate_model_budget("sft-action", 5_000_000, 10_000_000)
        task = proposal["experiment"]["training_tasks"][0]
        dataset = self.root / "sft-dataset"
        (dataset / "images").mkdir(parents=True)
        image_path = dataset / "image.png"
        Image.new("RGB", (16, 16), (1, 2, 3)).save(image_path)
        image = image_path.read_bytes()
        image_name = "images/" + digest(image) + ".png"
        image_path.rename(dataset / image_name)
        sample = {"id": task + ":demo-1", "messages": [
            {"role": "system", "content": "play"},
            {"role": "user", "content": [{"type": "text", "text": "act"},
                                             {"type": "image", "image": image_name}]},
        ], "completion": [{"role": "assistant", "content": '{"tool_name":"wait","arguments":{}}'}]}
        samples = canonical(sample)
        (dataset / "samples.jsonl").write_bytes(samples)
        source = {"schema_version": 1, "kind": "teacher-policy", "tasks": [task],
                  "rights": "Synthetic test fixture", "artifact_sha256": "5" * 64,
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "evaluation_policy_contains_privileged_state": False}
        source_path = self.root / "sft-source.json"
        source_path.write_bytes(canonical(source))
        manifest = {"schema_version": 1, "purpose": "train-only-action-imitation",
                    "contract_sha256": self.contract_hash, "samples": 1, "episodes": [],
                    "files": {"samples.jsonl": digest(samples), image_name: digest(image)},
                    "gameworld": {"schema_version": 1, "tasks": [task],
                                  "driver_sha256": "c" * 64,
                                  "source_receipt_sha256": digest(canonical(source))}}
        (dataset / "dataset.json").write_bytes(canonical(manifest))
        dataset_sha256 = digest(canonical(manifest))
        self.coordinator.registry = GameWorldTrainingRegistry(
            self.coordinator.controller, self.fixture.policy, self.fixture.catalog)
        self.coordinator.attach_sft_dataset("sft-action", dataset, dataset_sha256, source_path)
        training = self.coordinator._items(proposal["id"], "training")
        self.assertEqual(len(training), 1)
        self.assertEqual(training[0]["assignment"]["objective"], "sft")
        admitted = self.coordinator.admit_ready(1)[0]["job_id"]
        authenticated = self.coordinator.registry.authenticate(admitted)
        self.assertEqual(authenticated["source_receipt"], source)

    def test_failed_rollout_rejects_without_training_admission(self):
        proposal = self.fixture.model_proposal("failed-rollout")
        self.coordinator.register(proposal)
        self.coordinator.start_next("failed-action")
        self.start_baseline_serving(proposal["id"])
        rollout = self.coordinator.admit_ready(1)[0]["job_id"]
        assignment = self.coordinator._items(proposal["id"], "rollout")[0]["assignment"]
        self.finish_job(rollout, {**assignment, "candidate": "baseline",
                                  "contract_sha256": self.contract_hash,
                                  "status": "failed", "error_type": "WorkerError"})
        self.coordinator.advance()
        self.assertEqual(self.coordinator.workflow(proposal["id"])["state"],
                         "awaiting_baseline_serving_stop")
        self.stop_baseline_serving(proposal["id"])
        self.assertEqual(self.coordinator.workflow(proposal["id"])["state"], "rejected")
        self.assertEqual(self.coordinator._items(proposal["id"], "training"), [])

    def test_joint_queue_reuses_live_model_and_covers_full_factorial(self):
        baseline = self.coordinator._candidate("baseline")
        driver = {**copy.deepcopy(baseline), "id": "driver-candidate", "parent": "baseline",
                  "change_class": "driver", "hypothesis": "driver", "comparison": "driver-proposal",
                  "driver_sha256": "1" * 64, "patch_sha256": "2" * 64}
        model = {**copy.deepcopy(baseline), "id": "model-candidate", "parent": "baseline",
                 "change_class": "model", "hypothesis": "model", "comparison": "model-proposal",
                 "policy_sha256": "3" * 64}
        model["model"]["adapter_sha256"] = "4" * 64
        model["model"]["served_model"] = model["id"]
        self.coordinator.controller.register_candidate(driver)
        self.coordinator.controller.register_candidate(model)
        with self.coordinator.controller.ledger.transaction() as connection:
            connection.execute("UPDATE candidates SET state='nominated' WHERE id IN (?,?)", (driver["id"], model["id"]))
            connection.execute("INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,?)",
                               ("driver-proposal", "driver-action", "driver", "driver-proposal", "complete",
                                driver["id"], canonical({}).decode(), canonical({"decision": "nominate"}).decode()))
            connection.execute("INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,?)",
                               ("model-proposal", "model-action", "model", "model-proposal",
                                "qualified_serving_live", model["id"],
                                canonical({"serving_job": "serving-job"}).decode(),
                                canonical({"decision": "nominate"}).decode()))
        joint = self.coordinator.start_joint("driver-action", "model-action")
        items = self.coordinator._items(joint["proposal_id"], "factorial")
        self.assertEqual(len(items), 272)
        self.assertEqual({item["candidate"] for item in items},
                         {"baseline", driver["id"], model["id"], joint["candidate_id"]})
        self.assertEqual({item["assignment"]["comparison"] for item in items}, {joint["comparison"]})
        self.coordinator._set_workflow(
            joint["proposal_id"], state="qualified_serving_live", decision={"decision": "nominate_joint"})
        closed = self.coordinator.close_serving(joint["proposal_id"])
        self.assertEqual(closed["state"], "awaiting_serving_stop")
        self.assertEqual(self.coordinator.workflow("model-action")["state"], "awaiting_serving_stop")

    def test_private_confirmation_promotion_sealed_and_rollback_workflow(self):
        baseline = self.coordinator._candidate("baseline")
        candidate = {**copy.deepcopy(baseline), "id": "confirmed-driver", "parent": "baseline",
                     "change_class": "driver", "hypothesis": "private workflow fixture",
                     "comparison": "confirmed-driver-comparison", "driver_sha256": "1" * 64,
                     "patch_sha256": "2" * 64}
        self.coordinator.controller.register_candidate(candidate)
        with self.coordinator.controller.ledger.transaction() as connection:
            connection.execute("UPDATE candidates SET state='nominated' WHERE id=?", (candidate["id"],))
            connection.execute(
                "INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,?)",
                ("confirmed-driver-workflow", "confirmed-driver-action", "driver",
                 candidate["comparison"], "complete", candidate["id"], canonical({}).decode(),
                 canonical({"decision": "nominate"}).decode()),
            )
        workflow = self.coordinator.start_confirmation(
            "confirmed-driver-action", "confirmed-driver-lease", 31)
        self.assertEqual(workflow["state"], "starting_baseline_serving")
        self.start_baseline_serving(workflow["proposal_id"])
        workflow = self.coordinator.workflow(workflow["proposal_id"])
        self.assertEqual(workflow["state"], "confirming")
        items = self.coordinator._items(workflow["proposal_id"], "confirmation")
        self.assertEqual(len(items), 68)
        self.assertEqual({item["private_lease"] for item in items}, {"confirmed-driver-lease"})
        while True:
            pending = [item for item in self.coordinator._items(workflow["proposal_id"], "confirmation")
                       if item["state"] == "pending"]
            if not pending:
                break
            for admitted in self.coordinator.admit_ready(2):
                item = next(row for row in self.coordinator._items(workflow["proposal_id"], "confirmation")
                            if row["job_id"] == admitted["job_id"])
                result = {**item["assignment"], "candidate": item["candidate"],
                          "contract_sha256": self.contract_hash, "status": "complete",
                          "success": item["candidate"] == candidate["id"], "steps": 10,
                          "invalid_actions": 0, "seconds": 5.0}
                self.finish_job(item["job_id"], result)
            self.coordinator.sync()
        self.coordinator.advance("confirmed-driver-action")
        workflow = self.coordinator.workflow("confirmed-driver-action")
        self.assertEqual(workflow["state"], "awaiting_baseline_serving_stop")
        self.stop_baseline_serving(workflow["proposal_id"])
        workflow = self.coordinator.workflow("confirmed-driver-action")
        self.assertEqual(workflow["state"], "complete")
        self.assertEqual(workflow["decision"]["decision"], "confirmation_pass")
        self.coordinator.promote("confirmed-driver-action", "coordinator-confirmation-receipt")
        self.assertEqual(self.coordinator.controller.snapshot()["controller"]["champion"], candidate["id"])

        sealed = self.coordinator.start_sealed("sealed-final", 37)
        self.assertEqual(sealed["state"], "starting_baseline_serving")
        self.start_baseline_serving(sealed["proposal_id"])
        sealed = self.coordinator.workflow(sealed["proposal_id"])
        self.assertEqual(sealed["state"], "sealed_evaluating")
        while True:
            pending = [item for item in self.coordinator._items(sealed["proposal_id"], "sealed")
                       if item["state"] == "pending"]
            if not pending:
                break
            for admitted in self.coordinator.admit_ready(2):
                item = next(row for row in self.coordinator._items(sealed["proposal_id"], "sealed")
                            if row["job_id"] == admitted["job_id"])
                result = {**item["assignment"], "candidate": item["candidate"],
                          "contract_sha256": self.contract_hash, "status": "complete", "success": True,
                          "steps": 10, "invalid_actions": 0, "seconds": 5.0}
                self.finish_job(item["job_id"], result)
            self.coordinator.sync()
        self.coordinator.advance(sealed["proposal_id"])
        sealed = self.coordinator.workflow(sealed["proposal_id"])
        self.assertEqual(sealed["state"], "awaiting_baseline_serving_stop")
        self.stop_baseline_serving(sealed["proposal_id"])
        sealed = self.coordinator.workflow(sealed["proposal_id"])
        self.assertEqual(sealed["state"], "complete")
        self.assertEqual(sealed["decision"]["episodes"], 34)
        self.coordinator.rollback("post-promotion operational regression")
        self.assertEqual(self.coordinator.controller.snapshot()["controller"]["champion"], "baseline")

    def test_promoted_model_keeps_serving_owner_for_sealed_queue(self):
        baseline = self.coordinator._candidate("baseline")
        model = {**copy.deepcopy(baseline), "id": "sealed-model", "parent": "baseline",
                 "change_class": "model", "hypothesis": "sealed model fixture",
                 "comparison": "sealed-model-comparison", "policy_sha256": "3" * 64}
        model["model"]["adapter_sha256"] = "4" * 64
        model["model"]["served_model"] = model["id"]
        self.coordinator.controller.register_candidate(model)
        decision = {"decision": "confirmation_pass"}
        input_hash = digest(canonical(decision))
        deadline = int(time.time()) + 600
        self.coordinator.controller.ledger.reserve(
            "job:sealed-model-serving:modal_micro_usd", "modal_micro_usd", 100, deadline)
        specification = canonical({"candidate": "baseline", "kind": "serving", "assignment": {},
                                   "reservations": {"modal_micro_usd": 100}, "timeout_seconds": 600}).decode()
        envelope = canonical({"result": {"status": "complete", "candidate_id": model["id"]},
                              "artifact_sha256": "e" * 64}).decode()
        with self.coordinator.controller.ledger.transaction() as connection:
            connection.execute("UPDATE candidates SET state='confirmed' WHERE id=?", (model["id"],))
            connection.execute("INSERT INTO decisions VALUES (?,'confirmation',?,?)",
                               (model["id"], input_hash, canonical(decision).decode()))
            connection.execute(
                "INSERT INTO jobs(id,candidate,kind,resource_group,specification,deadline,state,provider_id,result) "
                "VALUES (?,?,?,?,?,?,'cleanup_pending',?,?)",
                ("sealed-model-serving", "baseline", "serving", "training", specification, deadline,
                 "modal:sealed-model-serving", envelope),
            )
            connection.execute(
                "INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,?)",
                ("sealed-model-workflow", "sealed-model-action", "model", model["comparison"],
                 "qualified_serving_live", model["id"],
                 canonical({"serving_job": "sealed-model-serving"}).decode(),
                 canonical(decision).decode()),
            )
        self.coordinator.promote("sealed-model-action", "sealed-model-confirmation")
        sealed = self.coordinator.start_sealed("sealed-model-final", 41)
        self.assertEqual(sealed["details"]["serving_owner"], "sealed-model-workflow")
        self.assertEqual(len(self.coordinator._items(sealed["proposal_id"], "sealed")), 34)


if __name__ == "__main__":
    unittest.main()
