"""Authenticated Modal transfer and execution for GameWorld GRPO updates."""

import asyncio
import json
from pathlib import Path
import time

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_grpo import verify_grpo_adapter, verify_parent_adapter, verify_rollout_dataset
from fps_bench.gameworld_research import load_policy
from fps_bench.gameworld_training import GameWorldTrainingRegistry
from fps_bench.modal_artifacts import ModalSandboxFiles
from fps_bench.modal_training import ModalSDKBackend, ModalTrainingLifecycle


MAX_REMOTE_FILE = 512 * 1024 * 1024


class GameWorldModalSDKBackend(ModalSDKBackend):
    async def run_worker(self, sandbox_id, plan, timeout):
        import modal

        worker = plan.get("worker", {})
        if worker.get("kind") != "gameworld-grpo" or worker.get("objective") != "grpo":
            raise ValueError("Modal launch is not an admitted GameWorld GRPO worker")
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        command = [
            "python", "-m", "scripts.gameworld_model_worker",
            "--objective", "grpo", "--dataset", "/dataset",
            "--dataset-sha256", worker["dataset_sha256"],
            "--policy-identity", "/input/policy.json",
            "--driver-sha256", worker["driver_sha256"],
            "--steps", str(worker["steps"]), "--campaign", plan["tags"]["campaign"],
            "--experiment", plan["tags"]["job"],
            "--evaluation-contract-sha256", plan["contract_sha256"], "--output", "/output",
        ]
        if worker["parent_adapter_sha256"] is not None:
            command.extend(["--parent-adapter", "/input/parent-adapter"])
        process = await sandbox.exec.aio(*command, workdir="/app", timeout=timeout, secrets=[])
        await process.wait.aio()
        return {"returncode": process.returncode, "artifacts_exported": False}


class GameWorldModalTrainingLifecycle(ModalTrainingLifecycle):
    def __init__(self, controller, backend=None, training_registry=None):
        super().__init__(controller, backend or GameWorldModalSDKBackend(),
                         training_registry or GameWorldTrainingRegistry(controller))


class GameWorldTrainingArtifacts:
    def __init__(self, lifecycle, files=None):
        self.lifecycle = lifecycle
        self.controller = lifecycle.controller
        self.registry = lifecycle.training_registry
        self.files = files
        self.policy, self.gameworld_context = load_policy()

    async def context(self, job_id):
        job, launch, plan = self.lifecycle.stored(job_id)
        if job["state"] not in ("running", "cleanup_pending") or not launch["sandbox_id"]:
            raise LedgerConflict("GameWorld artifact transfer requires an acknowledged live sandbox")
        observed = await asyncio.wait_for(self.lifecycle.backend.inspect(launch["sandbox_id"]), 30)
        self.lifecycle.acknowledge(job_id, observed)
        if observed.get("returncode") is not None:
            raise LedgerConflict("Export GameWorld artifacts before sandbox termination")
        return job, launch, plan, self.files or ModalSandboxFiles(launch["sandbox_id"])

    async def stage(self, job_id, parent_adapter=None):
        authenticated = self.registry.authenticate(job_id)
        job, launch, plan, files = await self.context(job_id)
        worker, manifest = plan["worker"], authenticated["manifest"]
        if (worker["dataset_sha256"] != authenticated["dataset_sha256"]
                or worker["policy_sha256"] != digest(canonical(manifest["policy"]))
                or worker["driver_sha256"] != manifest["driver_sha256"]):
            raise LedgerConflict("Modal worker plan differs from the authenticated rollout dataset")
        verify_rollout_dataset(authenticated["root"], authenticated["dataset_sha256"],
                               policy=self.policy, context=self.gameworld_context,
                               expected_policy=manifest["policy"],
                               expected_driver_sha256=manifest["driver_sha256"])
        parent = verify_parent_adapter(parent_adapter, worker["parent_adapter_sha256"], manifest["policy"])
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            if self.controller._job(connection, job_id)["state"] != "running":
                raise LedgerConflict("Training job is not accepting uploads")
            if connection.execute("SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("Never overwrite GameWorld inputs after worker dispatch")
            if connection.execute("SELECT 1 FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("GameWorld upload already attempted; reconcile or discard the sandbox")
            connection.execute("INSERT INTO modal_training_transfers VALUES (?,NULL,NULL)", (job_id,))
        async with asyncio.timeout(max(1, job["deadline"] - time.time() - 30)):
            await files.begin_stage(("/dataset", "/input"))
            root = Path(authenticated["root"])
            for name, expected in manifest["files"].items():
                data = (root / name).read_bytes()
                if digest(data) != expected:
                    raise ValueError("GameWorld rollout file changed before Modal staging")
                await files.write(name, data)
                if digest(await files.read("/dataset/" + name, MAX_REMOTE_FILE)) != expected:
                    raise ValueError("Staged GameWorld rollout file failed read-back validation")
            rollout_manifest = (root / "rollouts.json").read_bytes()
            await files.write("rollouts.json", rollout_manifest)
            await files.write("policy.json", canonical(manifest["policy"]), "/input")
            if parent is not None:
                parent_manifest = json.loads((parent / "adapter-manifest.json").read_bytes())
                await files.write("parent-adapter/adapter-manifest.json",
                                  (parent / "adapter-manifest.json").read_bytes(), "/input")
                for name in parent_manifest["files"]:
                    await files.write("parent-adapter/" + name, (parent / name).read_bytes(), "/input")
        return await self.reconcile_stage(job_id)

    async def reconcile_stage(self, job_id):
        job, launch, plan, files = await self.context(job_id)
        worker = plan["worker"]
        manifest_data = await files.read("/dataset/rollouts.json", MAX_REMOTE_FILE)
        if digest(manifest_data) != worker["dataset_sha256"]:
            raise ValueError("Staged GameWorld rollout manifest differs from admission")
        manifest = json.loads(manifest_data)
        if digest(await files.read("/input/policy.json")) != worker["policy_sha256"]:
            raise ValueError("Staged GameWorld policy identity differs from admission")
        for name, expected in manifest["files"].items():
            if digest(await files.read("/dataset/" + name, MAX_REMOTE_FILE)) != expected:
                raise ValueError("Staged GameWorld dataset is incomplete or corrupt")
        if worker["parent_adapter_sha256"] is not None:
            parent_manifest = await files.read("/input/parent-adapter/adapter-manifest.json")
            if digest(parent_manifest) != worker["parent_adapter_sha256"]:
                raise ValueError("Staged parent adapter identity differs from admission")
        receipt = {"sandbox_id": launch["sandbox_id"], "dataset_sha256": worker["dataset_sha256"],
                   "policy_sha256": worker["policy_sha256"],
                   "parent_adapter_sha256": worker["parent_adapter_sha256"]}
        with self.controller.ledger.transaction() as connection:
            transfer = connection.execute(
                "SELECT * FROM modal_training_transfers WHERE job_id=?", (job_id,)
            ).fetchone()
            if transfer is None or self.controller._job(connection, job_id)["state"] != "running":
                raise LedgerConflict("No active durable GameWorld upload attempt exists")
            connection.execute("UPDATE modal_training_transfers SET staging_receipt=? WHERE job_id=?",
                               (canonical(receipt).decode(), job_id))
        return receipt

    def reconcile_export(self, job_id):
        _, _, plan = self.lifecycle.stored(job_id)
        with self.controller.ledger.transaction() as connection:
            row = connection.execute(
                "SELECT export_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)
            ).fetchone()
        if not row or not row["export_receipt"]:
            raise LedgerConflict("No durable local GameWorld export receipt")
        receipt = json.loads(row["export_receipt"])
        root = Path(receipt["output"])
        if digest((root / "bundle.json").read_bytes()) != digest(canonical(receipt)):
            raise ValueError("GameWorld export bundle receipt changed")
        for name, expected in receipt["files"].items():
            path = root / name
            if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
                raise ValueError("GameWorld exported artifact changed")
        policy_identity = json.loads((root / "policy.json").read_bytes())
        verify_grpo_adapter(root / "adapter", receipt["adapter_manifest_sha256"], policy_identity,
                            plan["worker"]["dataset_sha256"], plan["worker"]["driver_sha256"])
        result = json.loads((root / "result.json").read_bytes())
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        return receipt

    async def export(self, job_id, output):
        with self.controller.ledger.transaction() as connection:
            previous = connection.execute(
                "SELECT export_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)
            ).fetchone()
        if previous and previous["export_receipt"]:
            return self.reconcile_export(job_id)
        job, launch, plan, files = await self.context(job_id)
        with self.controller.ledger.transaction() as connection:
            transfer = connection.execute(
                "SELECT * FROM modal_training_transfers WHERE job_id=?", (job_id,)
            ).fetchone()
            attempted = connection.execute(
                "SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)
            ).fetchone()
            if not transfer or not transfer["staging_receipt"] or not attempted:
                raise LedgerConflict("Verified staging and one worker attempt are required before export")
        completion_data = await files.read("/output/worker-finished.json")
        completion = json.loads(completion_data)
        worker = plan["worker"]
        expected_completion = {"job_id": job_id, "campaign": plan["tags"]["campaign"],
                               "experiment": job_id, "objective": worker["objective"],
                               "contract_sha256": plan["contract_sha256"],
                               "dataset_sha256": worker["dataset_sha256"]}
        if any(completion.get(key) != value for key, value in expected_completion.items()):
            raise ValueError("GameWorld worker completion belongs to different admitted work")
        result_data = await files.read("/output/training/result.json", MAX_REMOTE_FILE)
        if digest(result_data) != completion.get("result_sha256"):
            raise ValueError("GameWorld training result differs from its completion receipt")
        result = json.loads(result_data)
        if (result.get("status") != "complete" or result.get("objective") != "grpo"
                or result.get("steps") != worker["steps"]
                or result.get("rollout_dataset_sha256") != worker["dataset_sha256"]
                or result.get("adapter_manifest_sha256") != completion.get("adapter_manifest_sha256")):
            raise ValueError("GameWorld training result differs from the admitted GRPO update")
        adapter_manifest_data = await files.read("/output/training/adapter/adapter-manifest.json")
        if digest(adapter_manifest_data) != result["adapter_manifest_sha256"]:
            raise ValueError("GameWorld adapter identity differs from the training result")
        adapter_manifest = json.loads(adapter_manifest_data)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        (output / "adapter").mkdir()
        bundle = {"result.json": result_data, "worker-finished.json": completion_data,
                  "adapter/adapter-manifest.json": adapter_manifest_data,
                  "policy.json": canonical(json.loads(await files.read("/input/policy.json")))}
        for name, expected in adapter_manifest["files"].items():
            if Path(name).name != name:
                raise ValueError("Unsafe GameWorld adapter file inventory")
            data = await files.read("/output/training/adapter/" + name, MAX_REMOTE_FILE)
            if digest(data) != expected:
                raise ValueError("Remote GameWorld adapter file digest mismatch")
            bundle["adapter/" + name] = data
        for name, remote in (("loss.jsonl", "/output/training/loss.jsonl"),
                             ("telemetry.sqlite", "/output/telemetry.sqlite")):
            bundle[name] = await files.read(remote, MAX_REMOTE_FILE)
        for name, data in bundle.items():
            exclusive_write(output / name, data, 0o400)
        policy_identity = json.loads(bundle["policy.json"])
        verify_grpo_adapter(output / "adapter", result["adapter_manifest_sha256"], policy_identity,
                            worker["dataset_sha256"], worker["driver_sha256"])
        receipt = {"job_id": job_id, "sandbox_id": launch["sandbox_id"], "output": str(output.resolve()),
                   "dataset_sha256": worker["dataset_sha256"],
                   "adapter_manifest_sha256": result["adapter_manifest_sha256"],
                   "files": {name: digest(data) for name, data in bundle.items()}}
        exclusive_write(output / "bundle.json", canonical(receipt), 0o400)
        with self.controller.ledger.transaction() as connection:
            changed = connection.execute(
                "UPDATE modal_training_transfers SET export_receipt=? WHERE job_id=? AND export_receipt IS NULL",
                (canonical(receipt).decode(), job_id),
            ).rowcount
            if changed != 1:
                raise LedgerConflict("Another GameWorld export already owns this job receipt")
        return self.reconcile_export(job_id)
