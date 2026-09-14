"""Offline integration checks for trusted GameWorld Fleet worker execution."""

import asyncio
import copy
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

import scripts.campaign_controller_check as fixtures
from fps_bench.campaign_controller import CampaignController
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_fleet import GameWorldFleetExecutor, extract_output_archive
from fps_bench.gameworld_grpo import reward_components
from fps_bench.gameworld_research import load_policy
from fps_bench.gameworld_training import GameWorldTrainingRegistry


class FakeLifecycle:
    def __init__(self, controller, pool="test-pool"):
        self.controller, self.pool = controller, pool
        self.releases = 0

    def job(self, job_id):
        with self.controller.ledger.transaction() as connection:
            return dict(self.controller._job(connection, job_id))

    async def acquire(self, job_id):
        job = self.job(job_id)
        if job["state"] == "reserved":
            self.controller.begin_dispatch(job_id)
            self.controller.provider_started(job_id, "fleet:test-pool/claim")
        return object()

    async def release(self, job_id):
        job = self.job(job_id)
        if job["state"] == "running":
            self.controller.request_cleanup(job_id)
        self.controller.provider_cleanup_confirmed(job_id, "fleet-release:" + job_id)
        self.releases += 1
        return {"claim_absent": True}


class FakeBackend:
    def __init__(self, fixture):
        self.fixture = Path(fixture)
        self.runs = 0
        self.cleaned = 0

    async def stage(self, sandbox, remote_root, files):
        self.staged = files

    async def run(self, sandbox, remote_root, command, timeout):
        self.runs += 1

    async def collect(self, sandbox, remote_root, output, maximum):
        shutil.copytree(self.fixture, output)
        return Path(output)

    async def cleanup(self, sandbox, remote_root):
        self.cleaned += 1


class FleetExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def run_async(self, action):
        return asyncio.run(action)

    def test_driver_candidate_is_exported_registered_and_replay_safe(self):
        source = fixtures.GameWorldControllerTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        proposal = {"id": "driver-input", "track": "driver", "hypothesis": "fix measured input failure"}
        proposal_path = self.home / "proposal.json"
        proposal_path.write_bytes(canonical(proposal))
        patch_path = self.home / "candidate.patch"
        patch_path.write_bytes(b"synthetic patch")
        assignment = {"pool": "test-pool", "operation": "driver-candidate", "proposal_id": proposal["id"],
                      "proposal_sha256": digest(proposal_path.read_bytes()),
                      "patch_sha256": digest(patch_path.read_bytes())}
        source.controller.admit_job("driver-build", "baseline", "driver_build", assignment, {}, 600)
        fixture = self.home / "driver-fixture"
        fixture.mkdir()
        binary = b"new-driver-binary"
        driver_sha = digest(binary)
        manifest = {"binary": {"path": "cua-driver", "sha256": driver_sha}}
        result = {"status": "complete", "candidate_id": "driver-input-candidate",
                  "proposal_sha256": assignment["proposal_sha256"], "patch_sha256": assignment["patch_sha256"],
                  "driver_sha256": driver_sha, "manifest_sha256": digest(canonical(manifest))}
        (fixture / "provider-result.json").write_bytes(canonical({"returncode": 0}))
        (fixture / "driver-manifest.json").write_bytes(canonical(manifest))
        (fixture / "result.json").write_bytes(canonical(result))
        (fixture / "cua-driver").write_bytes(binary)
        backend = FakeBackend(fixture)
        lifecycle = FakeLifecycle(source.controller)
        executor = GameWorldFleetExecutor(source.controller, lifecycle, self.home / "artifacts", backend)
        first = self.run_async(executor.driver_candidate("driver-build", proposal_path, patch_path))
        second = self.run_async(executor.driver_candidate("driver-build", proposal_path, patch_path))
        self.assertEqual(first["candidate"], second["candidate"])
        self.assertEqual(backend.runs, 1)
        self.assertEqual(lifecycle.releases, 2)
        candidate = next(row for row in source.controller.snapshot()["candidates"]
                         if row["id"] == "driver-input-candidate")
        self.assertEqual(candidate["state"], "materialized")

    def test_rollout_dataset_is_verified_before_controller_result(self):
        source = fixtures.GameWorldControllerTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        policy, context = load_policy()
        endpoint = "https://candidate.example/v1"
        identity = {"base_model": policy["model"]["base_model"],
                    "base_revision": policy["model"]["base_revision"], "adapter_sha256": None,
                    "served_model": "qwen-baseline",
                    "deployment": {"app_id": "ap-Test", "function_id": "fu-Test", "image_id": "im-Test",
                                   "endpoint_sha256": digest(endpoint.encode())},
                    "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                                   "response_format": "unconstrained-json-text"}}
        identity_path = self.home / "policy.json"
        identity_path.write_bytes(canonical(identity))
        contract = copy.deepcopy(source.contract)
        train_id = context["splits"]["train"][0]
        train_assignment = context["assignments"][train_id]
        contract["public_splits"]["train"]["tasks"] = [{**train_assignment, "seed": 42}]
        contract_path = self.home / "rollout-contract.json"
        contract_path.write_bytes(canonical(contract))
        contract_hash = digest(canonical(contract))
        controller = CampaignController(self.home / "rollout.sqlite", contract_path, contract_hash)
        controller.initialize("rollout-controller")
        baseline = copy.deepcopy(source.baseline)
        baseline["contract_hash"] = contract_hash
        baseline["policy_sha256"] = digest(identity_path.read_bytes())
        controller.register_candidate(baseline)
        train = contract["public_splits"]["train"]["tasks"][0]
        assignment = {"split": "train", "task_id": train["id"], "game": train["game"],
                      "task": train["task"], "seed": train["seed"], "repeat": 0,
                      "group_id": "group-one", "members": 2, "max_steps": 4,
                      "policy_sha256": baseline["policy_sha256"],
                      "driver_sha256": baseline["driver_sha256"]}
        controller.admit_job("rollout-one", "baseline", "rollout", assignment,
                             {"modal_micro_usd": 100}, 600)
        fixture = self.home / "rollout-fixture"
        dataset = fixture / "dataset"
        (dataset / "images").mkdir(parents=True)
        (dataset / "trajectories").mkdir()
        files, members = {}, []
        for index, progress in enumerate((0.0, 0.5)):
            image = f"image-{index}".encode()
            image_name = f"images/{digest(image)}.png"
            (dataset / image_name).write_bytes(image)
            files[image_name] = digest(image)
            response = '{"tool_name":"wait","arguments":{}}'
            row = {"step": 0, "messages": [{"role": "system", "content": "play"},
                   {"role": "user", "content": [{"type": "text", "text": "act"},
                                                  {"type": "image", "image": image_name}]}],
                   "response": response, "observation": image_name, "observation_sha256": digest(image),
                   "action": {"tool_name": "wait", "arguments": {}}, "invalid_action": None}
            trajectory = f"trajectories/trajectory-{index}.jsonl"
            (dataset / trajectory).write_bytes(canonical(row))
            files[trajectory] = digest(canonical(row))
            summary = {"steps": 1, "success": False, "progress": progress,
                       "invalid_actions": 0, "driver_errors": 0}
            rewards = reward_components(summary, policy["model"]["grpo"])
            members.append({"id": f"trajectory-{index}", "trajectory": trajectory,
                            "trajectory_sha256": files[trajectory], **summary,
                            "reward_components": rewards, "reward": rewards["total"]})
        manifest = {"schema_version": 1, "purpose": "gameworld-interactive-grpo-v1",
                    "catalog_manifest_sha256": context["catalog_manifest_sha256"], "policy": identity,
                    "driver_sha256": baseline["driver_sha256"], "reward": policy["model"]["grpo"],
                    "groups": [{"id": "group-one", "game": train["game"], "task": train["task"],
                                "seed": train["seed"], "initial_state_sha256": "f" * 64, "members": members}],
                    "files": files}
        dataset_hash = digest(canonical(manifest))
        (dataset / "rollouts.json").write_bytes(canonical(manifest))
        (fixture / "provider-result.json").write_bytes(canonical({"returncode": 0}))
        (fixture / "result.json").write_bytes(canonical({"dataset_sha256": dataset_hash,
                                                          "usage": {"prompt_tokens": 20, "completion_tokens": 4},
                                                          "seconds": 2.0}))
        executor = GameWorldFleetExecutor(
            controller, FakeLifecycle(controller), self.home / "rollout-artifacts", FakeBackend(fixture))
        result = self.run_async(executor.rollout(
            "rollout-one", identity_path, {"QWEN_BASE_URL": endpoint, "QWEN_API_KEY": "x" * 32}))
        self.assertEqual(result["result"]["dataset_sha256"], dataset_hash)
        self.assertEqual(controller.snapshot()["jobs"][0]["state"], "billing_pending")
        registry = GameWorldTrainingRegistry(controller)
        registry.register_rollout("rollout-one", result["artifacts"]["root"], result["artifacts"])
        combined = registry.export(["rollout-one"], self.home / "combined-rollouts")
        training = {"split": "train", "tasks": [train["id"]], "dataset_sha256": combined["dataset_sha256"],
                    "objective": "grpo", "policy_sha256": baseline["policy_sha256"],
                    "driver_sha256": baseline["driver_sha256"], "steps": 2}
        controller.admit_job("training-one", "baseline", "training", training,
                             {"modal_micro_usd": 100}, 600)
        self.assertEqual(registry.authenticate("training-one")["jobs"], ["rollout-one"])

    def test_archive_rejects_symlinks_and_traversal(self):
        for name, kind in (("../escape", "file"), ("output/link", "symlink")):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                member = tarfile.TarInfo(name)
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/etc/passwd"
                    archive.addfile(member)
                else:
                    payload = b"bad"
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            with self.assertRaises(ValueError):
                extract_output_archive(data.getvalue(), self.home / f"unsafe-{kind}", 1024)

    def test_candidate_evaluation_is_bound_to_task_model_and_driver(self):
        source = fixtures.GameWorldControllerTests()
        source.setUp()
        self.addCleanup(source.doCleanups)
        policy, _ = load_policy()
        driver = b"candidate-driver"
        driver_path = self.home / "driver"
        driver_path.write_bytes(driver)
        endpoint = "https://evaluation.example/v1"
        identity = {"base_model": policy["model"]["base_model"],
                    "base_revision": policy["model"]["base_revision"], "adapter_sha256": None,
                    "served_model": "qwen-baseline",
                    "deployment": {"app_id": "ap-Test", "function_id": "fu-Test", "image_id": "im-Test",
                                   "endpoint_sha256": digest(endpoint.encode())},
                    "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                                   "response_format": "unconstrained-json-text"}}
        policy_path = self.home / "evaluation-policy.json"
        policy_path.write_bytes(canonical(identity))
        contract = copy.deepcopy(source.contract)
        contract["episode_template"].update(model=identity["base_model"], revision=identity["base_revision"],
                                            served_model=identity["served_model"])
        contract["spec"]["baseline_driver_sha256"] = digest(driver)
        contract_path = self.home / "evaluation-contract.json"
        contract_path.write_bytes(canonical(contract))
        contract_hash = digest(canonical(contract))
        controller = CampaignController(self.home / "evaluation.sqlite", contract_path, contract_hash)
        controller.initialize("evaluation-controller")
        candidate = copy.deepcopy(source.baseline)
        candidate.update(contract_hash=contract_hash, driver_sha256=digest(driver),
                         policy_sha256=digest(policy_path.read_bytes()))
        candidate["model"] = {"base_model": identity["base_model"], "base_revision": identity["base_revision"],
                              "processor_revision": identity["base_revision"], "adapter_sha256": None,
                              "served_model": identity["served_model"]}
        controller.register_candidate(candidate)
        task = contract["public_splits"]["development"]["tasks"][0]
        assignment = {"split": "development", "task_id": task["id"], "game": task["game"],
                      "task": task["task"], "seed": task["seed"], "repeat": 0,
                      "comparison": "evaluation-one"}
        controller.admit_job("evaluation-one", "baseline", "evaluation", assignment,
                             {"modal_micro_usd": 100}, 600)
        fixture = self.home / "evaluation-fixture"
        fixture.mkdir()
        summary = {"status": "complete", "success": False, "steps": 1, "invalid_actions": 0,
                   "driver_errors": 0, "progress": 0.25, "seconds": 1.0,
                   "usage": {"prompt_tokens": 10, "completion_tokens": 2}, "evaluation": {}}
        trajectory = canonical({"step": 0})
        (fixture / "summary.json").write_bytes(canonical(summary))
        (fixture / "trajectory.jsonl").write_bytes(trajectory)
        files = {"summary.json": digest(canonical(summary)), "trajectory.jsonl": digest(trajectory)}
        manifest = {"schema_version": 1, "contract_sha256": contract_hash, "assignment": assignment,
                    "candidate_sha256": digest(canonical(candidate)),
                    "policy_sha256": digest(canonical(identity)), "driver_sha256": digest(driver),
                    "files": files}
        (fixture / "manifest.json").write_bytes(canonical(manifest))
        result = {**assignment, "candidate": "baseline", "contract_sha256": contract_hash,
                  "status": "complete", "success": False, "steps": 1, "invalid_actions": 0,
                  "driver_errors": 0, "execution_status": "executed", "progress": 0.25,
                  "seconds": 1.0, "usage": summary["usage"],
                  "manifest_sha256": digest(canonical(manifest)), "execution_statuses": ["executed"]}
        (fixture / "result.json").write_bytes(canonical(result))
        (fixture / "provider-result.json").write_bytes(canonical({"returncode": 0}))
        executor = GameWorldFleetExecutor(
            controller, FakeLifecycle(controller), self.home / "evaluation-artifacts", FakeBackend(fixture))
        completed = self.run_async(executor.evaluate(
            "evaluation-one", policy_path,
            {"QWEN_BASE_URL": endpoint, "QWEN_API_KEY": "x" * 32}, driver_path))
        self.assertEqual(completed["result"]["task_id"], task["id"])
        self.assertEqual(controller.snapshot()["jobs"][0]["state"], "billing_pending")


if __name__ == "__main__":
    unittest.main()
