"""Credentialed provider runner for durable GameWorld coordinator jobs."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.fleet_provider import FleetLifecycle
from fps_bench.gameworld_coordinator import GameWorldCoordinator
from fps_bench.gameworld_fleet import GameWorldFleetExecutor
from fps_bench.gameworld_modal import GameWorldModalTrainingLifecycle, GameWorldTrainingArtifacts
from fps_bench.gameworld_serving import GameWorldServingLifecycle


MODAL_FIELDS = {
    "workspace", "environment", "environment_id", "training_app", "training_app_id",
    "training_image_id", "serving_app", "serving_app_id", "serving_image_id",
}


class GameWorldProviderRunner:
    def __init__(self, coordinator, modal_config, qwen_environment, *, candidate_api_key=None,
                 fleet_lifecycle=None, fleet_executor=None, training_lifecycle=None,
                 training_artifacts=None, serving_lifecycle=None):
        self.coordinator = coordinator
        self.controller = coordinator.controller
        if not isinstance(modal_config, dict) or set(modal_config) != MODAL_FIELDS:
            raise ValueError("Runner requires exact pinned Modal app, environment and image identities")
        if any(not isinstance(value, str) or not value for value in modal_config.values()):
            raise ValueError("Runner Modal identities must be nonempty strings")
        self.modal_config = modal_config
        endpoint = qwen_environment.get("QWEN_BASE_URL", "").rstrip("/")
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or len(qwen_environment.get("QWEN_API_KEY", "")) < 32):
            raise ValueError("Runner requires credentialed HTTPS baseline Qwen serving")
        self.baseline_qwen = {"QWEN_BASE_URL": endpoint, "QWEN_API_KEY": qwen_environment["QWEN_API_KEY"]}
        self.candidate_api_key = candidate_api_key or qwen_environment["QWEN_API_KEY"]
        if len(self.candidate_api_key) < 32:
            raise ValueError("Candidate serving API key is missing or too short")
        self.fleet_lifecycle = fleet_lifecycle or FleetLifecycle(
            self.controller, coordinator.pool, coordinator.state_root / "fleet-provider")
        self.fleet = fleet_executor or GameWorldFleetExecutor(
            self.controller, self.fleet_lifecycle, coordinator.state_root / "fleet")
        self.training = training_lifecycle or GameWorldModalTrainingLifecycle(
            self.controller, training_registry=coordinator.registry)
        self.training_artifacts = training_artifacts or GameWorldTrainingArtifacts(self.training)
        self.serving = serving_lifecycle or GameWorldServingLifecycle(
            self.controller, coordinator.state_root / "serving")

    def _workflow(self, proposal_id):
        return self.coordinator.workflow(proposal_id)

    def _candidate(self, candidate_id):
        return self.coordinator._candidate(candidate_id)

    def _model_workflow(self, candidate_id):
        candidate = self._candidate(candidate_id)
        if candidate["change_class"] == "joint":
            return self._model_workflow(candidate["components"]["model"])
        if candidate["change_class"] == "model":
            with self.controller.ledger.transaction() as connection:
                row = connection.execute(
                    "SELECT proposal_id FROM gameworld_workflows WHERE candidate_id=? AND track='model'",
                    (candidate_id,),
                ).fetchone()
            if row is None:
                raise LedgerConflict("Model candidate lost its coordinator workflow")
            return self._workflow(row["proposal_id"])
        return None

    def policy_path(self, candidate_id):
        candidate = self._candidate(candidate_id)
        workflow = self._model_workflow(candidate_id)
        path = (self.coordinator.state_root / "inputs/baseline-policy.json" if workflow is None
                else Path(workflow["details"]["policy_path"]))
        data = path.read_bytes()
        if digest(data) != candidate["policy_sha256"]:
            raise LedgerConflict("Candidate policy bytes differ from the controller manifest")
        return path

    def driver_binary(self, candidate_id):
        candidate = self._candidate(candidate_id)
        baseline = self._candidate("baseline")
        if candidate["driver_sha256"] == baseline["driver_sha256"]:
            return None
        if candidate["change_class"] == "joint":
            return self.driver_binary(candidate["components"]["driver"])
        root = Path(candidate.get("artifact_root", ""))
        path = root / "cua-driver"
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != candidate["driver_sha256"]:
            raise LedgerConflict("Candidate driver binary differs from its materialized manifest")
        return path

    async def qwen_environment(self, candidate_id):
        workflow = self._model_workflow(candidate_id)
        if workflow is None:
            return self.baseline_qwen.copy()
        serving_job = workflow["details"]["serving_job"]
        _, launch, _ = self.serving.stored(serving_job)
        if not launch["sandbox_id"]:
            raise LedgerConflict("Model serving sandbox is not acknowledged")
        observed = await asyncio.wait_for(self.serving.backend.inspect(launch["sandbox_id"]), 30)
        self.serving.acknowledge(serving_job, observed)
        endpoint = observed.get("endpoint", "").rstrip("/")
        policy = json.loads(self.policy_path(candidate_id).read_bytes())
        if (not endpoint or digest(endpoint.encode()) != policy["deployment"]["endpoint_sha256"]
                or observed.get("returncode") is not None):
            raise LedgerConflict("Live candidate endpoint differs from the policy identity")
        return {"QWEN_BASE_URL": endpoint, "QWEN_API_KEY": self.candidate_api_key}

    def parent_adapter(self, candidate_id):
        candidate = self._candidate(candidate_id)
        if candidate["model"]["adapter_sha256"] is None:
            return None
        workflow = self._model_workflow(candidate_id)
        training = self.coordinator._items(workflow["proposal_id"], "training")
        if len(training) != 1:
            raise LedgerConflict("Model candidate lost its training job")
        path = self.coordinator.state_root / "modal" / training[0]["job_id"] / "adapter"
        manifest = path / "adapter-manifest.json"
        if not manifest.is_file() or digest(manifest.read_bytes()) != candidate["model"]["adapter_sha256"]:
            raise LedgerConflict("Parent adapter bytes differ from the candidate manifest")
        return path

    async def dispatch_fleet(self, row):
        workflow = self._workflow(row["workflow"])
        try:
            if row["kind"] == "driver_build":
                return await self.fleet.driver_candidate(
                    row["job_id"], workflow["details"]["proposal_path"], workflow["details"]["patch_path"])
            candidate_id = self._job_candidate(row["job_id"])
            policy = self.policy_path(candidate_id)
            qwen = await self.qwen_environment(candidate_id)
            driver = self.driver_binary(candidate_id)
            if row["kind"] == "rollout":
                return await self.fleet.rollout(row["job_id"], policy, qwen, driver)
            return await self.fleet.evaluate(row["job_id"], policy, qwen, driver)
        except BaseException:
            await self._cleanup_fleet(row["job_id"])
            raise

    def _job_candidate(self, job_id):
        with self.controller.ledger.transaction() as connection:
            return self.controller._job(connection, job_id)["candidate"]

    async def _cleanup_fleet(self, job_id):
        with self.controller.ledger.transaction() as connection:
            state = self.controller._job(connection, job_id)["state"]
        if state != "cleaned":
            await self.fleet_lifecycle.release(job_id)

    async def dispatch_training(self, row):
        config = self.modal_config
        job_id = row["job_id"]
        try:
            await self.training.prepare(
                job_id, workspace=config["workspace"], app=config["training_app"],
                environment=config["environment"], environment_id=config["environment_id"],
                image_id=config["training_image_id"], app_id=config["training_app_id"],
                isolation_policy="app-scoped")
            await self.training.start(job_id)
            with self.controller.ledger.transaction() as connection:
                staged = connection.execute(
                    "SELECT staging_receipt FROM modal_training_transfers WHERE job_id=?", (job_id,)
                ).fetchone()
            if staged and staged["staging_receipt"]:
                await self.training_artifacts.reconcile_stage(job_id)
            else:
                await self.training_artifacts.stage(
                    job_id, self.parent_adapter(self._job_candidate(job_id)))
            with self.controller.ledger.transaction() as connection:
                attempted = connection.execute(
                    "SELECT 1 FROM modal_training_attempts WHERE job_id=?", (job_id,)
                ).fetchone()
            if not attempted:
                await self.training.run_worker(job_id)
            output = self.coordinator.state_root / "modal" / job_id
            return await self.training_artifacts.export(job_id, output)
        finally:
            await self.cleanup_training(job_id)

    async def cleanup_training(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
        if job["state"] == "reserved":
            self.controller.cancel_undispatched(job_id)
        elif job["state"] not in ("billing_pending", "cleaned"):
            await self.training.terminate(job_id)

    async def dispatch_serving(self, row):
        config = self.modal_config
        assignment = row["assignment"]
        output = self.coordinator.state_root / "modal" / assignment["training_job"]
        try:
            await self.serving.prepare(
                row["job_id"], output, workspace=config["workspace"], app=config["serving_app"],
                environment=config["environment"], environment_id=config["environment_id"],
                image_id=config["serving_image_id"], app_id=config["serving_app_id"],
                isolation_policy="app-scoped")
            return await self.serving.start(row["job_id"], self.candidate_api_key)
        except BaseException:
            await self.cleanup_serving_job(row["job_id"])
            raise

    async def cleanup_serving_job(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
        if job["state"] == "reserved":
            self.controller.cancel_undispatched(job_id)
        elif job["state"] not in ("billing_pending", "cleaned"):
            await self.serving.terminate(job_id)

    async def dispatch(self, row):
        if row["kind"] in ("driver_build", "rollout", "evaluation"):
            return await self.dispatch_fleet(row)
        if row["kind"] == "training":
            return await self.dispatch_training(row)
        if row["kind"] == "serving":
            return await self.dispatch_serving(row)
        raise LedgerConflict("Runner has no provider adapter for this job kind")

    async def safe_dispatch(self, row):
        try:
            await self.dispatch(row)
            event = {"job_id": row["job_id"], "kind": row["kind"], "outcome": "complete"}
        except Exception as error:
            event = {"job_id": row["job_id"], "kind": row["kind"],
                     "outcome": "failed", "error_type": type(error).__name__}
        with self.controller.ledger.transaction() as connection:
            self.controller.ledger._event(connection, "gameworld_runner_dispatch", event)
        return event

    def consecutive_failures(self):
        with self.controller.ledger.transaction() as connection:
            rows = connection.execute(
                "SELECT payload FROM events WHERE kind IN "
                "('gameworld_runner_dispatch','gameworld_runner_serving_cleanup') ORDER BY sequence DESC"
            ).fetchall()
        failures = 0
        for row in rows:
            if json.loads(row["payload"]).get("outcome") not in ("failed", "unresolved"):
                break
            failures += 1
        return failures

    def stop_after_durable_failures(self):
        if self.consecutive_failures() < 3:
            return False
        snapshot = self.controller.snapshot()["controller"]
        if not snapshot["stopped"]:
            self.controller.stop("Three consecutive provider runner failures")
        return True

    def start_joint_if_ready(self):
        snapshot = self.coordinator.snapshot()
        if any(row["track"] == "joint" for row in snapshot["workflows"]):
            return None
        drivers = [row for row in snapshot["workflows"] if row["track"] == "driver"
                   and row["state"] == "complete" and row["decision"]
                   and row["decision"].get("decision") == "nominate"]
        models = [row for row in snapshot["workflows"] if row["track"] == "model"
                  and row["state"] == "qualified_serving_live"]
        if not drivers or not models:
            return None
        return self.coordinator.start_joint(drivers[-1]["action_id"], models[-1]["action_id"])

    async def terminate_due_serving(self):
        outcomes = []
        seen = set()
        for action in self.coordinator.required_actions():
            if action["action"] != "terminate-serving" or action["owner"] in seen:
                continue
            seen.add(action["owner"])
            serving = self.coordinator._items(action["owner"], "serving")
            if len(serving) != 1:
                raise LedgerConflict("Serving cleanup owner lost its one admitted serving job")
            try:
                await self.cleanup_serving_job(serving[0]["job_id"])
                event = {"workflow": action["owner"], "job_id": serving[0]["job_id"],
                         "outcome": "serving-terminated"}
            except Exception as error:
                event = {"workflow": action["owner"], "job_id": serving[0]["job_id"],
                         "outcome": "unresolved", "error_type": type(error).__name__}
            with self.controller.ledger.transaction() as connection:
                self.controller.ledger._event(connection, "gameworld_runner_serving_cleanup", event)
            outcomes.append(event)
        return outcomes

    async def run_once(self, maximum=2):
        failure_gate = self.stop_after_durable_failures()
        transitions = self.coordinator.advance()
        joint = None if failure_gate else self.start_joint_if_ready()
        if joint is not None:
            transitions.append({"workflow": joint["proposal_id"], "state": joint["state"]})
        cleanup = await self.terminate_due_serving()
        transitions.extend(self.coordinator.advance())
        admitted = [] if failure_gate else self.coordinator.admit_ready(maximum)
        runnable = [] if failure_gate else self.coordinator.runnable()[:maximum]
        events = await asyncio.gather(*(self.safe_dispatch(row) for row in runnable)) if runnable else []
        transitions.extend(self.coordinator.advance())
        self.stop_after_durable_failures()
        telemetry = None
        if self.coordinator.supervisor.telemetry is not None:
            event_count = self.controller.ledger.snapshot()["event_count"]
            recorded = self.controller.emit_telemetry(
                self.coordinator.supervisor.telemetry, f"runner-accounting-{event_count}")
            telemetry = self.coordinator.supervisor.telemetry.flush() if recorded else {"recorded": False}
        return {"transitions": transitions, "admitted": admitted, "dispatch": events, "cleanup": cleanup,
                "required_actions": self.coordinator.required_actions(), "telemetry": telemetry}

    async def run_until_idle(self, maximum=2, max_cycles=10000):
        if type(max_cycles) is not int or not 1 <= max_cycles <= 100000:
            raise ValueError("Runner cycle bound must be 1..100000")
        history = []
        for _ in range(max_cycles):
            result = await self.run_once(maximum)
            history.append(result)
            if result["dispatch"] or result["cleanup"] or result["transitions"] or result["admitted"]:
                continue
            proposal = self.coordinator.supervisor.next()
            if proposal is not None:
                action = "action-" + digest(canonical(proposal["id"]))[:24]
                self.coordinator.start_next(action)
                continue
            break
        else:
            raise RuntimeError("Runner cycle bound exhausted")
        return {"cycles": len(history), "last": history[-1], "snapshot": self.coordinator.snapshot()}


def modal_config(args):
    return {name: getattr(args, name) for name in MODAL_FIELDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["once", "run"])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-policy", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--pool", default="gameworld-autoresearch")
    parser.add_argument("--telemetry", type=Path)
    for name in sorted(MODAL_FIELDS):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--maximum", type=int, default=2)
    parser.add_argument("--max-cycles", type=int, default=10000)
    args = parser.parse_args()
    qwen = {"QWEN_BASE_URL": os.environ.get("QWEN_BASE_URL", ""),
            "QWEN_API_KEY": os.environ.get("QWEN_API_KEY", "")}
    coordinator = GameWorldCoordinator(
        args.database, args.contract, args.contract_sha256, args.baseline, args.state_root,
        args.policy, args.catalog, args.telemetry, args.pool)
    coordinator.initialize(args.campaign, args.baseline_policy)
    runner = GameWorldProviderRunner(
        coordinator, modal_config(args), qwen,
        candidate_api_key=os.environ.get("QWEN_CANDIDATE_API_KEY"))
    if args.operation == "once":
        result = asyncio.run(runner.run_once(args.maximum))
    else:
        result = asyncio.run(runner.run_until_idle(args.maximum, args.max_cycles))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
