"""Bounded training data transfer and checkpoint export for trusted Modal sandboxes."""

import asyncio
import json
from pathlib import Path, PurePosixPath
import time

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION, verify_adapter
from fps_bench.training_data import checked_bytes, MAX_FILE_BYTES, verify_dataset


READ_FILE = """import os, pathlib, sys
path = pathlib.Path(sys.argv[1])
if any(parent.is_symlink() for parent in [path, *path.parents]):
    raise ValueError('symlink artifact rejected')
with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as handle:
    sys.stdout.buffer.write(handle.read(int(sys.argv[2]) + 1))
"""


class ModalSandboxFiles:
    def __init__(self, sandbox_id):
        self.sandbox_id = sandbox_id

    async def begin_stage(self):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(self.sandbox_id)
        process = await sandbox.exec.aio("python", "-c", "import os; os.mkdir('/dataset')", timeout=30)
        if await process.wait.aio() != 0:
            raise ValueError("Dataset destination already exists or cannot be created")

    async def write(self, name, data):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(self.sandbox_id)
        await sandbox.filesystem.write_bytes.aio(data, "/dataset/" + name)

    async def read(self, path, limit=MAX_FILE_BYTES):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(self.sandbox_id)
        process = await sandbox.exec.aio("python", "-c", READ_FILE, path, str(limit), text=False, timeout=30)
        data, code = await asyncio.gather(process.stdout.read.aio(), process.wait.aio())
        if code != 0 or len(data) > limit:
            raise ValueError("Remote artifact missing, oversized or unsafe")
        return data


class TrainingArtifacts:
    def __init__(self, lifecycle, files=None):
        self.lifecycle = lifecycle
        self.controller = lifecycle.controller
        self.files = files

    async def context(self, job_id):
        job, launch, plan = self.lifecycle.stored(job_id)
        if job["state"] not in ("running", "cleanup_pending") or not launch["sandbox_id"]:
            raise LedgerConflict("Artifact transfer requires an acknowledged live sandbox")
        observed = await asyncio.wait_for(self.lifecycle.backend.inspect(launch["sandbox_id"]), 30)
        self.lifecycle.acknowledge(job_id, observed)
        if observed.get("returncode") is not None:
            raise LedgerConflict("Export before sandbox termination")
        files = self.files or ModalSandboxFiles(launch["sandbox_id"])
        return job, launch, plan, files

    async def stage(self, job_id, root):
        job, launch, plan, files = await self.context(job_id)
        assignment = plan["assignment"]
        manifest, _ = verify_dataset(root, assignment["dataset_sha256"], plan["contract_sha256"])
        seeds = [episode["seed"] for episode in manifest["episodes"]]
        if any(type(seed) is not int for seed in seeds) or sorted(seeds) != sorted(assignment["seeds"]):
            raise ValueError("Dataset seed inventory differs from the admitted job")
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            if self.controller._job(connection, job_id)["state"] != "running":
                raise LedgerConflict("Job is not accepting uploads")
            if connection.execute("SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("Never overwrite a dataset after worker dispatch")
            if connection.execute("SELECT 1 FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("Upload already attempted; reconcile read-only or discard this sandbox")
            connection.execute("INSERT INTO modal_training_transfers VALUES (?,NULL,NULL)", (job_id,))
        async with asyncio.timeout(max(1, job["deadline"] - time.time() - 30)):
            await files.begin_stage()
            for name, expected in manifest["files"].items():
                data = checked_bytes(root, name, expected)
                await files.write(name, data)
                if digest(await files.read("/dataset/" + name)) != expected:
                    raise ValueError("Uploaded training file failed read-back validation")
            data = checked_bytes(root, "dataset.json", assignment["dataset_sha256"])
            await files.write("dataset.json", data)
        return await self.reconcile_stage(job_id)

    async def reconcile_stage(self, job_id):
        job, launch, plan, files = await self.context(job_id)
        async with asyncio.timeout(max(1, job["deadline"] - time.time() - 30)):
            data = await files.read("/dataset/dataset.json")
            if digest(data) != plan["assignment"]["dataset_sha256"]:
                raise ValueError("Staged dataset manifest differs from admission")
            manifest = json.loads(data)
            for name, expected in manifest["files"].items():
                if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                    raise ValueError("Unsafe dataset inventory")
                if digest(await files.read("/dataset/" + name)) != expected:
                    raise ValueError("Staged dataset is incomplete or corrupt")
        receipt = {"sandbox_id": launch["sandbox_id"], "dataset_sha256": digest(data)}
        with self.controller.ledger.transaction() as connection:
            transfer = connection.execute("SELECT * FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone()
            if transfer is None:
                raise LedgerConflict("No durable upload attempt exists")
            if self.controller._job(connection, job_id)["state"] != "running":
                raise LedgerConflict("Job stopped before staging completed")
            connection.execute("UPDATE modal_training_transfers SET staging_receipt=? WHERE job_id=?",
                               (canonical(receipt).decode(), job_id))
        return receipt

    def reconcile_export(self, job_id):
        _, _, plan = self.lifecycle.stored(job_id)
        with self.controller.ledger.transaction() as connection:
            row = connection.execute("SELECT export_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone()
        if not row or not row["export_receipt"]:
            raise LedgerConflict("No durable local export receipt")
        receipt = json.loads(row["export_receipt"])
        root = Path(receipt["output"])
        checked_bytes(root, "bundle.json", digest(canonical(receipt)))
        for name, expected in receipt["files"].items():
            checked_bytes(root, name, expected)
        verify_adapter(root / "adapter", receipt["adapter_manifest_sha256"], BASE_MODEL, BASE_REVISION,
                       plan["assignment"]["dataset_sha256"], plan["contract_sha256"])
        result = json.loads(checked_bytes(root, "result.json", receipt["files"]["result.json"]))
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        return receipt

    async def export(self, job_id, output):
        with self.controller.ledger.transaction() as connection:
            previous = connection.execute("SELECT export_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone()
        if previous and previous["export_receipt"]:
            return self.reconcile_export(job_id)
        job, launch, plan, files = await self.context(job_id)
        with self.controller.ledger.transaction() as connection:
            transfer = connection.execute("SELECT * FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone()
            if not transfer or not transfer["staging_receipt"]:
                raise LedgerConflict("No verified staged input")
            if not connection.execute("SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("No worker dispatch attempt exists")
            if transfer["export_receipt"]:
                raise LedgerConflict("Export already recorded; use its immutable local bundle")
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        async with asyncio.timeout(max(1, job["deadline"] - time.time() - 5)):
            completion_data = await files.read("/output/worker-finished.json")
            completed = json.loads(completion_data)
            if (completed.get("job_id") != job_id or completed.get("campaign") != plan["tags"]["campaign"]
                    or completed.get("dataset_sha256") != plan["assignment"]["dataset_sha256"]
                    or completed.get("contract_sha256") != plan["contract_sha256"]):
                raise ValueError("Worker completion belongs to a different input")
            result_data = await files.read("/output/training/result.json")
            if digest(result_data) != completed.get("result_sha256"):
                raise ValueError("Training result differs from the completion receipt")
            result = json.loads(result_data)
            if result.get("status") != "complete" or type(result.get("steps")) is not int or result["steps"] != 1:
                raise ValueError("Compatibility worker did not complete exactly one update")
            adapter_data = await files.read("/output/training/adapter/adapter-manifest.json")
            if digest(adapter_data) != result.get("adapter_manifest_sha256"):
                raise ValueError("Adapter identity differs from completed training")
            adapter_manifest = json.loads(adapter_data)
            if set(adapter_manifest["files"]) - {"adapter_config.json", "adapter_model.safetensors", "README.md"}:
                raise ValueError("Unexpected adapter file inventory")
            (output / "adapter").mkdir()
            bundle = {"result.json": result_data, "adapter/adapter-manifest.json": adapter_data,
                      "worker-finished.json": completion_data}
            for name, expected in adapter_manifest["files"].items():
                data = await files.read("/output/training/adapter/" + name)
                if digest(data) != expected:
                    raise ValueError("Remote adapter file digest mismatch")
                bundle["adapter/" + name] = data
            for name, data in bundle.items():
                exclusive_write(output / name, data, 0o400)
            verify_adapter(output / "adapter", result["adapter_manifest_sha256"], BASE_MODEL, BASE_REVISION,
                           plan["assignment"]["dataset_sha256"], plan["contract_sha256"])
            for name, remote in (("loss.jsonl", "/output/training/loss.jsonl"), ("telemetry.sqlite", "/output/telemetry.sqlite")):
                bundle[name] = await files.read(remote)
                exclusive_write(output / name, bundle[name], 0o400)
        receipt = {"job_id": job_id, "sandbox_id": launch["sandbox_id"], "output": str(output.resolve()),
                   "dataset_sha256": plan["assignment"]["dataset_sha256"],
                   "adapter_manifest_sha256": result["adapter_manifest_sha256"],
                   "files": {name: digest(data) for name, data in bundle.items()}}
        exclusive_write(output / "bundle.json", canonical(receipt), 0o400)
        with self.controller.ledger.transaction() as connection:
            changed = connection.execute("UPDATE modal_training_transfers SET export_receipt=? WHERE job_id=? AND export_receipt IS NULL",
                                         (canonical(receipt).decode(), job_id)).rowcount
            if changed != 1:
                raise LedgerConflict("Another export already owns this job receipt")
        return self.reconcile_export(job_id)
