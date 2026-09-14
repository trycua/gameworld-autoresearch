"""Controller-admitted Modal sandbox serving for immutable GameWorld adapters."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import re
import time
from urllib import request

from fps_bench.campaign_ledger import BudgetRefused, LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_grpo import (
    policy_core,
    policy_digest,
    validate_policy_core,
    validate_policy_identity,
    verify_grpo_adapter,
    verify_parent_adapter,
)
from fps_bench.modal_scope import check_scope
from fps_bench.qwen_lora import verify_adapter as verify_sft_adapter


GPU = "L4"
CPU = 4
MEMORY_MIB = 32768


def compute_reservation(rates, seconds, checked_at):
    if type(seconds) is not int or not 300 <= seconds <= 3600:
        raise ValueError("Serving sandbox lifetime must be 300..3600 seconds")
    age = time.time() - datetime.fromisoformat(checked_at.replace("Z", "+00:00")).timestamp()
    if not 0 <= age <= 300:
        raise ValueError("Modal serving price snapshot is stale or future-dated")
    values = [Decimal(rates[name]) for name in (
        "gpu_hour_cost_l4", "cpu_hour_cost_sandbox", "mem_gib_hour_cost_sandbox")]
    if any(not value.is_finite() or value <= 0 or value > 100 for value in values):
        raise ValueError("Invalid Modal serving rate")
    hourly = values[0] + CPU * values[1] + (MEMORY_MIB // 1024) * values[2]
    estimate = int((hourly * seconds / 3600 * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    return {"compute_estimate_micro_usd": estimate,
            "required_reservation_micro_usd": 2 * estimate + 1_000_000,
            "rates": {name: rates[name] for name in (
                "gpu_hour_cost_l4", "cpu_hour_cost_sandbox", "mem_gib_hour_cost_sandbox")},
            "checked_at": checked_at, "seconds": seconds}


def authenticated_request(endpoint, api_key, route, payload=None, timeout=120):
    data = None if payload is None else json.dumps(payload).encode()
    outgoing = request.Request(endpoint.rstrip("/") + route, data=data, headers={
        "Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    with request.urlopen(outgoing, timeout=timeout) as response:
        return json.load(response)


class ModalServingBackend:
    async def app_scope(self, workspace, environment, app):
        from fps_bench.modal_scope import inspect_app_scope
        return await inspect_app_scope(workspace, environment, app)

    async def environment(self, workspace, name):
        from fps_bench.modal_environment import inspect_environment
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
        return await self.inspect(sandbox.object_id)

    async def inspect(self, sandbox_id):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        returncode = await sandbox.poll.aio()
        tunnels = {} if returncode is not None else await sandbox.tunnels.aio()
        endpoint = tunnels[8000].url.rstrip("/") + "/v1" if 8000 in tunnels else None
        return {"id": sandbox.object_id, "tags": await sandbox.get_tags.aio(),
                "returncode": returncode, "endpoint": endpoint}

    async def create(self, plan):
        import modal
        await check_scope(self, plan)
        current = await self.prices(plan["workspace"])
        refreshed = compute_reservation(current["rates"], plan["seconds"], current["checked_at"])
        if refreshed["required_reservation_micro_usd"] > plan["quote"]["required_reservation_micro_usd"]:
            raise BudgetRefused("Modal serving rates increased after preparation")
        app = await modal.App.lookup.aio(plan["app"], environment_name=plan["environment"], create_if_missing=False)
        if plan.get("app_id") is not None and app.app_id != plan["app_id"]:
            raise LedgerConflict("Serving app identity changed before sandbox creation")
        cache = modal.Volume.from_name("gameworld-qwen-hf-cache", create_if_missing=False).with_mount_options(read_only=True)
        sandbox = await modal.Sandbox.create.aio(
            "/bin/sleep", str(plan["seconds"]), app=app, image=modal.Image.from_id(plan["image_id"]),
            name=plan["name"], tags=plan["tags"], gpu=GPU, cpu=(CPU, CPU), memory=(MEMORY_MIB, MEMORY_MIB),
            timeout=plan["seconds"], block_network=True, secrets=[], volumes={"/cache": cache},
            network_file_systems={}, encrypted_ports=[8000], include_oidc_identity_token=False,
            env={"HF_HOME": "/cache/huggingface", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                 "HF_HUB_DISABLE_TELEMETRY": "1", "VLLM_NO_USAGE_STATS": "1", "DO_NOT_TRACK": "1"})
        return await self.inspect(sandbox.object_id)

    async def stage(self, sandbox_id, adapter, manifest, target):
        if target not in {"adapter", "parent-adapter"}:
            raise ValueError("Unsupported serving adapter target")
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        destination = "/input/" + target
        process = await sandbox.exec.aio("mkdir", "-p", destination, "/output", timeout=30)
        if await process.wait.aio() != 0:
            raise RuntimeError("Serving input directories could not be created")
        payloads = {"adapter-manifest.json": (Path(adapter) / "adapter-manifest.json").read_bytes()}
        payloads.update({name: (Path(adapter) / name).read_bytes() for name in manifest["files"]})
        for name, data in payloads.items():
            await sandbox.filesystem.write_bytes.aio(data, destination + "/" + name)
        return {name: digest(data) for name, data in payloads.items()}

    async def start_server(self, sandbox_id, plan, api_key):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        command = [
            "vllm", "serve", plan["base_model"], "--revision", plan["base_revision"],
            "--tokenizer-revision", plan["base_revision"], "--served-model-name", plan["raw_base_served_model"],
            "--host", "0.0.0.0", "--port", "8000", "--dtype", "bfloat16",
            "--max-model-len", "8192", "--max-num-seqs", "1", "--gpu-memory-utilization", "0.85",
            "--limit-mm-per-prompt", '{"image":1,"video":0}', "--seed", "42",
            "--generation-config", "vllm", "--enforce-eager",
        ]
        loras = []
        if plan["parent_adapter_sha256"] is not None:
            loras.append(plan["parent_served_model"] + "=/input/parent-adapter")
        if plan["mode"] == "adapter":
            loras.append(plan["served_model"] + "=/input/adapter")
        if loras:
            command.extend(["--enable-lora", "--max-loras", str(len(loras)), "--max-lora-rank", "8",
                            "--lora-modules", *loras])
        shell = " ".join(__import__("shlex").quote(value) for value in command)
        process = await sandbox.exec.aio(
            "bash", "-lc", f"nohup {shell} >/output/server.log 2>&1 </dev/null & echo $! >/output/server.pid",
            timeout=30, env={"VLLM_API_KEY": api_key}, secrets=[])
        if await process.wait.aio() != 0:
            raise RuntimeError("Candidate vLLM launch command failed")
        for _ in range(240):
            observed = await self.inspect(sandbox_id)
            if observed["returncode"] is not None:
                raise RuntimeError("Candidate serving sandbox exited during startup")
            if observed["endpoint"]:
                try:
                    models = await asyncio.to_thread(
                        authenticated_request, observed["endpoint"], api_key, "/models", None, 10)
                    advertised = {item.get("id") for item in models.get("data", [])}
                    if set(plan["advertised_models"]) <= advertised:
                        return observed
                except Exception:
                    pass
            await asyncio.sleep(2)
        raise TimeoutError("Candidate vLLM endpoint did not become ready")

    async def terminate(self, sandbox_id):
        import modal
        sandbox = await modal.Sandbox.from_id.aio(sandbox_id)
        await sandbox.terminate.aio(wait=True)


class GameWorldServingLifecycle:
    def __init__(self, controller, output, backend=None):
        self.controller, self.output = controller, Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.backend = backend or ModalServingBackend()
        with controller.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS gameworld_serving_launches ("
                               "job_id TEXT PRIMARY KEY REFERENCES jobs(id), plan TEXT NOT NULL, sandbox_id TEXT, "
                               "adapter_staged INTEGER NOT NULL DEFAULT 0, "
                               "parent_adapter_staged INTEGER NOT NULL DEFAULT 0, "
                               "server_attempted INTEGER NOT NULL DEFAULT 0, "
                               "policy_identity TEXT, termination_receipt TEXT)")
            columns = {row["name"] for row in connection.execute(
                "PRAGMA table_info(gameworld_serving_launches)")}
            if "parent_adapter_staged" not in columns:
                connection.execute(
                    "ALTER TABLE gameworld_serving_launches ADD COLUMN "
                    "parent_adapter_staged INTEGER NOT NULL DEFAULT 0")

    def stored(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = dict(self.controller._job(connection, job_id))
            launch = connection.execute(
                "SELECT * FROM gameworld_serving_launches WHERE job_id=?", (job_id,)
            ).fetchone()
            if launch is None:
                raise LedgerConflict("No prepared GameWorld serving launch")
            return job, dict(launch), json.loads(launch["plan"])

    def save_plan(self, job_id, plan):
        encoded = canonical(plan).decode()
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT plan FROM gameworld_serving_launches WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                if existing["plan"] != encoded:
                    raise LedgerConflict("Serving launch identity is immutable")
                return json.loads(existing["plan"])
            if self.controller._job(connection, job_id)["state"] != "reserved":
                raise LedgerConflict("Prepare serving before provider dispatch")
            connection.execute("INSERT INTO gameworld_serving_launches(job_id,plan) VALUES (?,?)",
                               (job_id, encoded))
        return plan

    async def prepare_source(self, job_id, policy_path, adapter=None, *, workspace, app, environment,
                             environment_id, image_id, app_id=None,
                             isolation_policy="restricted-environment"):
        if not re.fullmatch(r"im-[A-Za-z0-9]+", image_id) or not re.fullmatch(r"ap-[A-Za-z0-9]+", app_id or ""):
            raise ValueError("Serving requires immutable Modal image and app IDs")
        policy_bytes = Path(policy_path).read_bytes()
        identity = json.loads(policy_bytes)
        if canonical(identity) != policy_bytes:
            raise ValueError("Source policy identity must use canonical encoding")
        template = self.controller.contract["episode_template"]
        core = validate_policy_core(identity, {"model": {
            "base_model": template["model"], "base_revision": template["revision"]}})
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            job = self.controller._job(connection, job_id)
            specification = json.loads(job["specification"])
            assignment = specification["assignment"]
            candidate = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
            if (job["kind"] != "serving"
                    or set(specification["reservations"]) != {"modal_micro_usd"}
                    or assignment.get("mode") != "source"
                    or assignment.get("policy_sha256") != policy_digest(core)
                    or candidate["policy_sha256"] != assignment["policy_sha256"]
                    or candidate["model"]["adapter_sha256"] != assignment["adapter_sha256"]
                    or core["adapter_sha256"] != assignment["adapter_sha256"]
                    or core["served_model"] != assignment.get("served_model")
                    or core["generation"] != assignment.get("generation")):
                raise LedgerConflict("Source serving differs from the registered candidate policy")
        parent_adapter = verify_parent_adapter(adapter, core["adapter_sha256"], identity)
        parent_manifest = (None if parent_adapter is None else
                           json.loads((parent_adapter / "adapter-manifest.json").read_bytes()))
        scope = {"workspace": workspace, "environment": environment, "environment_id": environment_id,
                 "app": app, "app_id": app_id, "isolation_policy": isolation_policy}
        guard = await check_scope(self.backend, scope)
        price = await asyncio.wait_for(self.backend.prices(workspace), 30)
        quote = compute_reservation(price["rates"], specification["timeout_seconds"], price["checked_at"])
        if specification["reservations"]["modal_micro_usd"] < quote["required_reservation_micro_usd"]:
            raise BudgetRefused("Serving job hold does not cover the refreshed Modal quote")
        campaign = self.controller.ledger.snapshot()["campaign"]["id"]
        raw_base_served_model = (core["served_model"] if parent_adapter is None else
                                 "base-" + digest(canonical([core["base_model"], core["base_revision"]]))[:24])
        launch = {**scope, "image_id": image_id, "name": "gw-serve-" + digest(canonical([campaign, job_id]))[:20],
                  "seconds": specification["timeout_seconds"], "mode": "source", "policy": core,
                  "served_model": core["served_model"], "base_model": core["base_model"],
                  "base_revision": core["base_revision"], "raw_base_served_model": raw_base_served_model,
                  "parent_policy": core, "parent_served_model": core["served_model"],
                  "parent_adapter_sha256": core["adapter_sha256"],
                  "parent_adapter_root": None if parent_adapter is None else str(parent_adapter.resolve()),
                  "parent_adapter_files": {} if parent_manifest is None else parent_manifest["files"],
                  "advertised_models": [core["served_model"]],
                  "adapter_manifest_sha256": None, "adapter_files": {}}
        tags = {"campaign": campaign, "job": job_id, "identity": digest(canonical(launch))}
        return self.save_plan(job_id, {**launch, "tags": tags, "quote": quote, "scope_guard": guard})

    async def prepare(self, job_id, training_output, parent_adapter=None, *, workspace, app, environment,
                      environment_id, image_id, app_id=None, isolation_policy="restricted-environment"):
        if not re.fullmatch(r"im-[A-Za-z0-9]+", image_id) or not re.fullmatch(r"ap-[A-Za-z0-9]+", app_id or ""):
            raise ValueError("Serving requires immutable Modal image and app IDs")
        training_output = Path(training_output).resolve()
        bundle = json.loads((training_output / "bundle.json").read_bytes())
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection, admission=True)
            job = self.controller._job(connection, job_id)
            specification = json.loads(job["specification"])
            assignment = specification["assignment"]
            training = self.controller._job(connection, assignment["training_job"])
            training_result = json.loads(training["result"])
            parent = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
            if (job["kind"] != "serving" or set(specification["reservations"]) != {"modal_micro_usd"}
                    or training_result["artifact_sha256"] != digest(canonical(bundle))
                    or bundle.get("output") != str(training_output)
                    or bundle.get("adapter_manifest_sha256") != assignment["adapter_sha256"]
                    or assignment["parent_policy_sha256"] != parent["policy_sha256"]
                    or assignment["parent_adapter_sha256"] != parent["model"]["adapter_sha256"]
                    or assignment["parent_served_model"] != parent["model"]["served_model"]):
                raise LedgerConflict("Serving input differs from the completed training job")
        policy_identity = json.loads((training_output / "policy.json").read_bytes())
        parent_policy = validate_policy_core(policy_identity, {"model": {
            "base_model": parent["model"]["base_model"], "base_revision": parent["model"]["base_revision"]}})
        if (policy_digest(parent_policy) != parent["policy_sha256"]
                or parent_policy["adapter_sha256"] != assignment["parent_adapter_sha256"]
                or parent_policy["served_model"] != assignment["parent_served_model"]):
            raise LedgerConflict("Child training policy differs from its registered parent")
        parent_adapter = verify_parent_adapter(
            parent_adapter, assignment["parent_adapter_sha256"], policy_identity)
        parent_manifest = (None if parent_adapter is None else
                           json.loads((parent_adapter / "adapter-manifest.json").read_bytes()))
        adapter_data = (training_output / "adapter/adapter-manifest.json").read_bytes()
        adapter_identity = json.loads(adapter_data)
        if adapter_identity.get("objective") == "grpo":
            adapter_manifest = verify_grpo_adapter(
                training_output / "adapter", assignment["adapter_sha256"], policy_identity,
                bundle["dataset_sha256"], parent["driver_sha256"])
        elif adapter_identity.get("objective") == "sft":
            adapter_manifest = verify_sft_adapter(
                training_output / "adapter", assignment["adapter_sha256"],
                parent["model"]["base_model"], parent["model"]["base_revision"],
                bundle["dataset_sha256"], self.controller.contract_hash)
        else:
            raise ValueError("Serving adapter has an unsupported training objective")
        scope = {"workspace": workspace, "environment": environment, "environment_id": environment_id,
                 "app": app, "app_id": app_id, "isolation_policy": isolation_policy}
        guard = await check_scope(self.backend, scope)
        price = await asyncio.wait_for(self.backend.prices(workspace), 30)
        quote = compute_reservation(price["rates"], specification["timeout_seconds"], price["checked_at"])
        if specification["reservations"]["modal_micro_usd"] < quote["required_reservation_micro_usd"]:
            raise BudgetRefused("Serving job hold does not cover the refreshed Modal quote")
        campaign = self.controller.ledger.snapshot()["campaign"]["id"]
        policy = {"base_model": parent["model"]["base_model"],
                  "base_revision": parent["model"]["base_revision"],
                  "adapter_sha256": assignment["adapter_sha256"],
                  "served_model": assignment["served_model"], "generation": assignment["generation"]}
        validate_policy_core(policy, {"model": {
            "base_model": parent["model"]["base_model"], "base_revision": parent["model"]["base_revision"]}})
        raw_base_served_model = (parent_policy["served_model"] if parent_adapter is None else
                                 "base-" + digest(canonical([
                                     parent["model"]["base_model"], parent["model"]["base_revision"]]))[:24])
        identity = {**scope, "image_id": image_id, "name": "gw-serve-" + digest(canonical([campaign, job_id]))[:20],
                    "mode": "adapter", "policy": policy,
                    "seconds": specification["timeout_seconds"], "training_output": str(training_output),
                    "training_job": assignment["training_job"], "hypothesis": assignment["hypothesis"],
                    "comparison": assignment["comparison"],
                    "objective": adapter_manifest["objective"],
                    "adapter_manifest_sha256": assignment["adapter_sha256"],
                    "served_model": assignment["served_model"], "generation": assignment["generation"],
                    "base_model": parent["model"]["base_model"], "base_revision": parent["model"]["base_revision"],
                    "raw_base_served_model": raw_base_served_model,
                    "parent_policy": parent_policy,
                    "parent_served_model": assignment["parent_served_model"],
                    "parent_adapter_sha256": assignment["parent_adapter_sha256"],
                    "parent_adapter_root": None if parent_adapter is None else str(parent_adapter.resolve()),
                    "advertised_models": [assignment["parent_served_model"], assignment["served_model"]]}
        tags = {"campaign": campaign, "job": job_id, "identity": digest(canonical(identity))}
        plan = {**identity, "tags": tags, "quote": quote, "scope_guard": guard,
                "adapter_files": adapter_manifest["files"],
                "parent_adapter_files": {} if parent_manifest is None else parent_manifest["files"]}
        return self.save_plan(job_id, plan)

    def acknowledge(self, job_id, observed):
        job, launch, plan = self.stored(job_id)
        if (not isinstance(observed.get("id"), str) or not observed["id"].startswith("sb-")
                or observed.get("tags") != plan["tags"]):
            raise LedgerConflict("Serving sandbox identity differs from its launch")
        if launch["sandbox_id"] and launch["sandbox_id"] != observed["id"]:
            raise LedgerConflict("Refusing to adopt a replacement serving sandbox")
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE gameworld_serving_launches SET sandbox_id=? WHERE job_id=?",
                               (observed["id"], job_id))
        if job["state"] == "dispatching":
            self.controller.provider_started(job_id, observed["id"])
        return observed["id"]

    async def start(self, job_id, api_key):
        if not isinstance(api_key, str) or len(api_key) < 32:
            raise ValueError("Candidate serving API key must contain at least 32 characters")
        job, launch, plan = self.stored(job_id)
        if job["state"] not in ("reserved", "dispatching", "running", "cleanup_pending"):
            raise LedgerConflict("Serving job cannot start or reconnect")
        observed = None
        if launch["sandbox_id"]:
            observed = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        else:
            observed = await asyncio.wait_for(self.backend.lookup(plan["app"], plan["environment"], plan["name"]), 30)
        if job["state"] == "reserved":
            if observed is not None:
                raise LedgerConflict("Named serving sandbox collision before dispatch")
            await check_scope(self.backend, plan)
            self.controller.begin_dispatch(job_id)
            observed = await asyncio.wait_for(self.backend.create(plan), 180)
        if observed is None:
            raise LedgerConflict("Ambiguous serving submission; never recreate automatically")
        self.acknowledge(job_id, observed)
        job, launch, plan = self.stored(job_id)
        if plan["parent_adapter_sha256"] is not None and not launch["parent_adapter_staged"]:
            parent_adapter = Path(plan["parent_adapter_root"])
            parent_manifest = json.loads((parent_adapter / "adapter-manifest.json").read_bytes())
            staged = await self.backend.stage(
                launch["sandbox_id"], parent_adapter, parent_manifest, "parent-adapter")
            expected = {"adapter-manifest.json": plan["parent_adapter_sha256"],
                        **plan["parent_adapter_files"]}
            if staged != expected:
                raise ValueError("Parent serving adapter staging receipt differs from admission")
            with self.controller.ledger.transaction() as connection:
                connection.execute(
                    "UPDATE gameworld_serving_launches SET parent_adapter_staged=1 WHERE job_id=?",
                    (job_id,))
        if plan["mode"] == "adapter":
            adapter = Path(plan["training_output"]) / "adapter"
            manifest = json.loads((adapter / "adapter-manifest.json").read_bytes())
            if not launch["adapter_staged"]:
                staged = await self.backend.stage(launch["sandbox_id"], adapter, manifest, "adapter")
                expected = {"adapter-manifest.json": plan["adapter_manifest_sha256"], **plan["adapter_files"]}
                if staged != expected:
                    raise ValueError("Serving adapter staging receipt differs from admission")
                with self.controller.ledger.transaction() as connection:
                    connection.execute("UPDATE gameworld_serving_launches SET adapter_staged=1 WHERE job_id=?",
                                       (job_id,))
        if not launch["server_attempted"]:
            with self.controller.ledger.transaction() as connection:
                connection.execute("UPDATE gameworld_serving_launches SET server_attempted=1 WHERE job_id=?",
                                   (job_id,))
            observed = await self.backend.start_server(launch["sandbox_id"], plan, api_key)
        else:
            observed = await self.backend.inspect(launch["sandbox_id"])
        self.acknowledge(job_id, observed)
        if not observed.get("endpoint") or observed.get("returncode") is not None:
            raise LedgerConflict("Attempted serving sandbox is not a live endpoint")
        models = await asyncio.to_thread(authenticated_request, observed["endpoint"], api_key, "/models")
        advertised = {item.get("id") for item in models.get("data", [])}
        if not set(plan["advertised_models"]) <= advertised:
            raise ValueError("Required policy models are not advertised by the serving endpoint")
        policy_identity = {**policy_core(plan["policy"]),
                           "deployment": {"app_id": plan["app_id"], "sandbox_id": launch["sandbox_id"],
                                          "image_id": plan["image_id"],
                                          "endpoint_sha256": digest(observed["endpoint"].encode())}}
        validate_policy_identity(policy_identity, {
            "model": {"base_model": plan["base_model"], "base_revision": plan["base_revision"],
                      "minimum_grpo_group_size": 2, "maximum_grpo_group_size": 8}})
        encoded = canonical(policy_identity).decode()
        with self.controller.ledger.transaction() as connection:
            current = connection.execute(
                "SELECT policy_identity FROM gameworld_serving_launches WHERE job_id=?", (job_id,)
            ).fetchone()[0]
            if current is not None and current != encoded:
                raise LedgerConflict("Serving policy identity changed")
            connection.execute("UPDATE gameworld_serving_launches SET policy_identity=? WHERE job_id=?",
                               (encoded, job_id))
        root = self.output / job_id
        if root.exists():
            if (root / "policy.json").read_bytes() != canonical(policy_identity):
                raise LedgerConflict("Local serving identity changed")
        else:
            root.mkdir()
            exclusive_write(root / "policy.json", canonical(policy_identity), 0o400)
        parent_policy_identity = None
        if plan["mode"] == "adapter":
            parent_policy_identity = {**policy_core(plan["parent_policy"]),
                                      "deployment": policy_identity["deployment"]}
            validate_policy_identity(parent_policy_identity, {
                "model": {"base_model": plan["base_model"], "base_revision": plan["base_revision"],
                          "minimum_grpo_group_size": 2, "maximum_grpo_group_size": 8}})
            parent_path = root / "parent-policy.json"
            if parent_path.exists():
                if parent_path.read_bytes() != canonical(parent_policy_identity):
                    raise LedgerConflict("Local parent serving identity changed")
            else:
                exclusive_write(parent_path, canonical(parent_policy_identity), 0o400)
        result = {"status": "complete", "candidate_id": (
                      job["candidate"] if plan["mode"] == "source" else plan["served_model"]),
                  "adapter_manifest_sha256": (plan["parent_adapter_sha256"]
                                                if plan["mode"] == "source"
                                                else plan["adapter_manifest_sha256"]),
                  "policy_sha256": policy_digest(policy_identity),
                  "deployment": policy_identity["deployment"]}
        receipt = {"job_id": job_id, "sandbox_id": launch["sandbox_id"], "result": result}
        if not (root / "serving.json").exists():
            exclusive_write(root / "serving.json", canonical(receipt), 0o400)
        elif (root / "serving.json").read_bytes() != canonical(receipt):
            raise LedgerConflict("Local serving receipt changed")
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        candidate = None
        if plan["mode"] == "adapter":
            with self.controller.ledger.transaction() as connection:
                parent = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
            candidate = {**{key: parent[key] for key in ("contract_hash", "image", "driver_sha256")},
                         "id": plan["served_model"], "parent": job["candidate"], "change_class": "model",
                         "hypothesis": plan["hypothesis"],
                         "comparison": plan["comparison"],
                         "policy_sha256": result["policy_sha256"],
                         "model": {**parent["model"], "adapter_sha256": plan["adapter_manifest_sha256"],
                                   "served_model": plan["served_model"]},
                         "training_job": plan["training_job"], "deployment": result["deployment"]}
            self.controller.register_candidate(candidate)
        return {"endpoint": observed["endpoint"], "policy_identity": policy_identity, "candidate": candidate,
                "policy_path": str(root / "policy.json"),
                "parent_policy_path": (None if parent_policy_identity is None
                                       else str(root / "parent-policy.json"))}

    async def terminate(self, job_id):
        job, launch, plan = self.stored(job_id)
        if launch["termination_receipt"]:
            receipt = json.loads(launch["termination_receipt"])
            self.controller.provider_cleanup_confirmed(
                job_id, "modal-serving-terminated:" + digest(canonical(receipt)))
            return receipt
        if not launch["sandbox_id"]:
            raise LedgerConflict("Unresolved serving create must be reconciled before termination")
        self.controller.request_cleanup(job_id)
        observed = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        self.acknowledge(job_id, observed)
        await asyncio.wait_for(self.backend.terminate(launch["sandbox_id"]), 120)
        stopped = await asyncio.wait_for(self.backend.inspect(launch["sandbox_id"]), 30)
        self.acknowledge(job_id, stopped)
        if type(stopped.get("returncode")) is not int:
            raise RuntimeError("Serving sandbox termination is not confirmed")
        receipt = {"sandbox_id": launch["sandbox_id"], "returncode": stopped["returncode"],
                   "checked_at": datetime.now(timezone.utc).isoformat(), "billing_reconciled": False}
        with self.controller.ledger.transaction() as connection:
            connection.execute("UPDATE gameworld_serving_launches SET termination_receipt=? WHERE job_id=?",
                               (canonical(receipt).decode(), job_id))
        self.controller.provider_cleanup_confirmed(
            job_id, "modal-serving-terminated:" + digest(canonical(receipt)))
        return receipt
