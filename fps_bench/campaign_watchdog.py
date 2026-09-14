"""Independent, cleanup-only deadline watchdog for a trusted local controller."""

import argparse
import asyncio
import fcntl
import json
from pathlib import Path
import time

from fps_bench.campaign_controller import CampaignController
from fps_bench.campaign_ledger import LedgerConflict


class CampaignWatchdog:
    def __init__(self, controller, modal=None, fleet_factory=None, serving=None, operation_timeout=210):
        if type(operation_timeout) not in (int, float) or not 0 < operation_timeout <= 240:
            raise ValueError("Cleanup timeout must be in (0, 240] seconds")
        self.controller = controller
        self.modal = modal
        self.serving = serving
        self.fleet_factory = fleet_factory
        self.operation_timeout = operation_timeout

    def due_jobs(self):
        with self.controller.ledger.transaction() as connection:
            settings = self.controller._controller(connection)
            frozen = connection.execute("SELECT frozen FROM campaign").fetchone()[0]
            now = time.time()
            jobs = []
            for row in connection.execute(
                    "SELECT * FROM jobs WHERE state NOT IN ('billing_pending','cleaned') ORDER BY id"):
                if frozen or settings["stopped"] or now >= min(settings["deadline"], row["deadline"]):
                    jobs.append(dict(row))
            return jobs

    async def clean(self, job):
        job_id = job["id"]
        if job["state"] == "reserved":
            self.controller.cancel_undispatched(job_id)
            return "cancelled_undispatched"
        if job["kind"] == "training":
            if self.modal is None:
                from fps_bench.gameworld_modal import GameWorldModalTrainingLifecycle
                self.modal = GameWorldModalTrainingLifecycle(self.controller)
            await self.modal.terminate(job_id)
            return "terminated_billing_pending"
        if job["kind"] == "serving":
            if self.serving is None:
                raise LedgerConflict("Serving cleanup requires its pinned durable output directory")
            await self.serving.terminate(job_id)
            return "serving_terminated_billing_pending"
        if job["kind"] in ("driver_build", "rollout", "evaluation") and self.fleet_factory is not None:
            fleet = self.fleet_factory(job)
            await fleet.release(job_id)
            return "claim_released"
        raise LedgerConflict("No cleanup adapter for this job kind; retain its holds")

    async def tick(self):
        jobs = self.due_jobs()

        async def attempt(job):
            try:
                async with asyncio.timeout(self.operation_timeout):
                    outcome = await self.clean(job)
                event = {"job_id": job["id"], "outcome": outcome}
            except Exception as error:
                event = {"job_id": job["id"], "outcome": "unresolved", "error_type": type(error).__name__}
            with self.controller.ledger.transaction() as connection:
                self.controller._controller(connection)
                self.controller.ledger._event(connection, "watchdog_cleanup", event)
            return event

        return await asyncio.gather(*(attempt(job) for job in jobs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--fleet-receipts", type=Path)
    parser.add_argument("--pool", default="gameworld-autoresearch")
    parser.add_argument("--serving-output", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing initialized controller database required; never create a new campaign")
    if not 1 <= args.interval <= 60:
        parser.error("Interval must be 1..60 seconds")
    controller = CampaignController(args.database, args.contract, args.contract_sha256)
    controller.snapshot()
    fleet_factory = None
    if args.fleet_receipts:
        if not args.fleet_receipts.is_dir():
            parser.error("Fleet receipt directory must already exist")

        def fleet_factory(job):
            from fps_bench.fleet_provider import FleetLifecycle
            assignment = json.loads(job["specification"])["assignment"]
            return FleetLifecycle(controller, assignment.get("pool", args.pool), args.fleet_receipts)

    serving = None
    if args.serving_output:
        if not args.serving_output.is_dir():
            parser.error("Serving output directory must already exist")
        from fps_bench.gameworld_serving import GameWorldServingLifecycle
        serving = GameWorldServingLifecycle(controller, args.serving_output)
    watchdog = CampaignWatchdog(controller, fleet_factory=fleet_factory, serving=serving)

    async def watch():
        while True:
            outcomes = await watchdog.tick()
            print(json.dumps({"checked_at_ns": time.time_ns(), "outcomes": outcomes}), flush=True)
            if args.once:
                return int(any(event["outcome"] == "unresolved" for event in outcomes))
            await asyncio.sleep(args.interval)

    with Path(str(args.database) + ".watchdog.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another watchdog already holds this database lock")
        raise SystemExit(asyncio.run(watch()))


if __name__ == "__main__":
    main()
