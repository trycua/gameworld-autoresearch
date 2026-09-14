"""Trusted Modal training sandbox lifecycle; live billing settlement remains separate."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
import re
import time

from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_environment import inspect_environment, validate_environment


GPU = "L40S"
CPU = 4
MEMORY_MIB = 32768


def compute_reservation(rates, seconds, checked_at):
    if type(seconds) is not int or not 60 <= seconds <= 1800:
        raise ValueError("Training sandbox lifetime must be 60..1800 seconds")
    age = time.time() - datetime.fromisoformat(checked_at.replace("Z", "+00:00")).timestamp()
    if not 0 <= age <= 300:
        raise ValueError("Modal price snapshot is stale or future-dated")
    values = []
    for key in ("gpu_hour_cost_l40s", "cpu_hour_cost_sandbox", "mem_gib_hour_cost_sandbox"):
        value = Decimal(rates[key])
        if not value.is_finite() or value <= 0 or value > 100:
            raise ValueError("Invalid Modal compute rate")
        values.append(value)
    hourly = values[0] + CPU * values[1] + (MEMORY_MIB // 1024) * values[2]
    estimate = int((hourly * seconds / 3600 * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    return {"compute_estimate_micro_usd": estimate, "required_reservation_micro_usd": 2 * estimate + 1_000_000,
            "rates": {key: rates[key] for key in ("gpu_hour_cost_l40s", "cpu_hour_cost_sandbox", "mem_gib_hour_cost_sandbox")},
            "checked_at": checked_at, "seconds": seconds,
            "limitation": "Compute-based reserve with 100% margin plus $1; not an independently verified all-in billing bound"}


def sandbox_options(plan):
    return {"name": plan["name"], "tags": plan["tags"], "gpu": GPU, "cpu": (CPU, CPU),
            "memory": (MEMORY_MIB, MEMORY_MIB), "timeout": plan["seconds"], "block_network": True,
            "secrets": [], "volumes": {}, "network_file_systems": {}, "include_oidc_identity_token": False,
            "env": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}}


class ModalSDKBackend:
    async def environment(self, workspace, name):
        return await inspect_environment(workspace, name)

    async def prices(self, workspace_name):
        import modal
        workspace = await modal.Workspace.from_context().hydrate.aio()
        if workspace.name != workspace_name:
            raise ValueError("Modal workspace mismatch")
        rates = await workspace.billing.rates.aio()
        return {"rates": {key: str(value) for key, value in rates.items()},
                "checked_at": datetime.now(timezone.utc).isoformat()}

    async def lookup(self, app, environment, name):
        import modal
        try:
            sandbox = await modal.Sandbox.from_name.aio(app, name, environment_name=environment)
        except modal.exception.NotFoundError:
            return None
        return {"id": sandbox.object_id, "tags": await sandbox.get_tags.aio()}

    async def inspect(self, sandbox_id):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        return {"id": sandbox.object_id, "tags": await sandbox.get_tags.aio(), "returncode": await sandbox.poll.aio()}

    async def create(self, plan):
        import modal
        validate_environment(await self.environment(plan["workspace"], plan["environment"]),
                             plan["environment"], plan["environment_id"])
        current = await self.prices(plan["workspace"])
        refreshed = compute_reservation(current["rates"], plan["seconds"], current["checked_at"])
        if refreshed["required_reservation_micro_usd"] > plan["quote"]["required_reservation_micro_usd"]:
            raise BudgetRefused("Modal rates increased after preparation; keep the hold and reconcile dispatch")
        app = await modal.App.lookup.aio(plan["app"], environment_name=plan["environment"], create_if_missing=False)
        image = await modal.Image.from_id.aio(plan["image_id"])
        sandbox = await modal.Sandbox.create.aio("/bin/sleep", str(plan["seconds"]),
                                                app=app, image=image, **sandbox_options(plan))
        return {"id": sandbox.object_id, "tags": await sandbox.get_tags.aio()}

    async def run_worker(self, sandbox_id, plan, timeout):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        process = await sandbox.exec.aio(
            "python", "-m", "scripts.qwen_lora_worker",
            "--dataset-sha256", plan["assignment"]["dataset_sha256"],
            "--contract-sha256", plan["contract_sha256"],
            "--campaign", plan["tags"]["campaign"], "--experiment", plan["tags"]["job"],
            workdir="/app", timeout=timeout, secrets=[])
        await process.wait.aio()
        return {"returncode": process.returncode, "artifacts_exported": False}

    async def terminate(self, sandbox_id):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        await sandbox.terminate.aio(wait=True)


class ModalTrainingLifecycle:
    def __init__(self, controller, backend=None):
        self.controller = controller
        self.backend = backend or ModalSDKBackend()
        with controller.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS modal_training_transfers "
                               "(job_id TEXT PRIMARY KEY REFERENCES jobs(id), staging_receipt TEXT, export_receipt TEXT)")
            connection.execute("CREATE TABLE IF NOT EXISTS modal_training_attempts "
                               "(job_id TEXT PRIMARY KEY REFERENCES jobs(id), started_at INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS modal_training_launches "
                               "(job_id TEXT PRIMARY KEY REFERENCES jobs(id), plan TEXT NOT NULL, "
                               "sandbox_id TEXT, termination_receipt TEXT)")

    def stored(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
            launch = connection.execute("SELECT * FROM modal_training_launches WHERE job_id=?", (job_id,)).fetchone()
            if not launch:
                raise LedgerConflict("No prepared Modal launch")
            return job, dict(launch), json.loads(launch["plan"])

    async def prepare(self, job_id, *, workspace, app, environment, environment_id, image_id):
        if not re.fullmatch(r"im-[A-Za-z0-9]+", image_id):
            raise ValueError("Only an already-built immutable Modal image ID is accepted")
        if any(not isinstance(value, str) or not value for value in (workspace, app, environment)):
            raise ValueError("Explicit Modal workspace/app/environment required")
        if not isinstance(environment_id, str) or not environment_id.startswith("en-"):
            raise ValueError("Pinned dedicated environment ID required")
        guard = validate_environment(await asyncio.wait_for(self.backend.environment(workspace, environment), 30),
                                     environment, environment_id)
        price = await asyncio.wait_for(self.backend.prices(workspace), 30)
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            job = self.controller._job(connection, job_id)
            specification = json.loads(job["specification"])
            if job["kind"] != "training" or set(specification["reservations"]) != {"modal_micro_usd"}:
                raise ValueError("A separately budget-admitted training job is required")
            seconds = specification["timeout_seconds"]
            quote = compute_reservation(price["rates"], seconds, price["checked_at"])
            if specification["reservations"]["modal_micro_usd"] < quote["required_reservation_micro_usd"]:
                raise BudgetRefused("Modal job hold does not cover the compute reservation")
            campaign = connection.execute("SELECT id FROM campaign").fetchone()[0]
            name = "gw-train-" + digest(canonical([campaign, job_id]))[:24]
            identity = {"workspace": workspace, "app": app, "environment": environment, "environment_id": environment_id, "image_id": image_id,
                        "name": name, "seconds": seconds, "assignment": specification["assignment"],
                        "contract_sha256": self.controller.contract_hash}
            tags = {"campaign": campaign, "job": job_id, "identity": digest(canonical(identity))}
            plan = {**identity, "tags": tags, "quote": quote, "environment_guard": guard}
            existing = connection.execute("SELECT plan FROM modal_training_launches WHERE job_id=?", (job_id,)).fetchone()
            if existing:
                saved = json.loads(existing["plan"])
                if any(saved[key] != value for key, value in identity.items()):
                    raise LedgerConflict("Modal launch identity is immutable")
                return saved
            if job["state"] != "reserved":
                raise LedgerConflict("Prepare the launch before any dispatch")
            connection.execute("INSERT INTO modal_training_launches VALUES (?,?,NULL,NULL)", (job_id, canonical(plan).decode()))
            return plan

    def acknowledge(self, job_id, observed):
        job, launch, plan = self.stored(job_id)
        if (not isinstance(observed.get("id"), str) or not observed["id"].startswith("sb-")
                or observed.get("tags") != plan["tags"]):
            raise LedgerConflict("Modal sandbox identity does not match the launch")
        if launch["sandbox_id"] and launch["sandbox_id"] != observed["id"]:
            raise LedgerConflict("Refusing to adopt a replacement sandbox")
        with self.controller.ledger.transaction() as connection:
            previous = connection.execute("SELECT sandbox_id FROM modal_training_launches WHERE job_id=?", (job_id,)).fetchone()[0]
            if previous is not None and previous != observed["id"]:
                raise LedgerConflict("Concurrent sandbox identity changed")
            connection.execute("UPDATE modal_training_launches SET sandbox_id=? WHERE job_id=?", (observed["id"], job_id))
        if job["state"] == "dispatching":
            self.controller.provider_started(job_id, observed["id"])
        return observed["id"]

    async def start(self, job_id):
        job, launch, plan = self.stored(job_id)
        if job["state"] not in ("reserved", "dispatching", "running"):
            raise LedgerConflict("Job cannot start a Modal sandbox")
        if launch["sandbox_id"]:
            observed = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        else:
            observed = await asyncio.wait_for(self.backend.lookup(plan["app"], plan["environment"], plan["name"]), 30)
        if job["state"] == "reserved":
            if observed:
                raise LedgerConflict("Named sandbox collision before dispatch")
            compute_reservation(plan["quote"]["rates"], plan["seconds"], plan["quote"]["checked_at"])
            if job["deadline"] - time.time() < plan["seconds"] - 5:
                raise BudgetRefused("Prepared timeout no longer fits the admitted job deadline")
            validate_environment(await asyncio.wait_for(self.backend.environment(plan["workspace"], plan["environment"]), 30),
                                 plan["environment"], plan["environment_id"])
            self.controller.begin_dispatch(job_id)
            observed = await asyncio.wait_for(self.backend.create(plan), 120)
        if observed is None:
            raise LedgerConflict("Ambiguous Modal submission: retain hold and never recreate")
        return self.acknowledge(job_id, observed)

    async def run_worker(self, job_id):
        job, launch, plan = self.stored(job_id)
        if job["state"] != "running" or not launch["sandbox_id"]:
            raise LedgerConflict("Only an acknowledged sandbox can run the training worker")
        observed = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        self.acknowledge(job_id, observed)
        if observed.get("returncode") is not None:
            raise LedgerConflict("Sandbox already exited")
        validate_environment(await asyncio.wait_for(self.backend.environment(plan["workspace"], plan["environment"]), 30),
                             plan["environment"], plan["environment_id"])
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            current = self.controller._job(connection, job_id)
            if current["state"] != "running":
                raise LedgerConflict("Job changed before worker dispatch")
            staged = connection.execute("SELECT staging_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)).fetchone()
            if not staged or not staged["staging_receipt"]:
                raise LedgerConflict("Verified dataset staging is required before worker dispatch")
            remaining = current["deadline"] - int(time.time()) - 30
            if remaining < 30:
                raise BudgetRefused("Insufficient admitted lifetime for worker and artifact export")
            if connection.execute("SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)).fetchone():
                raise LedgerConflict("Worker dispatch already attempted; inspect artifacts, never retry automatically")
            connection.execute("INSERT INTO modal_training_attempts VALUES (?,?)", (job_id, int(time.time())))
        return await asyncio.wait_for(self.backend.run_worker(launch["sandbox_id"], plan, remaining), remaining + 5)

    async def terminate(self, job_id):
        job, launch, plan = self.stored(job_id)
        if launch["termination_receipt"]:
            return json.loads(launch["termination_receipt"])
        if not launch["sandbox_id"]:
            if job["state"] == "reserved":
                raise LedgerConflict("Undispatched work must be cancelled, not terminated")
            observed = await asyncio.wait_for(self.backend.lookup(plan["app"], plan["environment"], plan["name"]), 30)
            if observed is None:
                raise LedgerConflict("Unresolved create: absence is not proof of zero cost")
            self.acknowledge(job_id, observed)
            job, launch, plan = self.stored(job_id)
        self.controller.request_cleanup(job_id)
        observed = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        self.acknowledge(job_id, observed)
        await asyncio.wait_for(self.backend.terminate(launch["sandbox_id"]), 120)
        stopped = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        self.acknowledge(job_id, stopped)
        if type(stopped.get("returncode")) is not int:
            raise RuntimeError("Modal termination is not confirmed")
        receipt = {"sandbox_id": launch["sandbox_id"], "returncode": stopped["returncode"],
                   "checked_at": datetime.now(timezone.utc).isoformat(), "billing_reconciled": False}
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE modal_training_launches SET termination_receipt=? WHERE job_id=?",
                               (canonical(receipt).decode(), job_id))
        return receipt
