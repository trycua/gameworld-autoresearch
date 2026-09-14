"""Durable GameWorld workflow coordinator over the supervisor and campaign ledger."""

import argparse
import json
import time
from pathlib import Path

from fps_bench.campaign_controller import CampaignController, IDENTIFIER
from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict, positive_integer
from fps_bench.evaluation_contract import canonical, digest, exclusive_write, schedule
from fps_bench.evaluation_contract import verify as verify_contract_sources
from fps_bench.gameworld_evaluation import validate_contract
from fps_bench.gameworld_grpo import policy_digest, validate_policy_identity
from fps_bench.gameworld_research import (
    DEFAULT_CATALOG,
    DEFAULT_POLICY,
    GameWorldResearchSupervisor,
)
from fps_bench.gameworld_training import GameWorldTrainingRegistry


QUEUE_STATES = {"pending", "admitted", "live", "complete", "failed"}
WORKFLOW_STATES = {
    "awaiting_patch", "building", "starting_baseline_serving", "collecting_rollouts",
    "awaiting_baseline_serving_stop", "awaiting_dataset", "awaiting_sft_dataset",
    "training", "serving", "evaluating", "qualified_serving_live",
    "confirming", "sealed_evaluating", "awaiting_serving_stop", "complete", "rejected",
}
ROOT = Path(__file__).resolve().parents[1]


def write_once(path, data, mode=0o400):
    path = Path(path)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise LedgerConflict(f"Immutable coordinator input changed: {path}")
        return path
    exclusive_write(path, data, mode)
    return path


class GameWorldCoordinator:
    def __init__(self, database, contract_path, contract_hash, baseline_output, state_root,
                 policy_path=DEFAULT_POLICY, catalog_path=DEFAULT_CATALOG, telemetry_path=None,
                 pool="gameworld-autoresearch", registry=None, private_splits=None,
                 verify_workspace=True):
        self.database = Path(database)
        self.state_root = Path(state_root).resolve()
        self.pool = pool
        self.policy_path = Path(policy_path)
        self.catalog_path = Path(catalog_path)
        if verify_workspace:
            contract = verify_contract_sources(contract_path, contract_hash)
            validate_contract(contract, contract_hash, private_splits)
            verify_contract_sources(contract_path, contract_hash, workspace=ROOT)
        self.supervisor = GameWorldResearchSupervisor(
            database, baseline_output, policy_path, catalog_path, telemetry_path)
        self.controller = CampaignController(database, contract_path, contract_hash, private_splits)
        self.policy = self.supervisor.policy
        self.context = self.supervisor.context
        self.registry = registry

    def initialize(self, campaign, baseline_policy_path):
        self.supervisor.initialize(campaign)
        self.controller.initialize(campaign, self.policy["limits"]["campaign_seconds"])
        policy_bytes = Path(baseline_policy_path).read_bytes()
        identity = json.loads(policy_bytes)
        if canonical(identity) != policy_bytes:
            raise ValueError("Baseline serving policy must use canonical encoding")
        validate_policy_identity(identity, self.policy)
        template = self.controller.contract["episode_template"]
        if (identity["base_model"] != template["model"]
                or identity["base_revision"] != template["revision"]
                or identity["adapter_sha256"] is not None
                or identity["served_model"] != template["served_model"]):
            raise ValueError("Baseline serving policy differs from the frozen evaluation contract")
        policy_target = write_once(self.state_root / "inputs/baseline-policy.json", policy_bytes)
        baseline = {
            "id": "baseline", "parent": None, "change_class": "baseline",
            "hypothesis": "Frozen all-catalog GameWorld baseline",
            "contract_hash": self.controller.contract_hash,
            "image": self.controller.contract["spec"]["provenance"]["image"],
            "driver_sha256": self.controller.contract["spec"]["baseline_driver_sha256"],
            "policy_sha256": policy_digest(identity),
            "model": {
                "base_model": identity["base_model"], "base_revision": identity["base_revision"],
                "processor_revision": identity["base_revision"], "adapter_sha256": None,
                "served_model": identity["served_model"],
            },
            "policy_path": str(policy_target),
        }
        self.controller.register_candidate(baseline)
        with self.controller.ledger.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_coordinator ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), contract_hash TEXT NOT NULL, "
                "baseline_policy_sha256 TEXT NOT NULL, state_root TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_workflows ("
                "proposal_id TEXT PRIMARY KEY, action_id TEXT NOT NULL UNIQUE, track TEXT NOT NULL, "
                "comparison TEXT NOT NULL UNIQUE, state TEXT NOT NULL, candidate_id TEXT, "
                "details TEXT NOT NULL, decision TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_work_items ("
                "id TEXT PRIMARY KEY, workflow TEXT NOT NULL REFERENCES gameworld_workflows(proposal_id), "
                "phase TEXT NOT NULL, ordinal INTEGER NOT NULL, job_id TEXT NOT NULL UNIQUE, "
                "candidate TEXT NOT NULL, kind TEXT NOT NULL, assignment TEXT NOT NULL, "
                "reservations TEXT NOT NULL, timeout_seconds INTEGER NOT NULL, state TEXT NOT NULL, "
                "private_lease TEXT, "
                "UNIQUE(workflow,phase,ordinal))"
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(gameworld_work_items)")}
            if "private_lease" not in columns:
                connection.execute("ALTER TABLE gameworld_work_items ADD COLUMN private_lease TEXT")
            existing = connection.execute("SELECT * FROM gameworld_coordinator").fetchone()
            expected = {
                "contract_hash": self.controller.contract_hash,
                "baseline_policy_sha256": digest(policy_bytes),
                "state_root": str(self.state_root),
            }
            if existing:
                if any(existing[name] != value for name, value in expected.items()):
                    raise LedgerConflict("Coordinator identity or durable root changed")
            else:
                connection.execute(
                    "INSERT INTO gameworld_coordinator VALUES (1,?,?,?)",
                    (expected["contract_hash"], expected["baseline_policy_sha256"], expected["state_root"]),
                )
                self.controller.ledger._event(connection, "gameworld_coordinator_initialized", expected)
        if self.registry is None:
            self.registry = GameWorldTrainingRegistry(
                self.controller, self.policy_path, self.catalog_path)
        return self.snapshot()

    def register(self, proposal):
        return self.supervisor.register(proposal)

    def _workflow(self, connection, action_or_proposal):
        row = connection.execute(
            "SELECT * FROM gameworld_workflows WHERE action_id=? OR proposal_id=?",
            (action_or_proposal, action_or_proposal),
        ).fetchone()
        if row is None:
            raise LedgerConflict("Unknown GameWorld workflow")
        value = dict(row)
        value["details"] = json.loads(value["details"])
        value["decision"] = None if value["decision"] is None else json.loads(value["decision"])
        return value

    def _proposal(self, connection, proposal_id):
        row = connection.execute(
            "SELECT manifest FROM gameworld_hypotheses WHERE id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise LedgerConflict("Workflow lost its supervisor proposal")
        return json.loads(row["manifest"])

    def _set_workflow(self, proposal_id, *, state=None, candidate_id=None, details=None, decision=None):
        if state is not None and state not in WORKFLOW_STATES:
            raise ValueError("Unsupported workflow state")
        with self.controller.ledger.transaction() as connection:
            current = self._workflow(connection, proposal_id)
            saved_decision = (None if current["decision"] is None else canonical(current["decision"]).decode())
            connection.execute(
                "UPDATE gameworld_workflows SET state=?,candidate_id=?,details=?,decision=? WHERE proposal_id=?",
                (state or current["state"], candidate_id if candidate_id is not None else current["candidate_id"],
                 canonical(details if details is not None else current["details"]).decode(),
                 saved_decision if decision is None else canonical(decision).decode(), proposal_id),
            )

    def start_next(self, action_id):
        if not IDENTIFIER.fullmatch(action_id):
            raise ValueError("Invalid coordinator action identity")
        proposal = self.supervisor.next()
        if proposal is None:
            return None
        action = self.supervisor.begin(proposal["id"], action_id)
        self.supervisor.provider_started(action_id, "coordinator:" + action_id)
        details = {"proposal_sha256": digest(canonical(proposal))}
        if proposal["track"] == "model":
            details["modal_allocation"] = {
                "training_micro_usd": proposal["budget"]["modal_training_micro_usd"],
                "serving_micro_usd": proposal["budget"]["modal_serving_micro_usd"],
            }
        state = "awaiting_patch" if proposal["track"] == "driver" else (
            "starting_baseline_serving" if proposal["experiment"]["objective"] == "grpo"
            else "awaiting_sft_dataset")
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_workflows WHERE proposal_id=?", (proposal["id"],)
            ).fetchone()
            if existing:
                if existing["action_id"] != action_id:
                    raise LedgerConflict("Proposal is already owned by another coordinator action")
                return self._workflow(connection, proposal["id"])
            connection.execute(
                "INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,NULL)",
                (proposal["id"], action_id, proposal["track"], proposal["id"], state, None,
                 canonical(details).decode()),
            )
            self.controller.ledger._event(connection, "gameworld_workflow_started", {
                "proposal": proposal["id"], "action": action_id, "track": proposal["track"],
            })
        if proposal["track"] == "model" and proposal["experiment"]["objective"] == "grpo":
            self._queue_baseline_serving(proposal["id"], "rollout")
        return {**action, "workflow": proposal["id"], "workflow_state": state}

    @staticmethod
    def _job_id(workflow, phase, ordinal):
        return "gw-" + digest(canonical([workflow, phase, ordinal]))[:32]

    def _queue(self, workflow, phase, rows):
        with self.controller.ledger.transaction() as connection:
            self._workflow(connection, workflow)
            inserted = 0
            for ordinal, row in enumerate(rows):
                item_id = "item-" + digest(canonical([workflow, phase, ordinal]))[:32]
                job_id = self._job_id(workflow, phase, ordinal)
                payload = {
                    "candidate": row["candidate"], "kind": row["kind"],
                    "assignment": row["assignment"], "reservations": row["reservations"],
                    "timeout_seconds": row["timeout_seconds"], "private_lease": row.get("private_lease"),
                }
                existing = connection.execute(
                    "SELECT * FROM gameworld_work_items WHERE id=?", (item_id,)
                ).fetchone()
                if existing:
                    observed = {
                        "candidate": existing["candidate"], "kind": existing["kind"],
                        "assignment": json.loads(existing["assignment"]),
                        "reservations": json.loads(existing["reservations"]),
                        "timeout_seconds": existing["timeout_seconds"],
                        "private_lease": existing["private_lease"],
                    }
                    if existing["job_id"] != job_id or observed != payload:
                        raise LedgerConflict("Queued workflow work changed after registration")
                    continue
                connection.execute(
                    "INSERT INTO gameworld_work_items "
                    "(id,workflow,phase,ordinal,job_id,candidate,kind,assignment,reservations,timeout_seconds,state,private_lease) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?)",
                    (item_id, workflow, phase, ordinal, job_id, row["candidate"], row["kind"],
                     canonical(row["assignment"]).decode(), canonical(row["reservations"]).decode(),
                     row["timeout_seconds"], row.get("private_lease")),
                )
                inserted += 1
            if inserted:
                self.controller.ledger._event(connection, "gameworld_work_queued", {
                    "workflow": workflow, "phase": phase, "jobs": inserted,
                })

    def _candidate(self, candidate_id):
        with self.controller.ledger.transaction() as connection:
            return json.loads(self.controller._candidate(connection, candidate_id)["manifest"])

    def _queue_baseline_serving(self, workflow, purpose):
        if purpose not in {"development", "rollout", "confirmation", "sealed"}:
            raise ValueError("Unsupported baseline serving purpose")
        phase = "baseline-serving-" + purpose
        baseline = self._candidate("baseline")
        current = self.workflow(workflow)
        owner = current["candidate_id"] or self.controller.snapshot()["controller"]["champion"]
        candidate = self._candidate(owner)
        identity = json.loads((self.state_root / "inputs/baseline-policy.json").read_bytes())
        if (candidate["model"]["adapter_sha256"] is not None
                or candidate["policy_sha256"] != baseline["policy_sha256"]
                or policy_digest(identity) != candidate["policy_sha256"]):
            raise LedgerConflict("Baseline policy bytes differ from the registered candidate")
        assignment = {"mode": "baseline", "policy_sha256": candidate["policy_sha256"],
                      "served_model": candidate["model"]["served_model"],
                      "generation": identity["generation"]}
        self._queue(workflow, phase, [{
            "candidate": owner, "kind": "serving", "assignment": assignment,
            "reservations": {"modal_micro_usd": self.policy["limits"]["baseline_serving_micro_usd"]},
            "timeout_seconds": self.policy["limits"]["serving_seconds"],
        }])
        current = self.workflow(workflow)
        job_id = self._job_id(workflow, phase, 0)
        self._set_workflow(workflow, details={**current["details"],
                                             "baseline_serving_job": job_id,
                                             "baseline_serving_phase": phase})
        return job_id

    def _request_baseline_stop(self, workflow, after):
        if "baseline_serving_job" not in workflow["details"]:
            raise LedgerConflict("Workflow lost its baseline serving owner")
        details = {**workflow["details"], "after_baseline_serving": after}
        self._set_workflow(workflow["proposal_id"], state="awaiting_baseline_serving_stop", details=details)

    def _queue_rollouts(self, proposal):
        parent = self._candidate(self.controller.snapshot()["controller"]["champion"])
        tasks = {task["id"]: task for task in self.controller.contract["public_splits"]["train"]["tasks"]}
        rows = []
        for task_id in proposal["experiment"]["training_tasks"]:
            if task_id not in tasks:
                raise ValueError("Proposal training task is absent from the frozen contract")
            task = tasks[task_id]
            group = "group-" + digest(canonical([proposal["id"], task_id]))[:24]
            assignment = {
                "split": "train", "task_id": task["id"], "game": task["game"], "task": task["task"],
                "seed": task["seed"], "repeat": 0, "group_id": group,
                "members": proposal["experiment"]["rollouts_per_task"],
                "max_steps": proposal["experiment"]["max_trajectory_steps"],
                "policy_sha256": parent["policy_sha256"], "driver_sha256": parent["driver_sha256"],
            }
            rows.append({"candidate": parent["id"], "kind": "rollout", "assignment": assignment,
                         "reservations": {}, "timeout_seconds": proposal["budget"]["timeout_seconds"]})
        self._queue(proposal["id"], "rollout", rows)

    def attach_driver_patch(self, action_id, patch_path):
        patch = Path(patch_path).read_bytes()
        with self.controller.ledger.transaction() as connection:
            workflow = self._workflow(connection, action_id)
            proposal = self._proposal(connection, workflow["proposal_id"])
        if workflow["track"] != "driver" or workflow["state"] != "awaiting_patch":
            raise LedgerConflict("Driver patch is not expected for this workflow")
        from fps_bench.driver_candidate import validate_patch
        patch_manifest = validate_patch(patch, self.policy["driver"]["allowed_source_prefixes"])
        if set(patch_manifest["paths"]) != set(proposal["experiment"]["target_paths"]):
            raise ValueError("Driver patch paths differ from the approved proposal")
        root = self.state_root / "workflows" / workflow["proposal_id"] / "input"
        proposal_path = write_once(root / "proposal.json", canonical(proposal))
        saved_patch = write_once(root / "candidate.patch", patch)
        details = {**workflow["details"], "proposal_path": str(proposal_path),
                   "patch_path": str(saved_patch), "patch_sha256": patch_manifest["patch_sha256"]}
        parent = self.controller.snapshot()["controller"]["champion"]
        assignment = {"pool": self.pool, "operation": "driver-candidate", "proposal_id": proposal["id"],
                      "proposal_sha256": details["proposal_sha256"],
                      "patch_sha256": details["patch_sha256"]}
        self._queue(workflow["proposal_id"], "driver-build", [{
            "candidate": parent, "kind": "driver_build", "assignment": assignment,
            "reservations": {}, "timeout_seconds": proposal["budget"]["timeout_seconds"],
        }])
        self._set_workflow(workflow["proposal_id"], state="building", details=details)
        return details

    def allocate_model_budget(self, action_id, training_micro_usd, serving_micro_usd):
        positive_integer(training_micro_usd, "training_micro_usd")
        positive_integer(serving_micro_usd, "serving_micro_usd")
        with self.controller.ledger.transaction() as connection:
            workflow = self._workflow(connection, action_id)
            proposal = self._proposal(connection, workflow["proposal_id"])
        if workflow["track"] != "model" or workflow["state"] not in {
                "collecting_rollouts", "awaiting_dataset", "awaiting_sft_dataset"}:
            raise LedgerConflict("Model budget can only be allocated before training admission")
        allocation = {"training_micro_usd": training_micro_usd, "serving_micro_usd": serving_micro_usd}
        approved = {
            "training_micro_usd": proposal["budget"]["modal_training_micro_usd"],
            "serving_micro_usd": proposal["budget"]["modal_serving_micro_usd"],
        }
        if allocation != approved or sum(allocation.values()) != proposal["budget"]["modal_micro_usd"]:
            raise BudgetRefused("Training and serving allocations differ from the approved proposal")
        previous = workflow["details"].get("modal_allocation")
        if previous is not None and previous != allocation:
            raise LedgerConflict("Model Modal allocation is immutable")
        self._set_workflow(workflow["proposal_id"], details={**workflow["details"], "modal_allocation": allocation})
        return allocation

    def _queue_evaluations(self, workflow, candidates, comparison, phase="development"):
        proposal = None
        if phase == "development":
            with self.controller.ledger.transaction() as connection:
                proposal = self._proposal(connection, workflow)
        rows = []
        for run in schedule(self.controller.contract, "development", candidates,
                            int(digest(canonical([workflow, comparison]))[:8], 16)):
            assignment = {key: run[key] for key in ("split", "task_id", "game", "task", "seed", "repeat")}
            assignment["comparison"] = comparison
            rows.append({"candidate": run["candidate"], "kind": "evaluation", "assignment": assignment,
                         "reservations": {}, "timeout_seconds": (
                             proposal["budget"]["timeout_seconds"] if proposal else 1800)})
        if proposal is not None and len(rows) != proposal["budget"]["desktop_episodes"] * 2:
            raise ValueError("Paired evaluation queue differs from the proposal episode bound")
        self._queue(workflow, phase, rows)

    def _queue_private_evaluations(self, workflow, lease, timeout_seconds):
        rows = [{
            "candidate": run["candidate"], "kind": "evaluation", "assignment": run["assignment"],
            "reservations": {}, "timeout_seconds": timeout_seconds, "private_lease": lease["id"],
        } for run in lease["schedule"]]
        self._queue(workflow, lease["split"], rows)

    def _private_lease(self, lease_id):
        with self.controller.ledger.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM private_split_leases WHERE id=?", (lease_id,)
            ).fetchone()
            if row is None:
                raise LedgerConflict("Workflow lost its protected split lease")
            return self.controller._lease_result(row, include_schedule=True)

    def start_confirmation(self, action_id, lease_id, randomization_seed, duration_seconds=18000):
        workflow = self.workflow(action_id)
        expected = "nominate_joint" if workflow["track"] == "joint" else "nominate"
        allowed_state = "qualified_serving_live" if workflow["track"] in ("model", "joint") else "complete"
        if (workflow["track"] not in ("driver", "model", "joint")
                or workflow["state"] != allowed_state or not workflow["decision"]
                or workflow["decision"].get("decision") != expected or not workflow["candidate_id"]):
            raise LedgerConflict("Confirmation requires a qualified candidate and any live model serving")
        if workflow["track"] == "driver":
            details = {**workflow["details"], "baseline_continuation": "confirmation",
                       "private_request": {"lease_id": lease_id, "randomization_seed": randomization_seed,
                                           "duration_seconds": duration_seconds}}
            self._set_workflow(workflow["proposal_id"], state="starting_baseline_serving", details=details)
            self._queue_baseline_serving(workflow["proposal_id"], "confirmation")
        else:
            lease = self.controller.issue_private_split_lease(
                lease_id, workflow["candidate_id"], "confirmation", randomization_seed, duration_seconds)
            timeout = min(1800, max(1, lease["expires"] - lease["issued"]))
            details = {**workflow["details"], "confirmation_lease": lease["id"],
                       "confirmation_schedule_sha256": lease["schedule_hash"]}
            self._queue_private_evaluations(workflow["proposal_id"], lease, timeout)
            self._set_workflow(workflow["proposal_id"], state="confirming", details=details)
        return self.workflow(workflow["proposal_id"])

    def start_sealed(self, lease_id, randomization_seed, duration_seconds=18000):
        champion = self.controller.snapshot()["controller"]["champion"]
        candidate = self._candidate(champion)
        needs_baseline = candidate["model"]["adapter_sha256"] is None
        serving_owner = None
        if candidate["change_class"] in ("model", "joint"):
            model_candidate = (candidate["components"]["model"] if candidate["change_class"] == "joint"
                               else champion)
            with self.controller.ledger.transaction() as connection:
                row = connection.execute(
                    "SELECT proposal_id FROM gameworld_workflows WHERE track='model' AND candidate_id=?",
                    (model_candidate,),
                ).fetchone()
            if row is None or self.workflow(row["proposal_id"])["state"] != "qualified_serving_live":
                raise BudgetRefused("Sealed model evaluation requires its attested endpoint to remain live")
            serving_owner = row["proposal_id"]
        workflow_id = "sealed-" + digest(canonical(lease_id))[:24]
        request = {"lease_id": lease_id, "randomization_seed": randomization_seed,
                   "duration_seconds": duration_seconds}
        lease = None if needs_baseline else self.controller.issue_private_split_lease(
            lease_id, champion, "sealed", randomization_seed, duration_seconds)
        details = ({"baseline_continuation": "sealed", "private_request": request}
                   if needs_baseline else {
                       "sealed_lease": lease["id"], "sealed_schedule_sha256": lease["schedule_hash"]})
        if serving_owner is not None:
            details["serving_owner"] = serving_owner
        if candidate["change_class"] == "joint":
            with self.controller.ledger.transaction() as connection:
                joint = connection.execute(
                    "SELECT proposal_id FROM gameworld_workflows WHERE track='joint' AND candidate_id=?", (champion,)
                ).fetchone()
            if joint is None or self.workflow(joint["proposal_id"])["state"] != "qualified_serving_live":
                raise BudgetRefused("Sealed joint evaluation requires its qualified workflow to remain live")
            details["joint_workflow"] = joint["proposal_id"]
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_workflows WHERE proposal_id=?", (workflow_id,)
            ).fetchone()
            if existing:
                current = self._workflow(connection, workflow_id)
                request_changed = (needs_baseline
                                   and current["details"].get("private_request") != request)
                if (current["candidate_id"] != champion or request_changed
                        or not needs_baseline and current["details"] != details):
                    raise LedgerConflict("Sealed workflow identity changed")
            else:
                initial_state = "starting_baseline_serving" if needs_baseline else "sealed_evaluating"
                connection.execute(
                    "INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,NULL)",
                    (workflow_id, workflow_id, "sealed", lease_id if needs_baseline else lease["comparison"], initial_state,
                     champion, canonical(details).decode()),
                )
                self.controller.ledger._event(connection, "gameworld_sealed_workflow_started", {
                    "workflow": workflow_id, "candidate": champion, "lease": lease_id,
                })
        if needs_baseline:
            self._queue_baseline_serving(workflow_id, "sealed")
        else:
            timeout = min(1800, max(1, lease["expires"] - lease["issued"]))
            self._queue_private_evaluations(workflow_id, lease, timeout)
        return self.workflow(workflow_id)

    def promote(self, action_id, receipt):
        workflow = self.workflow(action_id)
        if not workflow["candidate_id"]:
            raise LedgerConflict("Workflow has no candidate to promote")
        return self.controller.promote_candidate(workflow["candidate_id"], receipt)

    def rollback(self, reason):
        return self.controller.rollback_champion(reason)

    def abandon_lease(self, lease_id, reason):
        result = self.controller.abandon_private_split_lease(lease_id, reason)
        with self.controller.ledger.transaction() as connection:
            row = next((workflow for workflow in connection.execute(
                "SELECT proposal_id,details FROM gameworld_workflows")
                        if lease_id in (json.loads(workflow["details"]).get("confirmation_lease"),
                                        json.loads(workflow["details"]).get("sealed_lease"))), None)
        if row is not None:
            workflow = self.workflow(row["proposal_id"])
            state = "awaiting_serving_stop" if workflow["track"] in ("model", "joint") else "rejected"
            self._set_workflow(row["proposal_id"], state=state, decision=result)
            if workflow["track"] == "joint":
                owner = workflow["details"]["serving_owner"]
                model = self.workflow(owner)
                self._set_workflow(owner, state="awaiting_serving_stop", decision=model["decision"])
        return result

    def admit_ready(self, maximum=2):
        positive_integer(maximum, "maximum")
        admitted = []
        with self.controller.ledger.transaction() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM gameworld_work_items WHERE state='pending' ORDER BY workflow,phase,ordinal"
            )]
        for row in rows:
            if len(admitted) >= maximum:
                break
            try:
                job = self.controller.admit_job(
                    row["job_id"], row["candidate"], row["kind"], json.loads(row["assignment"]),
                    json.loads(row["reservations"]), row["timeout_seconds"], row["private_lease"])
            except BudgetRefused as error:
                if "concurrency" in str(error):
                    break
                raise
            with self.controller.ledger.transaction() as connection:
                connection.execute("UPDATE gameworld_work_items SET state='admitted' WHERE id=?", (row["id"],))
            admitted.append({"job_id": row["job_id"], "kind": row["kind"], "state": job["state"]})
        return admitted

    def sync(self):
        changed = []
        with self.controller.ledger.transaction() as connection:
            items = [dict(row) for row in connection.execute(
                "SELECT * FROM gameworld_work_items WHERE state IN ('admitted','live') ORDER BY workflow,phase,ordinal"
            )]
            for item in items:
                job = self.controller._job(connection, item["job_id"])
                state = item["state"]
                if item["kind"] == "serving" and job["state"] == "cleanup_pending" and job["result"]:
                    state = "live"
                elif job["state"] in ("billing_pending", "cleaned"):
                    if job["result"] is None:
                        state = "failed"
                    else:
                        result = json.loads(job["result"])["result"]
                        state = ("complete" if item["kind"] == "evaluation"
                                 or result.get("status") == "complete" else "failed")
                if state != item["state"]:
                    connection.execute("UPDATE gameworld_work_items SET state=? WHERE id=?", (state, item["id"]))
                    changed.append({"job_id": item["job_id"], "state": state})
        return changed

    def prepare_training_dataset(self, action_id):
        self.sync()
        with self.controller.ledger.transaction() as connection:
            workflow = self._workflow(connection, action_id)
            proposal = self._proposal(connection, workflow["proposal_id"])
            items = [dict(row) for row in connection.execute(
                "SELECT * FROM gameworld_work_items WHERE workflow=? AND phase='rollout' ORDER BY job_id",
                (workflow["proposal_id"],),
            )]
        if workflow["track"] != "model" or workflow["state"] not in {
                "collecting_rollouts", "awaiting_dataset"}:
            raise LedgerConflict("Model workflow is not ready to authenticate rollout data")
        if not items or any(item["state"] != "complete" for item in items):
            raise LedgerConflict("Every admitted rollout must complete before dataset registration")
        allocation = workflow["details"].get("modal_allocation")
        if allocation is None:
            raise BudgetRefused("Model Modal allocation is required before training admission")
        if self.registry is None:
            self.registry = GameWorldTrainingRegistry(
                self.controller, self.policy_path, self.catalog_path)
        job_ids = sorted(item["job_id"] for item in items)
        for job_id in job_ids:
            root = self.state_root / "fleet" / job_id
            receipt = json.loads((root / "artifact-receipt.json").read_bytes())
            self.registry.register_rollout(job_id, root, receipt)
        exported = self.registry.export(job_ids, self.state_root / "datasets" / workflow["proposal_id"])
        return self._queue_training(workflow, proposal, exported, job_ids)

    def _queue_training(self, workflow, proposal, dataset, source_jobs):
        parent = self._candidate(self.controller.snapshot()["controller"]["champion"])
        assignment = {
            "split": "train", "tasks": sorted(proposal["experiment"]["training_tasks"]),
            "dataset_sha256": dataset["dataset_sha256"], "objective": proposal["experiment"]["objective"],
            "policy_sha256": parent["policy_sha256"], "driver_sha256": parent["driver_sha256"],
            "steps": proposal["experiment"]["optimizer_steps"],
        }
        allocation = workflow["details"]["modal_allocation"]
        self._queue(workflow["proposal_id"], "training", [{
            "candidate": parent["id"], "kind": "training", "assignment": assignment,
            "reservations": {"modal_micro_usd": allocation["training_micro_usd"]},
            "timeout_seconds": proposal["budget"]["timeout_seconds"],
        }])
        details = {**workflow["details"], "dataset_sha256": dataset["dataset_sha256"],
                   "dataset_root": dataset["root"], "source_jobs": source_jobs}
        self._set_workflow(workflow["proposal_id"], state="training", details=details)
        return dataset

    def attach_sft_dataset(self, action_id, dataset_root, dataset_sha256, source_receipt_path):
        with self.controller.ledger.transaction() as connection:
            workflow = self._workflow(connection, action_id)
            proposal = self._proposal(connection, workflow["proposal_id"])
        if workflow["track"] != "model" or workflow["state"] != "awaiting_sft_dataset":
            raise LedgerConflict("SFT demonstrations are not expected for this workflow")
        if "modal_allocation" not in workflow["details"]:
            raise BudgetRefused("Model Modal allocation is required before SFT training admission")
        if self.registry is None:
            self.registry = GameWorldTrainingRegistry(
                self.controller, self.policy_path, self.catalog_path)
        parent = self.controller.snapshot()["controller"]["champion"]
        source_receipt = json.loads(Path(source_receipt_path).read_bytes())
        registered = self.registry.register_sft(
            parent, dataset_root, dataset_sha256, proposal["experiment"]["training_tasks"], source_receipt)
        return self._queue_training(workflow, proposal, registered, [])

    def _items(self, workflow, phase=None):
        with self.controller.ledger.transaction() as connection:
            query = "SELECT * FROM gameworld_work_items WHERE workflow=?"
            values = [workflow]
            if phase is not None:
                query += " AND phase=?"
                values.append(phase)
            query += " ORDER BY phase,ordinal"
            rows = [dict(row) for row in connection.execute(query, values)]
        for row in rows:
            row["assignment"] = json.loads(row["assignment"])
            row["reservations"] = json.loads(row["reservations"])
        return rows

    def _result(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = self.controller._job(connection, job_id)
            return None if job["result"] is None else json.loads(job["result"])

    def _finalize(self, workflow, candidate_id, qualified, evidence):
        artifact = digest(canonical(evidence))
        self.supervisor.finish(workflow["action_id"], {
            "candidate_id": candidate_id, "qualified": qualified,
            "artifact_sha256": artifact, "metrics": evidence,
        })
        self.supervisor.cleanup_confirmed(
            workflow["action_id"], "coordinator-workflow:" + artifact)
        self._set_workflow(workflow["proposal_id"], state="complete" if qualified else "rejected",
                           candidate_id=candidate_id, decision=evidence)

    def emit_evaluation(self, workflow, candidate_id, decision, phase):
        telemetry = self.supervisor.telemetry
        if telemetry is None:
            return None
        try:
            evaluation_split = phase if phase in ("confirmation", "sealed") else "development"
            with self.controller.ledger.transaction() as connection:
                rows = []
                for job in connection.execute(
                        "SELECT specification,result FROM jobs WHERE kind='evaluation'"):
                    assignment = json.loads(job["specification"])["assignment"]
                    if (assignment.get("comparison") == workflow["comparison"]
                            and assignment.get("split") == evaluation_split and job["result"]):
                        rows.append(json.loads(job["result"])["result"])
            complete = [row for row in rows if row.get("status") == "complete"]
            values = {
                "gameworld_eval_completed_episodes": len(complete),
                "gameworld_eval_failed_episodes": len(rows) - len(complete),
                "gameworld_eval_seconds": sum(row.get("seconds", 0) for row in complete),
            }
            candidate_rows = [row for row in complete if row.get("candidate") == candidate_id]
            if candidate_rows:
                values["gameworld_eval_success_rate"] = sum(row["success"] for row in candidate_rows) / len(candidate_rows)
                progress = [row.get("progress") for row in candidate_rows
                            if type(row.get("progress")) in (int, float)]
                if progress:
                    values["gameworld_eval_mean_progress"] = sum(progress) / len(progress)
            candidate = self._candidate(candidate_id)
            telemetry.record(
                "evaluation-" + digest(canonical([workflow["comparison"], candidate_id, phase]))[:32],
                "gameworld-eval",
                {"experiment": candidate_id, "phase": phase, "split": evaluation_split,
                 "change_class": candidate["change_class"],
                 "outcome": decision.get("decision", decision.get("status", "unknown"))},
                values,
            )
            return telemetry.flush()
        except Exception as error:
            return {"metrics": False, "logs": False, "errors": [{"type": type(error).__name__}]}

    def advance(self, action_id=None):
        self.sync()
        with self.controller.ledger.transaction() as connection:
            if action_id is None:
                workflows = [self._workflow(connection, row["proposal_id"]) for row in connection.execute(
                    "SELECT proposal_id FROM gameworld_workflows WHERE state NOT IN ('complete','rejected') "
                    "ORDER BY rowid"
                )]
            else:
                workflows = [self._workflow(connection, action_id)]
        transitions = []
        for workflow in workflows:
            proposal_id, state = workflow["proposal_id"], workflow["state"]
            if state == "starting_baseline_serving":
                items = self._items(proposal_id, workflow["details"]["baseline_serving_phase"])
                if items and items[0]["state"] == "failed":
                    continuation = workflow["details"].get("baseline_continuation")
                    decision = {"phase": "baseline-serving", "failed": True}
                    if continuation in ("confirmation", "sealed"):
                        lease_id = workflow["details"].get(continuation + "_lease")
                        if lease_id is not None:
                            self.controller.abandon_private_split_lease(lease_id, "baseline serving failed")
                        self._set_workflow(proposal_id, state="rejected", decision=decision)
                    else:
                        self._finalize(workflow, workflow["candidate_id"] or proposal_id, False, decision)
                    transitions.append({"workflow": proposal_id, "state": "rejected"})
                elif items and items[0]["state"] == "live":
                    continuation = workflow["details"].get("baseline_continuation")
                    if continuation in ("confirmation", "sealed"):
                        request = workflow["details"].get("private_request")
                        if not isinstance(request, dict):
                            raise LedgerConflict("Baseline serving continuation lost its private lease request")
                        lease = self.controller.issue_private_split_lease(
                            request["lease_id"], workflow["candidate_id"], continuation,
                            request["randomization_seed"], request["duration_seconds"])
                        timeout = min(1800, max(1, lease["expires"] - int(time.time())))
                        self._queue_private_evaluations(proposal_id, lease, timeout)
                        next_state = "confirming" if continuation == "confirmation" else "sealed_evaluating"
                        details = {**workflow["details"], continuation + "_lease": lease["id"],
                                   continuation + "_schedule_sha256": lease["schedule_hash"]}
                        self._set_workflow(proposal_id, state=next_state, details=details)
                    elif workflow["track"] == "driver":
                        self._queue_evaluations(
                            proposal_id, ["baseline", workflow["candidate_id"]], workflow["comparison"])
                        self._set_workflow(proposal_id, state="evaluating")
                        next_state = "evaluating"
                    else:
                        with self.controller.ledger.transaction() as connection:
                            proposal = self._proposal(connection, proposal_id)
                        self._queue_rollouts(proposal)
                        self._set_workflow(proposal_id, state="collecting_rollouts")
                        next_state = "collecting_rollouts"
                    transitions.append({"workflow": proposal_id, "state": next_state})
            elif state == "building":
                items = self._items(proposal_id, "driver-build")
                if items and items[0]["state"] in ("complete", "failed"):
                    envelope = self._result(items[0]["job_id"])
                    result = {} if envelope is None else envelope["result"]
                    if items[0]["state"] == "failed" or result.get("status") != "complete":
                        self._finalize(workflow, proposal_id, False, {"phase": "driver-build", "result": result})
                        transitions.append({"workflow": proposal_id, "state": "rejected"})
                        continue
                    candidate_id = result["candidate_id"]
                    self._candidate(candidate_id)
                    self._set_workflow(proposal_id, state="starting_baseline_serving", candidate_id=candidate_id)
                    self._queue_baseline_serving(proposal_id, "development")
                    transitions.append({"workflow": proposal_id, "state": "starting_baseline_serving"})
            elif state == "collecting_rollouts":
                items = self._items(proposal_id, "rollout")
                if any(item["state"] == "failed" for item in items):
                    decision = {"phase": "rollout", "failed": True}
                    self._request_baseline_stop(workflow, {
                        "state": "rejected", "candidate_id": proposal_id, "qualified": False,
                        "decision": decision})
                    transitions.append({"workflow": proposal_id, "state": "awaiting_baseline_serving_stop"})
                elif items and all(item["state"] == "complete" for item in items):
                    self._request_baseline_stop(workflow, {"state": "awaiting_dataset"})
                    transitions.append({"workflow": proposal_id, "state": "awaiting_baseline_serving_stop"})
            elif state == "training":
                items = self._items(proposal_id, "training")
                if items and items[0]["state"] in ("complete", "failed"):
                    envelope = self._result(items[0]["job_id"])
                    result = {} if envelope is None else envelope["result"]
                    if items[0]["state"] == "failed" or result.get("status") != "complete":
                        self._finalize(workflow, proposal_id, False, {"phase": "training", "result": result})
                        transitions.append({"workflow": proposal_id, "state": "rejected"})
                        continue
                    with self.controller.ledger.transaction() as connection:
                        proposal = self._proposal(connection, proposal_id)
                    allocation = workflow["details"]["modal_allocation"]
                    candidate_id = "model-" + digest(canonical([proposal_id, result["adapter_manifest_sha256"]]))[:24]
                    baseline_policy = json.loads((self.state_root / "inputs/baseline-policy.json").read_bytes())
                    assignment = {
                        "training_job": items[0]["job_id"],
                        "adapter_sha256": result["adapter_manifest_sha256"],
                        "served_model": candidate_id, "hypothesis": proposal["hypothesis"],
                        "comparison": workflow["comparison"], "generation": baseline_policy["generation"],
                    }
                    self._queue(proposal_id, "serving", [{
                        "candidate": items[0]["candidate"], "kind": "serving", "assignment": assignment,
                        "reservations": {"modal_micro_usd": allocation["serving_micro_usd"]},
                        "timeout_seconds": self.policy["limits"]["serving_seconds"],
                    }])
                    self._set_workflow(proposal_id, state="serving", candidate_id=candidate_id)
                    transitions.append({"workflow": proposal_id, "state": "serving"})
            elif state == "serving":
                items = self._items(proposal_id, "serving")
                if items and items[0]["state"] == "failed":
                    self._finalize(workflow, workflow["candidate_id"] or proposal_id, False,
                                   {"phase": "serving", "failed": True})
                    transitions.append({"workflow": proposal_id, "state": "rejected"})
                elif items and items[0]["state"] == "live":
                    self._candidate(workflow["candidate_id"])
                    self._queue_evaluations(
                        proposal_id, ["baseline", workflow["candidate_id"]], workflow["comparison"])
                    details = {**workflow["details"], "serving_job": items[0]["job_id"],
                               "policy_path": str(self.state_root / "serving" / items[0]["job_id"] / "policy.json")}
                    self._set_workflow(proposal_id, state="evaluating", details=details)
                    transitions.append({"workflow": proposal_id, "state": "evaluating"})
            elif state == "evaluating":
                phase = "factorial" if workflow["track"] == "joint" else "development"
                items = self._items(proposal_id, phase)
                if items and all(item["state"] == "complete" for item in items):
                    if workflow["track"] == "joint":
                        decision = self.controller.decide_factorial(workflow["candidate_id"])
                        self.emit_evaluation(workflow, workflow["candidate_id"], decision, "factorial")
                        if decision["decision"] == "nominate_joint":
                            self._set_workflow(proposal_id, state="qualified_serving_live", decision=decision)
                        else:
                            self._set_workflow(proposal_id, state="awaiting_serving_stop", decision=decision)
                            owner = workflow["details"]["serving_owner"]
                            with self.controller.ledger.transaction() as connection:
                                model = self._workflow(connection, owner)
                            self._set_workflow(owner, state="awaiting_serving_stop", decision=model["decision"])
                    else:
                        decision = self.controller.decide_development(workflow["candidate_id"])
                        self.emit_evaluation(workflow, workflow["candidate_id"], decision, "paired")
                        if workflow["track"] == "driver":
                            qualified = decision["decision"] == "nominate"
                            self._request_baseline_stop(workflow, {
                                "state": "complete" if qualified else "rejected",
                                "candidate_id": workflow["candidate_id"], "qualified": qualified,
                                "decision": decision})
                        elif decision["decision"] == "nominate":
                            self._set_workflow(proposal_id, state="qualified_serving_live", decision=decision)
                        else:
                            self._set_workflow(proposal_id, state="awaiting_serving_stop", decision=decision)
                    transitions.append({"workflow": proposal_id, "state": self.workflow(proposal_id)["state"]})
            elif state == "awaiting_baseline_serving_stop":
                serving = self._items(proposal_id, workflow["details"]["baseline_serving_phase"])
                if serving and serving[0]["state"] == "complete":
                    after = workflow["details"].get("after_baseline_serving")
                    if not isinstance(after, dict) or "state" not in after:
                        raise LedgerConflict("Baseline serving stop lost its continuation")
                    if after["state"] == "awaiting_dataset":
                        self._set_workflow(proposal_id, state="awaiting_dataset")
                    elif after.get("finalize", True):
                        self._finalize(workflow, after["candidate_id"], after["qualified"], after["decision"])
                    else:
                        self._set_workflow(proposal_id, state=after["state"],
                                           candidate_id=after["candidate_id"], decision=after["decision"])
                    transitions.append({"workflow": proposal_id, "state": after["state"]})
            elif state == "confirming":
                items = self._items(proposal_id, "confirmation")
                if items and all(item["state"] == "complete" for item in items):
                    decision = self.controller.decide_confirmation(workflow["details"]["confirmation_lease"])
                    self.emit_evaluation(workflow, workflow["candidate_id"], decision, "confirmation")
                    if workflow["track"] == "driver":
                        qualified = decision["decision"] == "confirmation_pass"
                        self._request_baseline_stop(workflow, {
                            "state": "complete" if qualified else "rejected",
                            "candidate_id": workflow["candidate_id"], "qualified": qualified,
                            "decision": decision, "finalize": False})
                    else:
                        if decision["decision"] == "confirmation_pass":
                            self._set_workflow(proposal_id, state="qualified_serving_live", decision=decision)
                        else:
                            self._set_workflow(proposal_id, state="awaiting_serving_stop", decision=decision)
                        if workflow["track"] == "joint" and decision["decision"] != "confirmation_pass":
                            owner = workflow["details"]["serving_owner"]
                            with self.controller.ledger.transaction() as connection:
                                model = self._workflow(connection, owner)
                            self._set_workflow(owner, state="awaiting_serving_stop", decision=model["decision"])
                    transitions.append({"workflow": proposal_id, "state": self.workflow(proposal_id)["state"]})
            elif state == "sealed_evaluating":
                items = self._items(proposal_id, "sealed")
                if items and all(item["state"] == "complete" for item in items):
                    report = self.controller.complete_sealed_evaluation(workflow["details"]["sealed_lease"])
                    self.emit_evaluation(workflow, workflow["candidate_id"], report, "sealed")
                    if "baseline_serving_job" in workflow["details"]:
                        self._request_baseline_stop(workflow, {
                            "state": "complete", "candidate_id": workflow["candidate_id"],
                            "qualified": True, "decision": report, "finalize": False})
                        transitions.append({"workflow": proposal_id,
                                            "state": "awaiting_baseline_serving_stop"})
                    else:
                        self._set_workflow(proposal_id, state="complete", decision=report)
                        serving_owner = workflow["details"].get("serving_owner")
                        if serving_owner is not None:
                            owner = self.workflow(serving_owner)
                            self._set_workflow(serving_owner, state="awaiting_serving_stop", decision=owner["decision"])
                        joint_workflow = workflow["details"].get("joint_workflow")
                        if joint_workflow is not None:
                            joint = self.workflow(joint_workflow)
                            self._set_workflow(joint_workflow, state="awaiting_serving_stop", decision=joint["decision"])
                        transitions.append({"workflow": proposal_id, "state": "complete"})
            elif state == "awaiting_serving_stop":
                if workflow["track"] == "joint":
                    owner = workflow["details"]["serving_owner"]
                    serving = self._items(owner, "serving")
                    if serving and serving[0]["state"] == "complete":
                        with self.controller.ledger.transaction() as connection:
                            model = self._workflow(connection, owner)
                        self._finalize(model, model["candidate_id"], True, model["decision"])
                        qualified = bool(workflow["decision"] and workflow["decision"].get("decision")
                                         in ("nominate_joint", "confirmation_pass"))
                        self._set_workflow(proposal_id, state="complete" if qualified else "rejected")
                        transitions.append({"workflow": proposal_id,
                                            "state": "complete" if qualified else "rejected"})
                else:
                    serving = self._items(proposal_id, "serving")
                    if serving and serving[0]["state"] == "complete":
                        qualified = bool(workflow["decision"] and workflow["decision"].get("decision")
                                         in ("nominate", "confirmation_pass"))
                        self._finalize(workflow, workflow["candidate_id"], qualified,
                                       workflow["decision"] or {"phase": "serving-stop"})
                        transitions.append({"workflow": proposal_id,
                                            "state": "complete" if qualified else "rejected"})
        return transitions

    def workflow(self, action_or_proposal):
        with self.controller.ledger.transaction() as connection:
            return self._workflow(connection, action_or_proposal)

    def start_joint(self, driver_action, model_action):
        with self.controller.ledger.transaction() as connection:
            driver = self._workflow(connection, driver_action)
            model = self._workflow(connection, model_action)
        if (driver["track"] != "driver" or driver["state"] != "complete"
                or not driver["decision"] or driver["decision"].get("decision") != "nominate"
                or model["track"] != "model" or model["state"] != "qualified_serving_live"):
            raise LedgerConflict("Joint evaluation requires qualified isolated driver and live model candidates")
        driver_manifest = self._candidate(driver["candidate_id"])
        model_manifest = self._candidate(model["candidate_id"])
        comparison = "factorial-" + digest(canonical([driver["proposal_id"], model["proposal_id"]]))[:24]
        joint_id = "joint-" + digest(canonical([driver_manifest, model_manifest]))[:24]
        joint = {
            **{key: driver_manifest[key] for key in (
                "contract_hash", "image", "driver_sha256", "patch_sha256")},
            "id": joint_id, "parent": driver_manifest["parent"], "change_class": "joint",
            "hypothesis": "Qualified driver and model candidates have a positive interaction.",
            "comparison": comparison, "policy_sha256": model_manifest["policy_sha256"],
            "model": model_manifest["model"],
            "components": {"driver": driver_manifest["id"], "model": model_manifest["id"]},
        }
        self.controller.register_candidate(joint)
        details = {"driver_workflow": driver["proposal_id"], "model_workflow": model["proposal_id"],
                   "serving_owner": model["proposal_id"]}
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_workflows WHERE proposal_id=?", (joint_id,)
            ).fetchone()
            if existing:
                current = self._workflow(connection, joint_id)
                if current["candidate_id"] != joint_id or current["details"] != details:
                    raise LedgerConflict("Joint workflow identity changed")
                return current
            connection.execute(
                "INSERT INTO gameworld_workflows VALUES (?,?,?,?,?,?,?,NULL)",
                (joint_id, joint_id, "joint", comparison, "evaluating", joint_id,
                 canonical(details).decode()),
            )
        self._queue_evaluations(
            joint_id, [joint["parent"], driver_manifest["id"], model_manifest["id"], joint_id],
            comparison, phase="factorial")
        return self.workflow(joint_id)

    def close_serving(self, action_id):
        workflow = self.workflow(action_id)
        if workflow["state"] != "qualified_serving_live" or workflow["track"] not in ("model", "joint"):
            raise LedgerConflict("Only a qualified live model or joint workflow can stop serving")
        self._set_workflow(workflow["proposal_id"], state="awaiting_serving_stop")
        if workflow["track"] == "joint":
            owner = workflow["details"]["serving_owner"]
            model = self.workflow(owner)
            self._set_workflow(owner, state="awaiting_serving_stop", decision=model["decision"])
        return self.workflow(workflow["proposal_id"])

    def close_model(self, action_id):
        return self.close_serving(action_id)

    def dispatchable(self):
        return [row for row in self.runnable() if row["state"] == "reserved"]

    def runnable(self):
        with self.controller.ledger.transaction() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT q.workflow,q.phase,q.job_id,q.kind,q.assignment,q.reservations,j.state "
                "FROM gameworld_work_items q JOIN jobs j ON j.id=q.job_id "
                "WHERE q.state='admitted' AND j.state IN ('reserved','dispatching','running','cleanup_pending') "
                "ORDER BY q.workflow,q.phase,q.ordinal"
            )]
        for row in rows:
            row["assignment"] = json.loads(row["assignment"])
            row["reservations"] = json.loads(row["reservations"])
        return rows

    def required_actions(self):
        actions = []
        with self.controller.ledger.transaction() as connection:
            workflows = [self._workflow(connection, row["proposal_id"]) for row in connection.execute(
                "SELECT proposal_id FROM gameworld_workflows WHERE state NOT IN ('complete','rejected') ORDER BY rowid"
            )]
        for workflow in workflows:
            if workflow["state"] == "awaiting_patch":
                actions.append({"workflow": workflow["proposal_id"], "action": "attach-driver-patch"})
            elif workflow["state"] == "awaiting_dataset":
                actions.append({"workflow": workflow["proposal_id"], "action": "register-training-dataset"})
            elif workflow["state"] == "awaiting_sft_dataset":
                actions.append({"workflow": workflow["proposal_id"],
                                "action": "attach-authenticated-sft-dataset"})
            elif workflow["state"] == "qualified_serving_live":
                action = ("start-confirmation-or-stop-serving" if workflow["track"] == "joint"
                          else "start-joint-or-confirmation-or-stop-serving")
                actions.append({"workflow": workflow["proposal_id"], "action": action})
            elif workflow["state"] == "awaiting_serving_stop":
                owner = workflow["details"].get("serving_owner", workflow["proposal_id"])
                actions.append({"workflow": workflow["proposal_id"], "action": "terminate-serving", "owner": owner})
            elif workflow["state"] == "awaiting_baseline_serving_stop":
                actions.append({"workflow": workflow["proposal_id"], "action": "terminate-serving",
                                "owner": workflow["proposal_id"],
                                "job_id": workflow["details"]["baseline_serving_job"]})
        actions.extend({"workflow": row["workflow"], "job_id": row["job_id"],
                        "action": ("dispatch-" if row["state"] == "reserved" else "resume-") + row["kind"]}
                       for row in self.runnable())
        with self.controller.ledger.transaction() as connection:
            completed_drivers = [self._workflow(connection, row["proposal_id"]) for row in connection.execute(
                "SELECT proposal_id FROM gameworld_workflows WHERE track='driver' AND state='complete' ORDER BY rowid"
            )]
        actions.extend({"workflow": row["proposal_id"], "action": "start-confirmation"}
                       for row in completed_drivers
                       if row["decision"] and row["decision"].get("decision") == "nominate")
        controller = self.controller.snapshot()
        actions.extend({"candidate": row["id"], "action": "promote-confirmed-candidate"}
                       for row in controller["candidates"] if row["state"] == "confirmed")
        active_promotion = next((row for row in reversed(controller["promotions"])
                                 if row["state"] == "active"), None)
        if active_promotion is not None:
            actions.append({"candidate": active_promotion["candidate"], "action": "rollback-available"})
        now = int(time.time())
        actions.extend({"lease": row["id"], "action": "abandon-expired-private-lease"}
                       for row in controller["private_split_leases"]
                       if row["state"] in ("issued", "active") and row["expires"] <= now)
        return actions

    def snapshot(self):
        with self.controller.ledger.transaction() as connection:
            workflows = [dict(row) for row in connection.execute(
                "SELECT * FROM gameworld_workflows ORDER BY rowid"
            )] if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gameworld_workflows'"
            ).fetchone() else []
            items = [dict(row) for row in connection.execute(
                "SELECT workflow,phase,state,COUNT(*) AS jobs FROM gameworld_work_items "
                "GROUP BY workflow,phase,state ORDER BY workflow,phase,state"
            )] if workflows else []
        for workflow in workflows:
            workflow["details"] = json.loads(workflow["details"])
            workflow["decision"] = None if workflow["decision"] is None else json.loads(workflow["decision"])
        return {"workflows": workflows, "queue": items, "required_actions": self.required_actions(),
                "supervisor": self.supervisor.snapshot(), "controller": self.controller.snapshot()}


def load_json(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=[
        "initialize", "status", "register", "start", "attach-patch", "allocate", "admit",
        "advance", "dataset", "attach-sft", "joint", "close-model", "close-serving", "confirm", "sealed",
        "promote", "rollback", "abandon-lease",
    ])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--private-splits", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--baseline-policy", type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--telemetry", type=Path)
    parser.add_argument("--pool", default="gameworld-autoresearch")
    parser.add_argument("--campaign")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--action")
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--training-micro-usd", type=int)
    parser.add_argument("--serving-micro-usd", type=int)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--dataset-sha256")
    parser.add_argument("--source-receipt", type=Path)
    parser.add_argument("--maximum", type=int, default=2)
    parser.add_argument("--driver-action")
    parser.add_argument("--model-action")
    parser.add_argument("--lease-id")
    parser.add_argument("--randomization-seed", type=int)
    parser.add_argument("--duration-seconds", type=int, default=18000)
    parser.add_argument("--receipt")
    parser.add_argument("--reason")
    args = parser.parse_args()
    coordinator = GameWorldCoordinator(
        args.database, args.contract, args.contract_sha256, args.baseline, args.state_root,
        args.policy, args.catalog, args.telemetry, args.pool, private_splits=args.private_splits)
    if args.operation == "initialize":
        if not args.campaign or not args.baseline_policy:
            parser.error("initialize requires --campaign and --baseline-policy")
        result = coordinator.initialize(args.campaign, args.baseline_policy)
    elif args.operation == "register":
        if not args.proposal:
            parser.error("register requires --proposal")
        result = coordinator.register(load_json(args.proposal))
    elif args.operation == "start":
        if not args.action:
            parser.error("start requires --action")
        result = coordinator.start_next(args.action)
    elif args.operation == "attach-patch":
        if not args.action or not args.patch:
            parser.error("attach-patch requires --action and --patch")
        result = coordinator.attach_driver_patch(args.action, args.patch)
    elif args.operation == "allocate":
        if not args.action or args.training_micro_usd is None or args.serving_micro_usd is None:
            parser.error("allocate requires --action and both Modal allocations")
        result = coordinator.allocate_model_budget(
            args.action, args.training_micro_usd, args.serving_micro_usd)
    elif args.operation == "admit":
        result = coordinator.admit_ready(args.maximum)
    elif args.operation == "advance":
        result = coordinator.advance(args.action)
    elif args.operation == "dataset":
        if not args.action:
            parser.error("dataset requires --action")
        result = coordinator.prepare_training_dataset(args.action)
    elif args.operation == "attach-sft":
        if not args.action or not args.dataset_root or not args.dataset_sha256 or not args.source_receipt:
            parser.error("attach-sft requires --action, --dataset-root, --dataset-sha256 and --source-receipt")
        result = coordinator.attach_sft_dataset(
            args.action, args.dataset_root, args.dataset_sha256, args.source_receipt)
    elif args.operation == "joint":
        if not args.driver_action or not args.model_action:
            parser.error("joint requires --driver-action and --model-action")
        result = coordinator.start_joint(args.driver_action, args.model_action)
    elif args.operation == "close-model":
        if not args.action:
            parser.error("close-model requires --action")
        result = coordinator.close_model(args.action)
    elif args.operation == "close-serving":
        if not args.action:
            parser.error("close-serving requires --action")
        result = coordinator.close_serving(args.action)
    elif args.operation == "confirm":
        if not args.action or not args.lease_id or args.randomization_seed is None:
            parser.error("confirm requires --action, --lease-id and --randomization-seed")
        result = coordinator.start_confirmation(
            args.action, args.lease_id, args.randomization_seed, args.duration_seconds)
    elif args.operation == "sealed":
        if not args.lease_id or args.randomization_seed is None:
            parser.error("sealed requires --lease-id and --randomization-seed")
        result = coordinator.start_sealed(args.lease_id, args.randomization_seed, args.duration_seconds)
    elif args.operation == "promote":
        if not args.action or not args.receipt:
            parser.error("promote requires --action and --receipt")
        result = coordinator.promote(args.action, args.receipt)
    elif args.operation == "rollback":
        if not args.reason:
            parser.error("rollback requires --reason")
        result = coordinator.rollback(args.reason)
    elif args.operation == "abandon-lease":
        if not args.lease_id or not args.reason:
            parser.error("abandon-lease requires --lease-id and --reason")
        result = coordinator.abandon_lease(args.lease_id, args.reason)
    else:
        result = coordinator.snapshot()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
