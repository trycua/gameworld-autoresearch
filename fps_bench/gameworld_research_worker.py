"""Durable Pi research and driver-patch materialization for GameWorld."""

import asyncio
import json
import os
from pathlib import Path
import time
from urllib import request

from fps_bench.driver_candidate import MAX_PATCH_BYTES, validate_patch
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_research import IDENTIFIER, SHA256
from fps_bench.research_gateway import MAX_BODY, MODELS, NoRedirect


ROOT = Path(__file__).resolve().parents[1]
MAX_SOURCE_BUNDLE = 512 * 1024
RESEARCH_TIMEOUT = 660
PATCH_TIMEOUT = 360
RESEARCH_GATEWAY_MODELS = "http://127.0.0.1:8765/v1/models"


def gateway_preflight(token):
    outgoing = request.Request(RESEARCH_GATEWAY_MODELS, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json",
    })
    opener = request.build_opener(NoRedirect())
    with opener.open(outgoing, timeout=5) as response:
        payload = response.read(MAX_BODY + 1)
    if len(payload) > MAX_BODY:
        raise ValueError("Research gateway model response exceeds its bound")
    result = json.loads(payload)
    models = {row.get("id") for row in result.get("data", []) if isinstance(row, dict)}
    if models != set(MODELS):
        raise ValueError("Research gateway model inventory differs from the pinned campaign aliases")
    return sorted(models)


def research_environment(source=None):
    source = os.environ if source is None else source
    environment = {
        "PATH": source.get("PATH", "/usr/bin:/bin"),
        "HOME": str(ROOT / ".pi-local/home"),
        "PI_CODING_AGENT_DIR": str(ROOT / ".pi-local/agent"),
        "LANG": source.get("LANG", "C.UTF-8"),
        "GAMEWORLD_RESEARCH_TOKEN": source.get("GAMEWORLD_RESEARCH_TOKEN", ""),
    }
    for name in ("PLAYWRIGHT_EXECUTABLE_PATH", "GAMEWORLD_SEARXNG_URL", "SSL_CERT_FILE"):
        if source.get(name):
            environment[name] = source[name]
    return environment


class PiResearchExecutor:
    def __init__(self, program=None, environment=None):
        self.program = Path(program or ROOT / "tools/pi/gameworld-proposal.mjs")
        self.environment = research_environment(environment)
        Path(self.environment["HOME"]).mkdir(parents=True, exist_ok=True)
        if len(self.environment["GAMEWORLD_RESEARCH_TOKEN"]) < 32:
            raise ValueError("Pi research requires the local metered gateway credential")
        if not self.program.is_file() or self.program.is_symlink():
            raise ValueError("Pinned Pi proposal program is missing or unsafe")

    async def run(self, kind, context_path, output_path, timeout):
        log_path = output_path.parent / "worker.log"
        with log_path.open("xb") as log:
            process = await asyncio.create_subprocess_exec(
                "node", str(self.program), "--kind", kind, "--context", str(context_path),
                "--output", str(output_path), cwd=ROOT, env=self.environment,
                stdout=log, stderr=asyncio.subprocess.STDOUT,
            )
            try:
                await asyncio.wait_for(process.wait(), timeout)
            except TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 10)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise
        if process.returncode != 0:
            tail = log_path.read_bytes()[-4000:].decode(errors="replace")
            raise RuntimeError(f"Pi {kind} worker failed ({process.returncode}): {tail}")

    async def preflight(self):
        return await asyncio.to_thread(
            gateway_preflight, self.environment["GAMEWORLD_RESEARCH_TOKEN"])


class GameWorldResearchWorker:
    def __init__(self, coordinator, output, executor=None, sft_source_catalog=None):
        self.coordinator = coordinator
        self.supervisor = coordinator.supervisor
        self.controller = coordinator.controller
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.executor = executor or PiResearchExecutor()
        self.sft_sources = self._load_sft_sources(sft_source_catalog)
        with self.controller.ledger.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS gameworld_research_attempts ("
                "id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL, ordinal INTEGER NOT NULL, "
                "input_sha256 TEXT NOT NULL, state TEXT NOT NULL, output_sha256 TEXT, error_type TEXT, "
                "started_at INTEGER NOT NULL, finished_at INTEGER, UNIQUE(kind,owner,ordinal))"
            )
            interrupted = connection.execute(
                "SELECT id FROM gameworld_research_attempts WHERE state='running' ORDER BY started_at"
            ).fetchall()
            for row in interrupted:
                connection.execute(
                    "UPDATE gameworld_research_attempts SET state='failed',error_type=?,finished_at=? WHERE id=?",
                    ("InterruptedResearchAttempt", int(time.time()), row["id"]),
                )
                self.controller.ledger._event(connection, "gameworld_research_attempt_failed", {
                    "id": row["id"], "error_type": "InterruptedResearchAttempt",
                })
        if self.consecutive_failures() >= 3 and not self.controller.snapshot()["controller"]["stopped"]:
            self.controller.stop("Three consecutive GameWorld research worker failures")

    def _load_sft_sources(self, catalog_path):
        if catalog_path is None:
            return {}
        path = Path(catalog_path)
        if not path.is_file() or path.is_symlink():
            raise ValueError("SFT source catalog must be a regular trusted-host file")
        catalog = json.loads(path.read_bytes())
        if (not isinstance(catalog, dict) or set(catalog) != {"schema_version", "sources"}
                or catalog["schema_version"] != 1 or not isinstance(catalog["sources"], list)):
            raise ValueError("Unexpected SFT source catalog schema")
        allowed_tasks = set(self.supervisor.context["splits"]["train"])
        sources = {}
        for source in catalog["sources"]:
            required = {"id", "tasks", "dataset_root", "dataset_sha256", "source_receipt"}
            if (not isinstance(source, dict) or set(source) != required
                    or not IDENTIFIER.fullmatch(source["id"])
                    or not isinstance(source["tasks"], list) or not source["tasks"]
                    or len(source["tasks"]) != len(set(source["tasks"]))
                    or not set(source["tasks"]) <= allowed_tasks
                    or not SHA256.fullmatch(source["dataset_sha256"])):
                raise ValueError("Invalid SFT source catalog entry")
            dataset_root = Path(source["dataset_root"])
            receipt = Path(source["source_receipt"])
            if (not dataset_root.is_dir() or dataset_root.is_symlink()
                    or not receipt.is_file() or receipt.is_symlink()):
                raise ValueError("SFT source custody path is missing or unsafe")
            if source["id"] in sources:
                raise ValueError("SFT source catalog repeats an identity")
            sources[source["id"]] = {**source, "dataset_root": dataset_root, "source_receipt": receipt}
        return sources

    def _driver_files(self):
        files = []
        for prefix in self.supervisor.policy["driver"]["allowed_source_prefixes"]:
            directory = ROOT / prefix
            if not directory.is_dir() or directory.is_symlink():
                raise ValueError("Allowlisted driver source directory is missing or unsafe")
            for path in sorted(directory.rglob("*.rs")):
                if path.is_file() and not path.is_symlink():
                    files.append(str(path.relative_to(ROOT)))
        if not files:
            raise ValueError("No allowlisted driver source files are available")
        return sorted(set(files))

    def _history(self):
        with self.controller.ledger.transaction() as connection:
            hypotheses = []
            for row in connection.execute(
                    "SELECT id,round,track,manifest,state FROM gameworld_hypotheses ORDER BY round"):
                value = {key: row[key] for key in ("id", "round", "track", "state")}
                value["proposal"] = json.loads(row["manifest"])
                action = connection.execute(
                    "SELECT result FROM gameworld_actions WHERE hypothesis=?", (row["id"],)
                ).fetchone()
                value["result"] = None if action is None or action["result"] is None else json.loads(action["result"])
                workflow = connection.execute(
                    "SELECT state,decision FROM gameworld_workflows WHERE proposal_id=?", (row["id"],)
                ).fetchone()
                value["workflow"] = None if workflow is None else {
                    "state": workflow["state"],
                    "decision": None if workflow["decision"] is None else json.loads(workflow["decision"]),
                }
                hypotheses.append(value)
        return hypotheses

    def recommended_track(self, history=None):
        history = self._history() if history is None else history
        qualified = {track: any(row["track"] == track and row["state"] == "qualified" for row in history)
                     for track in ("driver", "model")}
        if qualified["driver"] != qualified["model"]:
            return "model" if qualified["driver"] else "driver"
        attempted = {track: sum(row["track"] == track for row in history) for track in qualified}
        return min(attempted, key=lambda track: (attempted[track], 0 if track == "driver" else 1))

    def proposal_context(self):
        history = self._history()
        snapshot = self.supervisor.snapshot()
        return {
            "schema_version": 1,
            "kind": "proposal",
            "campaign": snapshot["budget"]["campaign"],
            "recommended_track": self.recommended_track(history),
            "round": len(history) + 1,
            "policy": self.supervisor.policy,
            "splits": self.supervisor.context["splits"],
            "baseline": self.supervisor.baseline,
            "history": history,
            "driver_source_files": self._driver_files(),
            "sft_sources": [{
                "id": source["id"], "tasks": source["tasks"],
                "dataset_sha256": source["dataset_sha256"],
                "source_receipt_sha256": digest(source["source_receipt"].read_bytes()),
            } for source in self.sft_sources.values()],
            "budget": snapshot["budget"]["resources"],
        }

    def patch_context(self, workflow):
        with self.controller.ledger.transaction() as connection:
            proposal = self.coordinator._proposal(connection, workflow["proposal_id"])
        sources = []
        total = 0
        for name in proposal["experiment"]["target_paths"]:
            path = ROOT / name
            if not path.is_file() or path.is_symlink():
                raise ValueError("Driver proposal targets a missing or unsafe source file")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_SOURCE_BUNDLE:
                raise ValueError("Driver patch source bundle exceeds 512 KiB")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("Driver patch source must be UTF-8 text") from error
            sources.append({"path": name, "sha256": digest(data), "content": text})
        return {
            "schema_version": 1,
            "kind": "driver-patch",
            "proposal": proposal,
            "sources": sources,
            "required_contract_tests": self.supervisor.policy["driver"]["required_contract_tests"],
        }

    def _begin(self, kind, owner, context):
        input_hash = digest(canonical(context))
        with self.controller.ledger.transaction() as connection:
            ordinal = connection.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 FROM gameworld_research_attempts WHERE kind=? AND owner=?",
                (kind, owner),
            ).fetchone()[0]
            attempt_id = "gw-research-" + digest(canonical([kind, owner, ordinal, input_hash]))[:32]
            connection.execute(
                "INSERT INTO gameworld_research_attempts VALUES (?,?,?,?,?,'running',NULL,NULL,?,NULL)",
                (attempt_id, kind, owner, ordinal, input_hash, int(time.time())),
            )
            self.controller.ledger._event(connection, "gameworld_research_attempt_started", {
                "id": attempt_id, "kind": kind, "owner": owner, "ordinal": ordinal,
                "input_sha256": input_hash,
            })
        return attempt_id, self.output / attempt_id

    @staticmethod
    def _prepare(directory, context):
        directory.mkdir(mode=0o700)
        context_path = directory / "context.json"
        exclusive_write(context_path, canonical(context), 0o400)
        return context_path

    def _finish(self, attempt_id, output_hash):
        with self.controller.ledger.transaction() as connection:
            attempt = connection.execute(
                "SELECT kind,started_at FROM gameworld_research_attempts WHERE id=?", (attempt_id,)
            ).fetchone()
            connection.execute(
                "UPDATE gameworld_research_attempts SET state='complete',output_sha256=?,finished_at=? WHERE id=?",
                (output_hash, int(time.time()), attempt_id),
            )
            self.controller.ledger._event(connection, "gameworld_research_attempt_completed", {
                "id": attempt_id, "output_sha256": output_hash,
            })
        self.supervisor._emit(attempt_id, {
            "gameworld_research_worker_attempts": 1,
            "gameworld_research_worker_failures": 0,
            "gameworld_research_worker_seconds": max(0, time.time() - attempt["started_at"]),
        }, attempt["kind"] + "-complete")

    def _fail(self, attempt_id, error):
        with self.controller.ledger.transaction() as connection:
            attempt = connection.execute(
                "SELECT kind,started_at FROM gameworld_research_attempts WHERE id=?", (attempt_id,)
            ).fetchone()
            connection.execute(
                "UPDATE gameworld_research_attempts SET state='failed',error_type=?,finished_at=? WHERE id=?",
                (type(error).__name__, int(time.time()), attempt_id),
            )
            self.controller.ledger._event(connection, "gameworld_research_attempt_failed", {
                "id": attempt_id, "error_type": type(error).__name__,
            })
        self.supervisor._emit(attempt_id, {
            "gameworld_research_worker_attempts": 1,
            "gameworld_research_worker_failures": 1,
            "gameworld_research_worker_seconds": max(0, time.time() - attempt["started_at"]),
        }, attempt["kind"] + "-failed")
        if self.consecutive_failures() >= 3 and not self.controller.snapshot()["controller"]["stopped"]:
            self.controller.stop("Three consecutive GameWorld research worker failures")

    def consecutive_failures(self):
        with self.controller.ledger.transaction() as connection:
            rows = connection.execute(
                "SELECT state FROM gameworld_research_attempts ORDER BY started_at DESC,rowid DESC"
            ).fetchall()
        failures = 0
        for row in rows:
            if row["state"] != "failed":
                break
            failures += 1
        return failures

    def can_propose(self):
        snapshot = self.supervisor.snapshot()
        if (snapshot["budget"]["campaign"]["frozen"]
                or len(snapshot["hypotheses"]) >= self.supervisor.policy["candidate_policy"]["maximum_candidates"]
                or snapshot["next"] is not None or snapshot["joint_ready"]):
            return False
        history = self._history()
        if snapshot["budget"]["resources"]["litellm_tokens"]["normal_remaining"] < 1:
            return False
        if (self.recommended_track(history) == "model"
                and snapshot["budget"]["resources"]["modal_micro_usd"]["normal_remaining"] < 2):
            return False
        active = {row["state"] for row in self.coordinator.snapshot()["workflows"]
                  if row["state"] not in ("complete", "rejected", "qualified_serving_live")}
        return not active

    async def propose(self):
        if not self.can_propose():
            return None
        if hasattr(self.executor, "preflight"):
            await self.executor.preflight()
        context = self.proposal_context()
        owner = f"round-{context['round']}-{context['recommended_track']}"
        attempt_id, directory = self._begin("proposal", owner, context)
        generated = directory / "generated.json"
        try:
            context_path = self._prepare(directory, context)
            await self.executor.run("proposal", context_path, generated, RESEARCH_TIMEOUT)
            if not generated.is_file() or generated.is_symlink() or generated.stat().st_size > MAX_PATCH_BYTES:
                raise ValueError("Pi proposal output is missing, unsafe or oversized")
            proposal = json.loads(generated.read_bytes())
            registered = self.coordinator.register(proposal)
            payload = canonical(proposal)
            exclusive_write(directory / "proposal.json", payload, 0o400)
            self._finish(attempt_id, digest(payload))
            return {"kind": "proposal", "outcome": "registered", "attempt": attempt_id,
                    "proposal": registered["id"]}
        except Exception as error:
            self._fail(attempt_id, error)
            return {"kind": "proposal", "outcome": "failed", "attempt": attempt_id,
                    "error_type": type(error).__name__}

    async def materialize_driver_patch(self, action):
        if hasattr(self.executor, "preflight"):
            await self.executor.preflight()
        workflow = self.coordinator.workflow(action["workflow"])
        context = self.patch_context(workflow)
        attempt_id, directory = self._begin(
            "driver-patch", workflow["proposal_id"], context)
        generated = directory / "generated.json"
        try:
            context_path = self._prepare(directory, context)
            await self.executor.run("driver-patch", context_path, generated, PATCH_TIMEOUT)
            if not generated.is_file() or generated.is_symlink() or generated.stat().st_size > MAX_PATCH_BYTES:
                raise ValueError("Pi patch output is missing, unsafe or oversized")
            result = json.loads(generated.read_bytes())
            if (not isinstance(result, dict) or set(result) != {"patch", "rationale"}
                    or not isinstance(result["patch"], str)
                    or not isinstance(result["rationale"], str) or not result["rationale"].strip()
                    or len(result["rationale"]) > 4000):
                raise ValueError("Pi patch output has an invalid schema")
            patch = result["patch"].encode("ascii")
            manifest = validate_patch(patch, self.supervisor.policy["driver"]["allowed_source_prefixes"])
            if set(manifest["paths"]) != set(context["proposal"]["experiment"]["target_paths"]):
                raise ValueError("Pi patch paths differ from the approved proposal")
            patch_path = directory / "candidate.patch"
            exclusive_write(patch_path, patch, 0o400)
            details = self.coordinator.attach_driver_patch(workflow["action_id"], patch_path)
            receipt = canonical({"patch_sha256": details["patch_sha256"],
                                 "rationale": result["rationale"]})
            exclusive_write(directory / "result.json", receipt, 0o400)
            self._finish(attempt_id, digest(receipt))
            return {"kind": "driver-patch", "outcome": "attached", "attempt": attempt_id,
                    "workflow": workflow["proposal_id"], "patch_sha256": details["patch_sha256"]}
        except Exception as error:
            self._fail(attempt_id, error)
            return {"kind": "driver-patch", "outcome": "failed", "attempt": attempt_id,
                    "workflow": workflow["proposal_id"], "error_type": type(error).__name__}

    async def materialize_required(self):
        events = []
        for action in self.coordinator.required_actions():
            if action["action"] == "attach-driver-patch":
                events.append(await self.materialize_driver_patch(action))
                break
            if action["action"] == "attach-authenticated-sft-dataset":
                workflow = self.coordinator.workflow(action["workflow"])
                with self.controller.ledger.transaction() as connection:
                    proposal = self.coordinator._proposal(connection, workflow["proposal_id"])
                source = self.sft_sources.get(proposal["experiment"]["sft_source_id"])
                if source is None:
                    continue
                self.coordinator.attach_sft_dataset(
                    workflow["action_id"], source["dataset_root"], source["dataset_sha256"],
                    source["source_receipt"])
                events.append({"kind": "sft-dataset", "outcome": "attached",
                               "workflow": workflow["proposal_id"], "source": source["id"]})
                break
        return events
