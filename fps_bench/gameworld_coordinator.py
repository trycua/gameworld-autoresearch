"""Durable GameWorld workflow coordinator over the supervisor and campaign ledger."""

import argparse
import json
from pathlib import Path

from fps_bench.campaign_controller import CampaignController, IDENTIFIER
from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict, positive_integer
from fps_bench.evaluation_contract import canonical, digest, exclusive_write, schedule
from fps_bench.gameworld_grpo import validate_policy_identity
from fps_bench.gameworld_research import (
    DEFAULT_CATALOG,
    DEFAULT_POLICY,
    GameWorldResearchSupervisor,
)
from fps_bench.gameworld_training import GameWorldTrainingRegistry


QUEUE_STATES = {"pending", "admitted", "live", "complete", "failed"}
WORKFLOW_STATES = {
    "awaiting_patch", "building", "collecting_rollouts", "awaiting_dataset", "awaiting_sft_dataset",
    "training", "serving", "evaluating", "qualified_serving_live",
    "awaiting_serving_stop", "complete", "rejected",
}


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
                 pool="gameworld-autoresearch", registry=None):
        self.database = Path(database)
        self.state_root = Path(state_root).resolve()
        self.pool = pool
        self.policy_path = Path(policy_path)
        self.catalog_path = Path(catalog_path)
        self.supervisor = GameWorldResearchSupervisor(
            database, baseline_output, policy_path, catalog_path, telemetry_path)
        self.controller = CampaignController(database, contract_path, contract_hash)
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
            "policy_sha256": digest(policy_bytes),
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
                "UNIQUE(workflow,phase,ordinal))"
            )
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
        state = "awaiting_patch" if proposal["track"] == "driver" else (
            "collecting_rollouts" if proposal["experiment"]["objective"] == "grpo" else "awaiting_sft_dataset")
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
            self._queue_rollouts(proposal)
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
                    "timeout_seconds": row["timeout_seconds"],
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
                    }
                    if existing["job_id"] != job_id or observed != payload:
                        raise LedgerConflict("Queued workflow work changed after registration")
                    continue
                connection.execute(
                    "INSERT INTO gameworld_work_items VALUES (?,?,?,?,?,?,?,?,?,?,'pending')",
                    (item_id, workflow, phase, ordinal, job_id, row["candidate"], row["kind"],
                     canonical(row["assignment"]).decode(), canonical(row["reservations"]).decode(),
                     row["timeout_seconds"]),
                )
                inserted += 1
            if inserted:
                self.controller.ledger._event(connection, "gameworld_work_queued", {
                    "workflow": workflow, "phase": phase, "jobs": inserted,
                })

    def _candidate(self, candidate_id):
        with self.controller.ledger.transaction() as connection:
            return json.loads(self.controller._candidate(connection, candidate_id)["manifest"])

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
        if sum(allocation.values()) > proposal["budget"]["modal_micro_usd"]:
            raise BudgetRefused("Training and serving allocations exceed the proposal Modal bound")
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
                    json.loads(row["reservations"]), row["timeout_seconds"])
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
            if state == "building":
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
                    self._queue_evaluations(proposal_id, ["baseline", candidate_id], workflow["comparison"])
                    self._set_workflow(proposal_id, state="evaluating", candidate_id=candidate_id)
                    transitions.append({"workflow": proposal_id, "state": "evaluating"})
            elif state == "collecting_rollouts":
                items = self._items(proposal_id, "rollout")
                if any(item["state"] == "failed" for item in items):
                    self._finalize(workflow, proposal_id, False, {"phase": "rollout", "failed": True})
                    transitions.append({"workflow": proposal_id, "state": "rejected"})
                elif items and all(item["state"] == "complete" for item in items):
                    self._set_workflow(proposal_id, state="awaiting_dataset")
                    transitions.append({"workflow": proposal_id, "state": "awaiting_dataset"})
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
                        "candidate": "baseline", "kind": "serving", "assignment": assignment,
                        "reservations": {"modal_micro_usd": allocation["serving_micro_usd"]},
                        "timeout_seconds": proposal["budget"]["timeout_seconds"],
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
                        self._set_workflow(proposal_id, state="awaiting_serving_stop", decision=decision)
                        owner = workflow["details"]["serving_owner"]
                        with self.controller.ledger.transaction() as connection:
                            model = self._workflow(connection, owner)
                        self._set_workflow(owner, state="awaiting_serving_stop", decision=model["decision"])
                    else:
                        decision = self.controller.decide_development(workflow["candidate_id"])
                        if workflow["track"] == "driver":
                            self._finalize(workflow, workflow["candidate_id"],
                                           decision["decision"] == "nominate", decision)
                        elif decision["decision"] == "nominate":
                            self._set_workflow(proposal_id, state="qualified_serving_live", decision=decision)
                        else:
                            self._set_workflow(proposal_id, state="awaiting_serving_stop", decision=decision)
                    transitions.append({"workflow": proposal_id, "state": self.workflow(proposal_id)["state"]})
            elif state == "awaiting_serving_stop":
                if workflow["track"] == "joint":
                    owner = workflow["details"]["serving_owner"]
                    serving = self._items(owner, "serving")
                    if serving and serving[0]["state"] == "complete":
                        with self.controller.ledger.transaction() as connection:
                            model = self._workflow(connection, owner)
                        self._finalize(model, model["candidate_id"], True, model["decision"])
                        self._set_workflow(proposal_id, state="complete")
                        transitions.append({"workflow": proposal_id, "state": "complete"})
                else:
                    serving = self._items(proposal_id, "serving")
                    if serving and serving[0]["state"] == "complete":
                        qualified = bool(workflow["decision"] and workflow["decision"].get("decision") == "nominate")
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

    def close_model(self, action_id):
        workflow = self.workflow(action_id)
        if workflow["track"] != "model" or workflow["state"] != "qualified_serving_live":
            raise LedgerConflict("Only a qualified live model workflow can close without a joint comparison")
        self._set_workflow(workflow["proposal_id"], state="awaiting_serving_stop")
        return self.workflow(workflow["proposal_id"])

    def dispatchable(self):
        with self.controller.ledger.transaction() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT q.workflow,q.phase,q.job_id,q.kind,q.assignment,q.reservations,j.state "
                "FROM gameworld_work_items q JOIN jobs j ON j.id=q.job_id "
                "WHERE q.state='admitted' AND j.state='reserved' ORDER BY q.workflow,q.phase,q.ordinal"
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
                action = "allocate-model-budget" if "modal_allocation" not in workflow["details"] else "register-training-dataset"
                actions.append({"workflow": workflow["proposal_id"], "action": action})
            elif workflow["state"] == "awaiting_sft_dataset":
                action = ("allocate-model-budget" if "modal_allocation" not in workflow["details"]
                          else "attach-authenticated-sft-dataset")
                actions.append({"workflow": workflow["proposal_id"], "action": action})
            elif workflow["state"] == "qualified_serving_live":
                actions.append({"workflow": workflow["proposal_id"], "action": "start-joint-or-stop-serving"})
            elif workflow["state"] == "awaiting_serving_stop":
                owner = workflow["details"].get("serving_owner", workflow["proposal_id"])
                actions.append({"workflow": workflow["proposal_id"], "action": "terminate-serving", "owner": owner})
        actions.extend({"workflow": row["workflow"], "job_id": row["job_id"],
                        "action": "dispatch-" + row["kind"]} for row in self.dispatchable())
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
        "advance", "dataset", "attach-sft", "joint", "close-model",
    ])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
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
    args = parser.parse_args()
    coordinator = GameWorldCoordinator(
        args.database, args.contract, args.contract_sha256, args.baseline, args.state_root,
        args.policy, args.catalog, args.telemetry, args.pool)
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
    else:
        result = coordinator.snapshot()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
