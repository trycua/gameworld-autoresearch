"""Bounded Fleet claim lifecycle for the trusted coordinator; no inference calls."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write


def timestamp(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


class FleetSDKBackend:
    async def inspect_pool(self, name):
        from cua_sandbox import Pool
        from cua_sandbox.transport.fleet_cloud import _FleetClient
        pool = await Pool.get(name)
        client = _FleetClient()
        try:
            resource = pool.resource
            template = await client.get_template(resource.metadata.namespace, resource.spec.sandbox_template_ref.name)
            claims = await client.list_claims(resource.metadata.namespace)
            vm = template.spec.vm_template
            scaling = resource.spec.autoscaling
            return {"pool": pool.name, "namespace": resource.metadata.namespace,
                    "created_at": resource.metadata.creation_timestamp,
                    "ttl_seconds": resource.spec.ttl_seconds_after_created,
                    "requested_replicas": resource.spec.replicas,
                    "replicas": resource.status.replicas if resource.status else None,
                    "ready_replicas": resource.status.ready_replicas if resource.status else None,
                    "min_pool_size": scaling.min_pool_size if scaling else None,
                    "max_pool_size": scaling.max_pool_size if scaling else None,
                    "image": vm.container_disk_image, "runtime": str(vm.runtime),
                    "cpu": vm.cpu_cores, "memory": vm.memory,
                    "claims": [claim.metadata.name for claim in claims],
                    "checked_at": datetime.now(timezone.utc).isoformat()}
        finally:
            await client.close()

    async def find_claim(self, pool_name, name):
        from cua_sandbox import Pool
        from cua_sandbox.transport.fleet_cloud import _FleetClient
        pool = await Pool.get(pool_name)
        client = _FleetClient()
        try:
            try:
                claim = await client.get_claim(pool.resource, name)
            except LookupError:
                return None
            return {"pool": pool_name, "warmpool": claim.spec.warmpool,
                    "template_name": claim.spec.sandbox_template_ref.name, "namespace": claim.metadata.namespace,
                    "name": claim.metadata.name, "created_at": claim.metadata.creation_timestamp,
                    "ttl_seconds": claim.spec.ttl_seconds_after_created,
                    "phase": claim.status.phase if claim.status else None,
                    "sandbox_name": claim.status.sandbox.name if claim.status and claim.status.sandbox else None}
        finally:
            await client.close()

    async def create_claim(self, pool_name, name, ttl):
        from cua_sandbox import Pool
        pool = await Pool.get(pool_name)
        handle = await pool.create_claim(name=name, ttl_seconds_after_created=ttl)
        return handle.to_dict()

    async def connect(self, reference, timeout):
        from cua_sandbox.pool import _ClaimHandle
        return await asyncio.wait_for(_ClaimHandle.from_dict(reference).wait(time_to_start=timeout), timeout)

    async def release(self, reference):
        from cua_sandbox.pool import _ClaimHandle
        await _ClaimHandle.from_dict(reference).release()


class FleetLifecycle:
    def __init__(self, controller, pool, output, backend=None):
        self.controller, self.pool = controller, pool
        self.output = Path(output)
        self.backend = backend or FleetSDKBackend()

    def job(self, job_id):
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection)
            return dict(self.controller._job(connection, job_id))

    def identity(self, job_id):
        job = self.job(job_id)
        specification = json.loads(job["specification"])
        if job["kind"] not in ("driver_build", "rollout", "evaluation"):
            raise ValueError("Only desktop jobs may use the Fleet lifecycle")
        resources = set(specification["reservations"])
        if ((job["kind"] == "driver_build" and resources)
                or (job["kind"] in ("rollout", "evaluation") and resources != {"modal_micro_usd"})):
            raise ValueError("Fleet desktop job resources differ from the controller contract")
        assignment = specification["assignment"]
        if job["kind"] == "driver_build" and (assignment.get("pool") != self.pool
                or assignment.get("operation") not in ("warm-driver-probe", "driver-candidate")):
            raise ValueError("Driver build job is not assigned to this pool and operation")
        campaign = self.controller.ledger.snapshot()["campaign"]["id"]
        name = "gw-" + digest(canonical([campaign, job_id]))[:24]
        return job, {"version": 1, "provider": "fleet", "pool": self.pool, "namespace": self.pool,
                     "claim": name, "service": "server"}

    async def preflight(self, required_seconds=1200):
        current = await asyncio.wait_for(self.backend.inspect_pool(self.pool), 30)
        if (current["namespace"] != self.pool or current["runtime"] != "RuntimeKind.GVISOR"
                or current["image"] != self.controller.contract["spec"]["provenance"]["image"]
                or current["min_pool_size"] != 0 or current["max_pool_size"] != 20
                or current["cpu"] != 4 or current["memory"] != "16384Mi"):
            raise ValueError("Fleet template/configuration differs from approved pilot")
        if not current["ttl_seconds"] or timestamp(current["created_at"]) + current["ttl_seconds"] < time.time() + required_seconds:
            raise ValueError("Pool expires before the bounded operation and cleanup window")
        return current

    def assert_owned(self, job, reference, claim):
        specification = json.loads(job["specification"])
        admitted = job["deadline"] - specification["timeout_seconds"]
        if (claim["pool"] != self.pool or claim["namespace"] != reference["namespace"]
                or claim["warmpool"] not in ("default", self.pool) or claim["template_name"] != self.pool
                or claim["name"] != reference["claim"] or timestamp(claim["created_at"]) < admitted - 2
                or timestamp(claim["created_at"]) > job["deadline"]
                or not claim["ttl_seconds"] or claim["ttl_seconds"] > specification["timeout_seconds"]):
            raise LedgerConflict("Refusing to adopt or release a claim with mismatched ownership/TTL")
        observed = self.output / f"{job['id']}-claim-observed.json"
        identity = {name: claim[name] for name in ("pool", "warmpool", "template_name", "namespace", "name", "created_at", "ttl_seconds")}
        if observed.exists():
            if json.loads(observed.read_bytes()) != identity:
                raise LedgerConflict("Claim was replaced after ownership was recorded")
        else:
            exclusive_write(observed, canonical(identity))

    async def acquire(self, job_id):
        job, reference = self.identity(job_id)
        specification = json.loads(job["specification"])
        await self.preflight(max(300, job["deadline"] - int(time.time())) + 600)
        existing = await asyncio.wait_for(self.backend.find_claim(self.pool, reference["claim"]), 30)
        if job["state"] == "reserved":
            if existing is not None:
                raise LedgerConflict("Claim collision before dispatch; existing claim will not be adopted")
            path = self.output / f"{job_id}-claim.json"
            payload = canonical(reference)
            if path.exists():
                if path.read_bytes() != payload:
                    raise LedgerConflict("Persisted claim reference differs")
            else:
                exclusive_write(path, payload)
            self.controller.begin_dispatch(job_id)
            await asyncio.wait_for(self.backend.create_claim(self.pool, reference["claim"], specification["timeout_seconds"]), 45)
            existing = await asyncio.wait_for(self.backend.find_claim(self.pool, reference["claim"]), 30)
        elif job["state"] not in ("dispatching", "running"):
            raise LedgerConflict("Job cannot acquire another Fleet sandbox")
        if existing is None:
            raise LedgerConflict("Ambiguous claim submission: reconcile later, never create again")
        self.assert_owned(job, reference, existing)
        provider_id = f"fleet:{self.pool}/{reference['claim']}"
        if job["state"] != "running":
            self.controller.provider_started(job_id, provider_id)
        remaining = job["deadline"] - int(time.time())
        if remaining <= 30:
            raise TimeoutError("Insufficient job lifetime to connect")
        return await self.backend.connect(reference, min(600, remaining - 30))

    async def release(self, job_id, timeout_seconds=120):
        job, reference = self.identity(job_id)
        if job["state"] == "reserved":
            self.controller.cancel_undispatched(job_id)
            return {"never_dispatched": True}
        deadline = time.monotonic() + timeout_seconds
        claim = await asyncio.wait_for(self.backend.find_claim(self.pool, reference["claim"]), 30)
        if claim is None:
            if job["state"] == "dispatching":
                raise LedgerConflict("Missing claim is not proof an ambiguous create never completed")
        else:
            if job["state"] == "cleaned":
                raise LedgerConflict("A claim appeared after confirmed cleanup; do not delete a replacement")
            self.assert_owned(job, reference, claim)
            if job["state"] == "dispatching":
                self.controller.provider_started(job_id, f"fleet:{self.pool}/{reference['claim']}")
            self.controller.request_cleanup(job_id)
            await asyncio.wait_for(self.backend.release(reference), 30)
        while await asyncio.wait_for(self.backend.find_claim(self.pool, reference["claim"]), 30) is not None:
            if time.monotonic() >= deadline:
                raise TimeoutError("Claim deletion not yet confirmed; retain cleanup obligation")
            await asyncio.sleep(2)
        receipt = {"job_id": job_id, "pool": self.pool, "claim": reference["claim"], "claim_absent": True,
                   "checked_at": datetime.now(timezone.utc).isoformat(), "modal_operations": 0}
        path = self.output / f"{job_id}-cleanup.json"
        if path.exists():
            receipt = json.loads(path.read_bytes())
        else:
            exclusive_write(path, canonical(receipt))
        self.controller.provider_cleanup_confirmed(job_id, "fleet-claim-release:" + digest(canonical(receipt)))
        return receipt

    async def wait_zero(self, timeout_seconds=900):
        deadline = time.monotonic() + timeout_seconds
        while True:
            current = await asyncio.wait_for(self.backend.inspect_pool(self.pool), 30)
            if current["replicas"] == 0 and current["ready_replicas"] == 0 and not current["claims"]:
                return {"scaled_to_zero": True, "pool": current}
            if time.monotonic() >= deadline:
                return {"scaled_to_zero": False, "pool": current}
            await asyncio.sleep(20)
