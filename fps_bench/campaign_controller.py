"""Trusted single-host coordinator state; provider adapters must validate receipts."""

import argparse
import json
from pathlib import Path
import re
import time

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger, LedgerConflict, positive_integer
from fps_bench.evaluation_contract import canonical, digest, paired_decision, split_for_controller, verify


IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
JOB_GROUPS = {"evaluation": "desktop", "driver_build": "desktop", "training": "training", "research": "research"}
GROUP_LIMITS = {"desktop": 2, "training": 1, "research": 2}


class CampaignController:
    def __init__(self, database, contract_path, expected_hash, private_splits=None):
        self.ledger = CampaignLedger(database)
        self.contract_path = Path(contract_path)
        self.contract_hash = expected_hash
        self.contract = verify(contract_path, expected_hash)
        self.private_splits = private_splits

    def initialize(self, campaign, duration_seconds=21600):
        positive_integer(duration_seconds, "duration_seconds")
        if duration_seconds > 21600:
            raise ValueError("Pilot campaigns cannot exceed six hours")
        self.ledger.initialize(campaign)
        with self.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS controller "
                               "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), contract_hash TEXT NOT NULL, "
                               "created INTEGER NOT NULL, deadline INTEGER NOT NULL, stopped INTEGER NOT NULL, "
                               "champion TEXT, duration INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS candidates "
                               "(id TEXT PRIMARY KEY, parent TEXT REFERENCES candidates(id), manifest TEXT NOT NULL, "
                               "manifest_hash TEXT NOT NULL UNIQUE, state TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS jobs "
                               "(id TEXT PRIMARY KEY, candidate TEXT NOT NULL REFERENCES candidates(id), "
                               "kind TEXT NOT NULL, resource_group TEXT NOT NULL, specification TEXT NOT NULL, "
                               "deadline INTEGER NOT NULL, state TEXT NOT NULL, provider_id TEXT, result TEXT, "
                               "cleanup_receipt TEXT UNIQUE)")
            connection.execute("CREATE TABLE IF NOT EXISTS decisions "
                               "(candidate TEXT NOT NULL REFERENCES candidates(id), split TEXT NOT NULL, "
                               "input_hash TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(candidate,split))")
            current = connection.execute("SELECT * FROM controller").fetchone()
            if current:
                if current["contract_hash"] != self.contract_hash or current["duration"] != duration_seconds:
                    raise LedgerConflict("Cannot change campaign protocol, duration or reset deadline")
                return
            now = int(time.time())
            connection.execute("INSERT INTO controller VALUES (1,?,?,?,0,NULL,?)",
                               (self.contract_hash, now, now + duration_seconds, duration_seconds))
            self.ledger._event(connection, "controller_initialized", {"deadline": now + duration_seconds,
                                                                      "contract_hash": self.contract_hash})

    def _controller(self, connection, admission=False):
        settings = connection.execute("SELECT * FROM controller").fetchone()
        if not settings or settings["contract_hash"] != self.contract_hash:
            raise LedgerConflict("Controller contract identity mismatch")
        if admission:
            frozen = connection.execute("SELECT frozen FROM campaign").fetchone()[0]
            if settings["stopped"] or frozen or int(time.time()) >= settings["deadline"]:
                raise BudgetRefused("Campaign stopped, frozen or past its deadline")
        return settings

    @staticmethod
    def _candidate(connection, candidate):
        row = connection.execute("SELECT * FROM candidates WHERE id=?", (candidate,)).fetchone()
        if row is None:
            raise LedgerConflict("Unknown candidate")
        return row

    @staticmethod
    def _job(connection, job_id):
        row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise LedgerConflict("Unknown job")
        return row

    def register_candidate(self, manifest):
        required = {"id", "parent", "change_class", "hypothesis", "contract_hash", "image", "driver_sha256", "model"}
        if not isinstance(manifest, dict) or not required <= manifest.keys():
            raise ValueError("Incomplete materialized candidate manifest")
        if not IDENTIFIER.fullmatch(manifest["id"]) or not SHA256.fullmatch(manifest["driver_sha256"]):
            raise ValueError("Invalid candidate or driver identity")
        if manifest["contract_hash"] != self.contract_hash or manifest["image"] != self.contract["spec"]["provenance"]["image"]:
            raise ValueError("Candidate changes the frozen protocol or image")
        if not isinstance(manifest["hypothesis"], str) or not manifest["hypothesis"].strip():
            raise ValueError("Candidate hypothesis required")
        model = manifest["model"]
        if (not isinstance(model, dict) or set(model) != {"base_model", "base_revision", "processor_revision", "adapter_sha256", "served_model"}
                or model["base_model"] != self.contract["episode_template"]["model"]
                or model["base_revision"] != self.contract["episode_template"]["revision"]
                or model["processor_revision"] != self.contract["episode_template"]["revision"]
                or not isinstance(model["served_model"], str) or not model["served_model"].strip()
                or (model["adapter_sha256"] is not None and not SHA256.fullmatch(model["adapter_sha256"]))):
            raise ValueError("Candidate model identity is incomplete or changes base/processor revision")
        payload = canonical(manifest).decode()
        with self.ledger.transaction() as connection:
            settings = self._controller(connection)
            existing = connection.execute("SELECT manifest FROM candidates WHERE id=?", (manifest["id"],)).fetchone()
            if existing:
                if existing[0] != payload:
                    raise LedgerConflict("Candidate manifests are immutable")
                return manifest["id"]
            self._controller(connection, admission=True)
            if manifest["change_class"] == "baseline":
                if settings["champion"] is not None or manifest["parent"] is not None or model["adapter_sha256"] is not None:
                    raise LedgerConflict("Baseline is registered exactly once, without an adapter")
                if model["served_model"] != self.contract["episode_template"]["served_model"]:
                    raise ValueError("Baseline serving identity differs from frozen model")
                state = "champion"
            else:
                if manifest["parent"] != settings["champion"]:
                    raise LedgerConflict("Candidate must be based on the current champion")
                if connection.execute("SELECT COUNT(*) FROM candidates WHERE parent IS NOT NULL").fetchone()[0] >= 10:
                    raise BudgetRefused("Pilot candidate limit reached")
                parent = json.loads(self._candidate(connection, manifest["parent"])["manifest"])
                driver_changed = manifest["driver_sha256"] != parent["driver_sha256"]
                model_changed = model != parent["model"]
                if manifest["change_class"] == "driver":
                    if not driver_changed or model_changed or not SHA256.fullmatch(manifest.get("patch_sha256", "")):
                        raise ValueError("Driver candidate must change only driver and identify its patch")
                elif manifest["change_class"] == "model":
                    if driver_changed or not model_changed or model["adapter_sha256"] is None:
                        raise ValueError("Model candidate must change only the trained model")
                elif manifest["change_class"] == "joint":
                    raise ValueError("Joint promotion requires the pending factorial provenance gate")
                else:
                    raise ValueError("Unsupported candidate class")
                state = "materialized"
            connection.execute("INSERT INTO candidates VALUES (?,?,?,?,?)",
                               (manifest["id"], manifest["parent"], payload, digest(payload.encode()), state))
            if state == "champion":
                connection.execute("UPDATE controller SET champion=?", (manifest["id"],))
            self.ledger._event(connection, "candidate_registered", {"id": manifest["id"], "manifest_hash": digest(payload.encode())})
        return manifest["id"]

    def admit_job(self, job_id, candidate, kind, assignment, reservations, timeout_seconds):
        if not IDENTIFIER.fullmatch(job_id) or kind not in JOB_GROUPS:
            raise ValueError("Unsupported job identity or kind")
        positive_integer(timeout_seconds, "timeout_seconds")
        if (not reservations and kind != "driver_build") or set(reservations) - {"modal_micro_usd", "litellm_tokens"}:
            raise ValueError("Explicit supported resource reservations required")
        required_resource = None if kind == "driver_build" else ("litellm_tokens" if kind == "research" else "modal_micro_usd")
        if required_resource is not None and required_resource not in reservations:
            raise ValueError("Job is missing required provider budget admission")
        if kind == "training":
            if (set(assignment) != {"split", "seeds", "dataset_sha256"} or assignment["split"] != "train"
                    or not isinstance(assignment["seeds"], list) or not assignment["seeds"]
                    or not SHA256.fullmatch(assignment["dataset_sha256"])):
                raise ValueError("Training requires a hashed train-only dataset manifest")
            training_seeds = set(self.contract["public_splits"]["train"]["seeds"])
            if (any(type(seed) is not int or seed not in training_seeds for seed in assignment["seeds"])
                    or len(assignment["seeds"]) != len(set(assignment["seeds"]))):
                raise ValueError("Training seeds must belong only to the registered training split")
        if kind == "evaluation":
            if set(assignment) != {"split", "seed", "repeat"}:
                raise ValueError("Evaluation jobs require an exact split/seed/repeat assignment")
            settings = split_for_controller(self.contract, assignment["split"], self.private_splits)
            if (type(assignment["seed"]) is not int or assignment["seed"] not in settings["seeds"]
                    or type(assignment["repeat"]) is not int or not 0 <= assignment["repeat"] < settings["repeats"]):
                raise ValueError("Episode is not registered in the frozen split")
            if assignment["split"] in ("confirmation", "sealed"):
                raise BudgetRefused("Private evaluation dispatch awaits a durable split-access lease")
        specification = canonical({"candidate": candidate, "kind": kind, "assignment": assignment,
                                   "reservations": reservations, "timeout_seconds": timeout_seconds}).decode()
        with self.ledger.transaction() as connection:
            current = self._controller(connection)
            existing = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if existing:
                if existing["specification"] != specification:
                    raise LedgerConflict("Job idempotency key reused with different work")
                return dict(existing)
            self._controller(connection, admission=True)
            materialized = self._candidate(connection, candidate)
            if materialized["state"] in ("rejected", "retired"):
                raise BudgetRefused("Candidate no longer admits work")
            group = JOB_GROUPS[kind]
            count = connection.execute("SELECT COUNT(*) FROM jobs WHERE resource_group=? AND state!='cleaned'", (group,)).fetchone()[0]
            if count >= GROUP_LIMITS[group]:
                raise BudgetRefused("Pilot concurrency exhausted, including pending cleanup")
            if kind == "evaluation":
                for row in connection.execute("SELECT specification FROM jobs WHERE candidate=? AND kind='evaluation'", (candidate,)):
                    if json.loads(row[0])["assignment"] == assignment:
                        raise LedgerConflict("Episode already assigned; hidden retries are forbidden")
            deadline = int(time.time()) + timeout_seconds
            if deadline + 300 > current["deadline"]:
                raise BudgetRefused("Job leaves insufficient campaign cleanup time")
            for resource, amount in reservations.items():
                self.ledger._reserve_in_transaction(connection, f"job:{job_id}:{resource}", resource, amount, deadline)
            connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,'reserved',NULL,NULL,NULL)",
                               (job_id, candidate, kind, group, specification, deadline))
            self.ledger._event(connection, "job_admitted", {"id": job_id, "candidate": candidate, "kind": kind})
            return dict(self._job(connection, job_id))

    def begin_dispatch(self, job_id):
        with self.ledger.transaction() as connection:
            self._controller(connection, admission=True)
            job = self._job(connection, job_id)
            stale = connection.execute("SELECT id FROM reservations WHERE state='held' AND expires_at<=?",
                                       (int(time.time()),)).fetchone()
            if stale:
                raise BudgetRefused("Unreconciled expired resource blocks dispatch")
            if job["state"] != "reserved" or int(time.time()) >= job["deadline"]:
                raise LedgerConflict("Dispatch already claimed or expired; reconcile, never resubmit")
            connection.execute("UPDATE jobs SET state='dispatching' WHERE id=?", (job_id,))
            self.ledger._event(connection, "dispatch_claimed", {"id": job_id})
            return dict(self._job(connection, job_id))

    def provider_started(self, job_id, provider_id):
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Provider identity required")
        with self.ledger.transaction() as connection:
            self._controller(connection)
            job = self._job(connection, job_id)
            if job["state"] == "running" and job["provider_id"] == provider_id:
                return
            if job["state"] != "dispatching":
                raise LedgerConflict("Provider acknowledgement does not match dispatch state")
            connection.execute("UPDATE jobs SET state='running',provider_id=? WHERE id=?", (provider_id, job_id))
            self.ledger._event(connection, "provider_started", {"id": job_id, "provider_id": provider_id})

    def record_result(self, job_id, result, artifact_sha256):
        if not SHA256.fullmatch(artifact_sha256):
            raise ValueError("Artifact bundle hash required")
        envelope = canonical({"result": result, "artifact_sha256": artifact_sha256}).decode()
        with self.ledger.transaction() as connection:
            self._controller(connection)
            job = self._job(connection, job_id)
            if job["result"] is not None:
                if job["result"] != envelope:
                    raise LedgerConflict("Job results are immutable")
                return
            if job["state"] != "running":
                raise LedgerConflict("Only acknowledged running jobs can produce a result")
            if job["kind"] == "evaluation":
                assigned = json.loads(job["specification"])["assignment"]
                if any(result.get(key) != value for key, value in {
                    **assigned, "candidate": job["candidate"], "contract_sha256": self.contract_hash
                }.items()):
                    raise ValueError("Result belongs to another assigned episode")
            connection.execute("UPDATE jobs SET result=?,state='cleanup_pending' WHERE id=?", (envelope, job_id))
            self.ledger._event(connection, "result_recorded", {"id": job_id, "artifact_sha256": artifact_sha256})

    def request_cleanup(self, job_id):
        with self.ledger.transaction() as connection:
            self._controller(connection)
            job = self._job(connection, job_id)
            if job["state"] in ("cleanup_pending", "cleaned"):
                return
            if job["state"] != "running":
                raise LedgerConflict("Reconcile provider submission before requesting cleanup")
            connection.execute("UPDATE jobs SET state='cleanup_pending' WHERE id=?", (job_id,))
            self.ledger._event(connection, "cleanup_requested", {"id": job_id})

    def cleanup_confirmed(self, job_id, receipt, actuals):
        if not isinstance(receipt, str) or not receipt.strip():
            raise ValueError("Validated cleanup/provider receipt required")
        with self.ledger.transaction() as connection:
            self._controller(connection)
            job = self._job(connection, job_id)
            resources = json.loads(job["specification"])["reservations"]
            if set(actuals) != set(resources):
                raise ValueError("Every reserved resource needs reconciled usage")
            if job["state"] == "reserved":
                raise LedgerConflict("Use cancel_undispatched for work that never left the controller")
            if job["state"] == "cleaned" and job["cleanup_receipt"] != receipt:
                raise LedgerConflict("Cleanup receipt is immutable")
            for resource, actual in actuals.items():
                self.ledger._settle_in_transaction(connection, f"job:{job_id}:{resource}", actual, f"{receipt}:{resource}")
            if job["state"] != "cleaned":
                connection.execute("UPDATE jobs SET state='cleaned',cleanup_receipt=? WHERE id=?", (receipt, job_id))
                self.ledger._event(connection, "cleanup_confirmed", {"id": job_id, "receipt": receipt})

    def cancel_undispatched(self, job_id):
        with self.ledger.transaction() as connection:
            self._controller(connection)
            job = self._job(connection, job_id)
            receipt = f"never-dispatched:{job_id}"
            if job["state"] == "cleaned" and job["cleanup_receipt"] == receipt:
                return
            if job["state"] != "reserved":
                raise LedgerConflict("Dispatch may have reached provider; zero-cost cancellation is unsafe")
            for resource in json.loads(job["specification"])["reservations"]:
                self.ledger._settle_in_transaction(connection, f"job:{job_id}:{resource}", 0, f"{receipt}:{resource}")
            connection.execute("UPDATE jobs SET state='cleaned',cleanup_receipt=? WHERE id=?", (receipt, job_id))
            self.ledger._event(connection, "undispatched_cancelled", {"id": job_id})

    def stop(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Stop reason required")
        with self.ledger.transaction() as connection:
            self._controller(connection)
            connection.execute("UPDATE controller SET stopped=1")
            connection.execute("UPDATE campaign SET frozen=1,reason=?", (reason,))
            self.ledger._event(connection, "campaign_stopped", {"reason": reason})

    def recovery_actions(self):
        with self.ledger.transaction() as connection:
            settings = self._controller(connection)
            frozen = connection.execute("SELECT frozen FROM campaign").fetchone()[0]
            jobs = connection.execute("SELECT * FROM jobs WHERE state!='cleaned' ORDER BY id").fetchall()
            actions = []
            for job in jobs:
                stopping = frozen or settings["stopped"] or int(time.time()) >= min(settings["deadline"], job["deadline"])
                action = {"reserved": "cancel_undispatched" if stopping else "eligible_for_dispatch",
                          "dispatching": "reconcile_ambiguous_submission",
                          "running": "cancel_and_reconcile" if stopping else "poll_provider",
                          "cleanup_pending": "export_artifacts_and_cleanup"}[job["state"]]
                actions.append({"job_id": job["id"], "action": action, "provider_id": job["provider_id"]})
            return actions

    def decide_development(self, candidate):
        with self.ledger.transaction() as connection:
            self._controller(connection)
            proposal = self._candidate(connection, candidate)
            if proposal["parent"] is None:
                raise ValueError("Baseline does not compete with itself")
            rows = []
            for job in connection.execute("SELECT * FROM jobs WHERE candidate IN (?,?) AND kind='evaluation'",
                                          (candidate, proposal["parent"])):
                assigned = json.loads(job["specification"])["assignment"]
                if assigned["split"] != "development":
                    continue
                if job["state"] != "cleaned" or job["result"] is None:
                    raise LedgerConflict("Comparison still has uncleaned or missing-result jobs")
                rows.append(json.loads(job["result"])["result"])
            result = paired_decision(self.contract, "development", rows, proposal["parent"], candidate)
            if result["decision"] in ("incomplete", "infrastructure_failure"):
                return result
            input_hash = digest(canonical(sorted(rows, key=lambda row: (row["candidate"], row["seed"], row["repeat"]))))
            existing = connection.execute("SELECT * FROM decisions WHERE candidate=? AND split='development'", (candidate,)).fetchone()
            if existing:
                if existing["input_hash"] != input_hash:
                    raise LedgerConflict("Decision inputs changed")
                return json.loads(existing["result"])
            connection.execute("INSERT INTO decisions VALUES (?,'development',?,?)",
                               (candidate, input_hash, canonical(result).decode()))
            state = "nominated" if result["decision"] == "nominate" else "rejected"
            connection.execute("UPDATE candidates SET state=? WHERE id=?", (state, candidate))
            self.ledger._event(connection, "development_decision", {"candidate": candidate, "decision": result["decision"]})
            return result

    def emit_telemetry(self, telemetry, event_id):
        try:
            snapshot = self.snapshot()
            if telemetry.campaign != snapshot["budget"]["campaign"]["id"]:
                raise ValueError("Telemetry campaign identity differs from ledger")
            reservations = snapshot["budget"]["reservations"]
            settled = lambda resource: (sum(row["actual"] for row in reservations
                                            if row["resource"] == resource and row["state"] == "settled")
                                        + sum(row["actual"] for row in snapshot["budget"]["prior_usage"]
                                              if row["resource"] == resource))
            held = lambda resource: sum(row["amount"] for row in reservations
                                        if row["resource"] == resource and row["state"] == "held")
            telemetry.record(event_id, "gameworld-research", {"experiment": "campaign", "phase": "budget", "objective": "accounting"}, {
                "gameworld_modal_spend": settled("modal_micro_usd") / 1_000_000,
                "gameworld_modal_reserved": held("modal_micro_usd") / 1_000_000,
                "gameworld_litellm_tokens": settled("litellm_tokens"),
                "gameworld_litellm_reserved_tokens": held("litellm_tokens"),
                "gameworld_active_claims": sum(job["kind"] in ("evaluation", "driver_build") and job["provider_id"] is not None and job["state"] != "cleaned"
                                                for job in snapshot["jobs"]),
                "gameworld_active_training_jobs": sum(job["kind"] == "training" and job["provider_id"] is not None and job["state"] != "cleaned"
                                                       for job in snapshot["jobs"]),
                "gameworld_desktop_slots_reserved": sum(job["kind"] in ("evaluation", "driver_build") and job["state"] != "cleaned"
                                                        for job in snapshot["jobs"]),
                "gameworld_training_slots_reserved": sum(job["kind"] == "training" and job["state"] != "cleaned"
                                                         for job in snapshot["jobs"]),
            })
            return True
        except Exception:
            return False

    def snapshot(self):
        with self.ledger.transaction() as connection:
            settings = dict(self._controller(connection))
            candidates = [dict(row) for row in connection.execute("SELECT id,parent,manifest_hash,state FROM candidates ORDER BY id")]
            jobs = [dict(row) for row in connection.execute("SELECT id,candidate,kind,state,provider_id,cleanup_receipt FROM jobs ORDER BY id")]
        return {"controller": settings, "candidates": candidates, "jobs": jobs,
                "budget": self.ledger.snapshot(), "recovery": self.recovery_actions()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["status", "recovery", "stop"])
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-hash", required=True)
    parser.add_argument("--reason")
    args = parser.parse_args()
    controller = CampaignController(args.db, args.contract, args.expected_hash)
    if args.operation == "stop":
        if not args.reason:
            parser.error("stop requires --reason")
        controller.stop(args.reason)
        result = {"stop_recorded": True, "provider_cleanup_not_executed": True, "obligations": controller.recovery_actions()}
    elif args.operation == "recovery":
        result = controller.recovery_actions()
    else:
        result = controller.snapshot()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
