"""Authenticated, conservative reconciliation for completed GameWorld Modal jobs."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.modal_reconciliation import reconcile, schema


ACTIVE_STATES = ("reserved", "dispatching", "running", "cleanup_pending")


def hour(value):
    return value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


class ModalBillingBackend:
    async def observe(self, plan):
        import modal

        workspace = await modal.Workspace.from_context().hydrate.aio()
        if workspace.name != plan["scope"]["workspace"]:
            raise ValueError("Active Modal credentials belong to another workspace")
        report = await workspace.billing.report.aio(
            start=datetime.fromisoformat(plan["scope"]["start"]),
            end=datetime.fromisoformat(plan["scope"]["end"]), resolution="h")
        rows = [{
            "object_id": row.object_id,
            "environment": row.environment_name,
            "interval_start": row.interval_start.isoformat(),
            "cost": str(row.cost),
        } for row in report if row.object_id in plan["scope"]["object_ids"]]
        running = []
        for app_id in plan["scope"]["object_ids"]:
            running.extend([sandbox.object_id async for sandbox in modal.Sandbox.list.aio(app_id=app_id)])
        resources = []
        for resource in plan["resources"]:
            sandbox = await modal.Sandbox.from_id.aio(resource["provider_id"])
            resources.append({
                **resource,
                "returncode": await sandbox.poll.aio(),
                "observed_tags": await sandbox.get_tags.aio(),
            })
        closure = {
            "scope": plan["scope"], "resources": resources,
            "running_sandbox_ids": sorted(running),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        return {"rows": rows, "closure": closure,
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


class GameWorldModalReconciler:
    def __init__(self, controller, output, backend=None, retry_seconds=60):
        if type(retry_seconds) is not int or not 0 <= retry_seconds <= 3600:
            raise ValueError("Modal billing retry delay must be 0..3600 seconds")
        self.controller = controller
        self.ledger = controller.ledger
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.backend = backend or ModalBillingBackend()
        self.retry_seconds = retry_seconds
        with self.ledger.transaction() as connection:
            schema(connection)
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_modal_reconciliation_attempts ("
                "id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL, ordinal INTEGER NOT NULL, "
                "state TEXT NOT NULL, error_type TEXT, started_at INTEGER NOT NULL, finished_at INTEGER, "
                "UNIQUE(plan_sha256,ordinal))"
            )
            connection.execute(
                "UPDATE gameworld_modal_reconciliation_attempts SET state='failed',"
                "error_type='InterruptedBillingAttempt',finished_at=? WHERE state='running'",
                (int(time.time()),),
            )
        if self.consecutive_failures() >= 3 and not self.controller.snapshot()["controller"]["stopped"]:
            self.controller.stop("Three consecutive Modal billing reconciliation failures")

    @staticmethod
    def _launch(connection, job):
        table = "modal_training_launches" if job["kind"] == "training" else "gameworld_serving_launches"
        if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            raise ValueError("Modal launch journal is missing")
        launch = connection.execute(f"SELECT * FROM {table} WHERE job_id=?", (job["id"],)).fetchone()
        if launch is None or not launch["sandbox_id"] or not launch["termination_receipt"]:
            raise ValueError("Billing-pending Modal job lacks terminal launch evidence")
        plan = json.loads(launch["plan"])
        receipt = json.loads(launch["termination_receipt"])
        if (receipt.get("sandbox_id") != launch["sandbox_id"]
                or type(receipt.get("returncode")) is not int
                or receipt.get("billing_reconciled") is not False):
            raise ValueError("Modal termination receipt is incomplete")
        return dict(launch), plan, receipt

    def close_recovered(self):
        groups = {}
        with self.ledger.transaction() as connection:
            for job in connection.execute(
                    "SELECT * FROM jobs WHERE state='billing_pending' AND kind IN ('training','serving')"):
                reservation_id = f"job:{job['id']}:modal_micro_usd"
                member = connection.execute(
                    "SELECT group_id FROM modal_reconciliation_members WHERE reservation_id=?",
                    (reservation_id,),
                ).fetchone()
                if member:
                    groups.setdefault(member["group_id"], []).append(job["id"])
        closed = []
        for group_id, job_ids in sorted(groups.items()):
            self.controller.retain_reconciled_jobs(sorted(job_ids), group_id)
            closed.extend(job_ids)
        return sorted(closed)

    def plan(self, now=None):
        now = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
        with self.ledger.transaction() as connection:
            placeholders = ",".join("?" for _ in ACTIVE_STATES)
            if connection.execute(
                    f"SELECT 1 FROM jobs WHERE kind IN ('training','serving') "
                    f"AND state IN ({placeholders}) LIMIT 1", ACTIVE_STATES).fetchone():
                return None
            jobs = [dict(row) for row in connection.execute(
                "SELECT * FROM jobs WHERE state='billing_pending' AND kind IN ('training','serving') ORDER BY id"
            )]
            resources = []
            reservation_times = {}
            for event in connection.execute("SELECT timestamp,payload FROM events WHERE kind='reserved'"):
                payload = json.loads(event["payload"])
                reservation_times[payload["id"]] = event["timestamp"]
            for job in jobs:
                reservation_id = f"job:{job['id']}:modal_micro_usd"
                reservation = connection.execute(
                    "SELECT * FROM reservations WHERE id=?", (reservation_id,)
                ).fetchone()
                if reservation is None or reservation["state"] != "held":
                    continue
                launch, launch_plan, receipt = self._launch(connection, job)
                if launch_plan.get("workspace") is None or launch_plan.get("environment") is None:
                    raise ValueError("Modal launch lacks billing scope")
                resources.append({
                    "job_id": job["id"], "reservation_id": reservation_id, "kind": "sandbox",
                    "provider_id": launch["sandbox_id"], "app_id": launch_plan["app_id"],
                    "expected_tags": launch_plan["tags"], "finished_at": receipt["checked_at"],
                    "workspace": launch_plan["workspace"], "environment": launch_plan["environment"],
                })
            if not resources:
                return None
            if len(resources) > 256:
                raise ValueError("Modal reconciliation group exceeds 256 resources")
            scopes = {(item["workspace"], item["environment"]) for item in resources}
            if len(scopes) != 1:
                raise ValueError("One reconciliation group cannot span Modal workspaces or environments")
            starts = []
            finishes = []
            selected = {item["reservation_id"] for item in resources}
            for item in resources:
                if item["reservation_id"] not in reservation_times:
                    raise ValueError("Modal reservation is missing its durable start event")
                starts.append(datetime.fromtimestamp(reservation_times[item["reservation_id"]], timezone.utc))
                finished = datetime.fromisoformat(item["finished_at"])
                if finished.tzinfo is None:
                    raise ValueError("Modal completion timestamp must be timezone-aware")
                finishes.append(finished.astimezone(timezone.utc))
            end = hour(max(finishes)) + timedelta(hours=1)
            if end > hour(now):
                return None
            for reservation in connection.execute(
                    "SELECT id FROM reservations WHERE resource='modal_micro_usd' AND state='held'"):
                if (reservation["id"] not in selected
                        and reservation_times.get(reservation["id"], int(end.timestamp())) < end.timestamp()):
                    return None
            workspace, environment = scopes.pop()
        scope = {
            "workspace": workspace, "environment": environment,
            "object_ids": sorted({item["app_id"] for item in resources}),
            "start": hour(min(starts)).isoformat(), "end": end.isoformat(),
        }
        cleaned = [{key: item[key] for key in (
            "job_id", "reservation_id", "kind", "provider_id", "app_id", "expected_tags", "finished_at")}
            for item in resources]
        return {"scope": scope, "resources": sorted(cleaned, key=lambda item: item["reservation_id"])}

    def _attempt(self, plan):
        plan_hash = digest(canonical(plan))
        with self.ledger.transaction() as connection:
            ordinal = connection.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 FROM gameworld_modal_reconciliation_attempts WHERE plan_sha256=?",
                (plan_hash,),
            ).fetchone()[0]
            attempt_id = "gw-modal-billing-" + digest(canonical([plan_hash, ordinal]))[:32]
            connection.execute(
                "INSERT INTO gameworld_modal_reconciliation_attempts VALUES (?,?,?,'running',NULL,?,NULL)",
                (attempt_id, plan_hash, ordinal, int(time.time())),
            )
        return attempt_id, self.output / attempt_id

    @staticmethod
    def _prepare(directory, plan):
        directory.mkdir(mode=0o700)
        exclusive_write(directory / "plan.json", canonical(plan), 0o400)

    def retry_ready(self, plan, now=None):
        if self.retry_seconds == 0:
            return True
        now = int(time.time()) if now is None else int(now.timestamp())
        plan_hash = digest(canonical(plan))
        with self.ledger.transaction() as connection:
            latest = connection.execute(
                "SELECT ordinal,state,started_at FROM gameworld_modal_reconciliation_attempts "
                "WHERE plan_sha256=? ORDER BY ordinal DESC LIMIT 1", (plan_hash,),
            ).fetchone()
        if latest is None or latest["state"] == "complete":
            return True
        delay = min(3600, self.retry_seconds * (2 ** min(latest["ordinal"] - 1, 6)))
        return now >= latest["started_at"] + delay

    def _terminal(self, attempt_id, state, error_type=None):
        with self.ledger.transaction() as connection:
            connection.execute(
                "UPDATE gameworld_modal_reconciliation_attempts SET state=?,error_type=?,finished_at=? WHERE id=?",
                (state, error_type, int(time.time()), attempt_id),
            )
            self.ledger._event(connection, "gameworld_modal_reconciliation_" + state, {
                "id": attempt_id, "error_type": error_type,
            })

    def consecutive_failures(self):
        with self.ledger.transaction() as connection:
            rows = connection.execute(
                "SELECT state FROM gameworld_modal_reconciliation_attempts ORDER BY started_at DESC,rowid DESC"
            ).fetchall()
        failures = 0
        for row in rows:
            if row["state"] != "failed":
                break
            failures += 1
        return failures

    async def run_once(self, now=None):
        recovered = self.close_recovered()
        plan = self.plan(now)
        if plan is None:
            return {"outcome": "recovered", "jobs": recovered} if recovered else None
        if not self.retry_ready(plan, now):
            return None
        attempt_id, directory = self._attempt(plan)
        try:
            self._prepare(directory, plan)
            observed = await self.backend.observe(plan)
            exclusive_write(directory / "provider.json", canonical(observed), 0o400)
            specification = {
                "scope": plan["scope"],
                "reservation_ids": sorted(item["reservation_id"] for item in plan["resources"]),
                "policy": "retain-full-allocation-no-refund-v1",
            }
            result = reconcile(self.ledger, specification, observed["rows"], observed["closure"])
            job_ids = sorted(item["job_id"] for item in plan["resources"])
            self.controller.retain_reconciled_jobs(job_ids, result["group_id"])
            exclusive_write(directory / "result.json", canonical(result), 0o400)
            exclusive_write(directory / "controller.json", canonical(self.controller.snapshot()), 0o400)
            self._terminal(attempt_id, "complete")
            return {"outcome": "complete", "attempt": attempt_id,
                    "group_id": result["group_id"], "jobs": job_ids,
                    "observed_micro_usd": result["observed_micro_usd"],
                    "retained_micro_usd": result["retained_micro_usd"]}
        except Exception as error:
            self._terminal(attempt_id, "failed", type(error).__name__)
            if self.consecutive_failures() >= 3 and not self.controller.snapshot()["controller"]["stopped"]:
                self.controller.stop("Three consecutive Modal billing reconciliation failures")
            return {"outcome": "failed", "attempt": attempt_id,
                    "error_type": type(error).__name__}
