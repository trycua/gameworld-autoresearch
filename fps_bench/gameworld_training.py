"""Controller-owned authentication for GameWorld SFT and rollout datasets."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_fleet import verify_artifact_receipt
from fps_bench.gameworld_grpo import verify_rollout_dataset
from fps_bench.gameworld_research import DEFAULT_CATALOG, DEFAULT_POLICY, load_policy
from fps_bench.training_data import verify_dataset


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SFT_SOURCE_KINDS = {"human-demonstrations", "teacher-policy", "state-oracle-distillation"}


def verify_sft_source(receipt, tasks):
    required = {"schema_version", "kind", "tasks", "rights", "artifact_sha256",
                "created_at", "evaluation_policy_contains_privileged_state"}
    if (not isinstance(receipt, dict) or set(receipt) != required or receipt["schema_version"] != 1
            or receipt["kind"] not in SFT_SOURCE_KINDS or receipt["tasks"] != sorted(set(tasks))
            or not isinstance(receipt["rights"], str) or not receipt["rights"].strip()
            or len(receipt["rights"]) > 1000 or not SHA256.fullmatch(receipt["artifact_sha256"])
            or receipt["evaluation_policy_contains_privileged_state"] is not False):
        raise ValueError("SFT source receipt is incomplete or unsafe")
    try:
        created = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("SFT source timestamp is invalid") from error
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError("SFT source timestamp must be timezone-aware and nonfuture")
    return receipt


def verify_sft_dataset(root, expected_hash, contract_hash, context, tasks, driver_sha256, source_receipt):
    tasks = sorted(set(tasks))
    verify_sft_source(source_receipt, tasks)
    if not tasks or not set(tasks) <= set(context["splits"]["train"]):
        raise ValueError("SFT dataset tasks must belong to the frozen train split")
    manifest, samples = verify_dataset(root, expected_hash, contract_hash)
    gameworld = manifest.get("gameworld")
    required = {"schema_version", "tasks", "driver_sha256", "source_receipt_sha256"}
    if (not isinstance(gameworld, dict) or set(gameworld) != required or gameworld["schema_version"] != 1
            or gameworld["tasks"] != tasks or gameworld["driver_sha256"] != driver_sha256
            or gameworld["source_receipt_sha256"] != digest(canonical(source_receipt))):
        raise ValueError("SFT dataset GameWorld provenance differs from controller admission")
    observed = set()
    identifiers = set()
    for sample in samples:
        identity = sample["id"]
        if not isinstance(identity, str) or identity in identifiers:
            raise ValueError("SFT samples require unique task-prefixed identities")
        identifiers.add(identity)
        matches = [task for task in tasks if identity.startswith(task + ":")]
        if len(matches) != 1:
            raise ValueError("SFT sample identity does not name one admitted train task")
        observed.add(matches[0])
    if observed != set(tasks):
        raise ValueError("SFT dataset does not contain every admitted train task")
    return manifest, samples


class GameWorldTrainingRegistry:
    def __init__(self, controller, policy_path=DEFAULT_POLICY, catalog_path=DEFAULT_CATALOG):
        self.controller = controller
        self.policy, self.context = load_policy(policy_path, catalog_path)
        with controller.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS gameworld_rollout_receipts ("
                               "job_id TEXT PRIMARY KEY REFERENCES jobs(id), root TEXT NOT NULL, "
                               "receipt TEXT NOT NULL, dataset_sha256 TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS gameworld_training_datasets ("
                               "sha256 TEXT PRIMARY KEY, root TEXT NOT NULL, jobs TEXT NOT NULL UNIQUE, "
                               "manifest TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS gameworld_sft_datasets ("
                               "sha256 TEXT PRIMARY KEY, root TEXT NOT NULL, candidate TEXT NOT NULL, "
                               "tasks TEXT NOT NULL, manifest TEXT NOT NULL, source_receipt TEXT NOT NULL)")

    def _rollout(self, connection, job_id, root, receipt):
        job = self.controller._job(connection, job_id)
        if (job["kind"] != "rollout" or job["state"] not in ("billing_pending", "cleaned")
                or not job["provider_id"] or not job["provider_cleanup_receipt"] or not job["result"]):
            raise LedgerConflict("An exported and provider-cleaned rollout job is required")
        specification = json.loads(job["specification"])
        assignment = specification["assignment"]
        envelope = json.loads(job["result"])
        result = envelope["result"]
        candidate = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
        if (receipt != verify_artifact_receipt(root, job_id, "rollout")
                or envelope["artifact_sha256"] != digest(canonical(receipt))
                or result.get("status") != "complete"
                or any(result.get(key) != value for key, value in {**assignment, "candidate": job["candidate"],
                                                                   "contract_sha256": self.controller.contract_hash}.items())
                or result.get("dataset_sha256") is None
                or assignment["policy_sha256"] != candidate["policy_sha256"]
                or assignment["driver_sha256"] != candidate["driver_sha256"]):
            raise LedgerConflict("Rollout artifact receipt differs from controller admission or result")
        identity = json.loads((Path(root) / "policy.json").read_bytes()) if (Path(root) / "policy.json").is_file() else None
        if identity is None:
            identity = json.loads((Path(root) / "dataset/rollouts.json").read_bytes())["policy"]
        verified = verify_rollout_dataset(
            Path(root) / "dataset", result["dataset_sha256"], policy=self.policy, context=self.context,
            expected_policy=identity, expected_driver_sha256=assignment["driver_sha256"])
        if digest(canonical(identity)) != assignment["policy_sha256"] or verified["groups"] != 1:
            raise LedgerConflict("Rollout policy or group count differs from controller admission")
        return result["dataset_sha256"], json.loads((Path(root) / "dataset/rollouts.json").read_bytes())

    def register_rollout(self, job_id, root, receipt):
        root = Path(root).resolve()
        encoded = canonical(receipt).decode()
        with self.controller.ledger.transaction() as connection:
            dataset_sha256, _ = self._rollout(connection, job_id, root, receipt)
            existing = connection.execute(
                "SELECT * FROM gameworld_rollout_receipts WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                if (existing["root"] != str(root) or existing["receipt"] != encoded
                        or existing["dataset_sha256"] != dataset_sha256):
                    raise LedgerConflict("Registered rollout custody is immutable")
                return dataset_sha256
            connection.execute("INSERT INTO gameworld_rollout_receipts VALUES (?,?,?,?)",
                               (job_id, str(root), encoded, dataset_sha256))
            self.controller.ledger._event(connection, "gameworld_rollout_registered", {
                "job_id": job_id, "dataset_sha256": dataset_sha256,
            })
            return dataset_sha256

    def export(self, job_ids, output):
        if not isinstance(job_ids, list) or not job_ids or job_ids != sorted(set(job_ids)):
            raise ValueError("Sorted unique rollout job IDs required")
        jobs_encoded = canonical(job_ids).decode()
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_training_datasets WHERE jobs=?", (jobs_encoded,)
            ).fetchone()
            if existing:
                manifest = json.loads(existing["manifest"])
                verify_rollout_dataset(existing["root"], existing["sha256"], policy=self.policy,
                                       context=self.context, expected_policy=manifest["policy"],
                                       expected_driver_sha256=manifest["driver_sha256"])
                return {"dataset_sha256": existing["sha256"], "root": existing["root"], "jobs": job_ids}
            datasets = []
            for job_id in job_ids:
                row = connection.execute(
                    "SELECT * FROM gameworld_rollout_receipts WHERE job_id=?", (job_id,)
                ).fetchone()
                if row is None:
                    raise LedgerConflict("Rollout custody is not registered")
                receipt = json.loads(row["receipt"])
                dataset_sha256, manifest = self._rollout(connection, job_id, Path(row["root"]), receipt)
                if dataset_sha256 != row["dataset_sha256"]:
                    raise LedgerConflict("Registered rollout dataset identity changed")
                datasets.append((Path(row["root"]) / "dataset", manifest))
        first = datasets[0][1]
        fixed = {key: first[key] for key in ("schema_version", "purpose", "catalog_manifest_sha256",
                                             "policy", "driver_sha256", "reward")}
        output = Path(output)
        groups, files, payloads = [], {}, {}
        for root, manifest in datasets:
            if any(manifest[key] != value for key, value in fixed.items()):
                raise ValueError("Combined rollout datasets changed policy, driver, catalog or reward")
            groups.extend(manifest["groups"])
            for name, expected in manifest["files"].items():
                data = (root / name).read_bytes()
                if digest(data) != expected or name in files and files[name] != expected:
                    raise ValueError("Rollout file collision or digest mismatch")
                files[name] = expected
                if name in payloads and payloads[name] != data:
                    raise ValueError("Rollout file collision changed content")
                payloads[name] = data
        manifest = {**fixed, "groups": groups, "files": files}
        payload = canonical(manifest)
        dataset_sha256 = digest(payload)
        if output.exists():
            if output.is_symlink() or not output.is_dir():
                raise ValueError("Training dataset destination is not a regular directory")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
            try:
                for name, data in payloads.items():
                    exclusive_write(temporary / name, data, 0o400)
                exclusive_write(temporary / "rollouts.json", payload, 0o400)
                verify_rollout_dataset(temporary, dataset_sha256, policy=self.policy, context=self.context,
                                       expected_policy=manifest["policy"],
                                       expected_driver_sha256=manifest["driver_sha256"])
                temporary.rename(output)
            except BaseException:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        verify_rollout_dataset(output, dataset_sha256, policy=self.policy, context=self.context,
                               expected_policy=manifest["policy"],
                               expected_driver_sha256=manifest["driver_sha256"])
        with self.controller.ledger.transaction() as connection:
            connection.execute("INSERT INTO gameworld_training_datasets VALUES (?,?,?,?)",
                               (dataset_sha256, str(output.resolve()), jobs_encoded, canonical(manifest).decode()))
            self.controller.ledger._event(connection, "gameworld_training_dataset_registered", {
                "dataset_sha256": dataset_sha256, "jobs": job_ids, "groups": len(groups),
            })
        return {"dataset_sha256": dataset_sha256, "root": str(output.resolve()), "jobs": job_ids}

    def register_sft(self, candidate_id, root, expected_hash, tasks, source_receipt):
        root = Path(root).resolve()
        tasks = sorted(set(tasks))
        with self.controller.ledger.transaction() as connection:
            candidate = json.loads(self.controller._candidate(connection, candidate_id)["manifest"])
        manifest, _ = verify_sft_dataset(
            root, expected_hash, self.controller.contract_hash, self.context, tasks,
            candidate["driver_sha256"], source_receipt)
        if candidate["model"]["adapter_sha256"] is not None:
            raise ValueError("The pilot SFT warm start must begin from the frozen base model")
        encoded = {"root": str(root), "candidate": candidate_id, "tasks": canonical(tasks).decode(),
                   "manifest": canonical(manifest).decode(),
                   "source_receipt": canonical(source_receipt).decode()}
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_sft_datasets WHERE sha256=?", (expected_hash,)
            ).fetchone()
            if existing:
                if any(existing[name] != value for name, value in encoded.items()):
                    raise LedgerConflict("Registered SFT dataset custody is immutable")
                return {"dataset_sha256": expected_hash, "root": str(root), "tasks": tasks}
            connection.execute(
                "INSERT INTO gameworld_sft_datasets VALUES (?,?,?,?,?,?)",
                (expected_hash, encoded["root"], candidate_id, encoded["tasks"],
                 encoded["manifest"], encoded["source_receipt"]),
            )
            self.controller.ledger._event(connection, "gameworld_sft_dataset_registered", {
                "dataset_sha256": expected_hash, "candidate": candidate_id,
                "tasks": tasks, "source_receipt_sha256": digest(canonical(source_receipt)),
            })
        return {"dataset_sha256": expected_hash, "root": str(root), "tasks": tasks}

    def authenticate(self, job_id):
        with self.controller.ledger.transaction() as connection:
            job = self.controller._job(connection, job_id)
            if job["kind"] != "training":
                raise LedgerConflict("GameWorld training job required")
            assignment = json.loads(job["specification"])["assignment"]
            if assignment["objective"] == "sft":
                row = connection.execute(
                    "SELECT * FROM gameworld_sft_datasets WHERE sha256=?", (assignment["dataset_sha256"],)
                ).fetchone()
                if row is None or row["candidate"] != job["candidate"]:
                    raise LedgerConflict("SFT dataset is not registered for the training source candidate")
                candidate = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
                tasks = json.loads(row["tasks"])
                source_receipt = json.loads(row["source_receipt"])
                manifest, _ = verify_sft_dataset(
                    row["root"], row["sha256"], self.controller.contract_hash, self.context, tasks,
                    candidate["driver_sha256"], source_receipt)
                policy_path = Path(candidate.get("policy_path", ""))
                if (assignment["tasks"] != tasks or assignment["driver_sha256"] != candidate["driver_sha256"]
                        or not policy_path.is_file() or policy_path.is_symlink()
                        or digest(policy_path.read_bytes()) != assignment["policy_sha256"]
                        or candidate["policy_sha256"] != assignment["policy_sha256"]):
                    raise LedgerConflict("SFT training assignment differs from registered demonstrations")
                policy_identity = json.loads(policy_path.read_bytes())
                return {"dataset_sha256": row["sha256"], "root": row["root"], "jobs": [],
                        "manifest": manifest, "policy": policy_identity,
                        "source_receipt": source_receipt}
            row = connection.execute(
                "SELECT * FROM gameworld_training_datasets WHERE sha256=?", (assignment["dataset_sha256"],)
            ).fetchone()
            if row is None:
                raise LedgerConflict("GameWorld training dataset is not controller-registered")
            manifest = json.loads(row["manifest"])
            verified = verify_rollout_dataset(
                row["root"], row["sha256"], policy=self.policy, context=self.context,
                expected_policy=manifest["policy"], expected_driver_sha256=manifest["driver_sha256"])
            tasks = sorted({f"{group['game']}--{group['task']}" for group in manifest["groups"]})
            if (assignment["objective"] != "grpo" or tasks != sorted(assignment["tasks"])
                    or assignment["policy_sha256"] != digest(canonical(manifest["policy"]))
                    or assignment["driver_sha256"] != manifest["driver_sha256"]
                    or verified["groups"] != len(manifest["groups"])):
                raise LedgerConflict("Training assignment differs from authenticated GameWorld rollouts")
            return {"dataset_sha256": row["sha256"], "root": row["root"],
                    "jobs": json.loads(row["jobs"]), "manifest": manifest,
                    "policy": manifest["policy"]}

    def worker_plan(self, job_id, authenticated=None):
        authenticated = authenticated or self.authenticate(job_id)
        with self.controller.ledger.transaction() as connection:
            job = self.controller._job(connection, job_id)
            assignment = json.loads(job["specification"])["assignment"]
            candidate = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
        if assignment["objective"] == "sft" and candidate["model"]["adapter_sha256"] is not None:
            raise LedgerConflict("SFT warm start cannot silently continue an existing adapter")
        return {"kind": "gameworld-" + assignment["objective"], "objective": assignment["objective"],
                "steps": assignment["steps"], "dataset_sha256": authenticated["dataset_sha256"],
                "tasks": assignment["tasks"],
                "policy_sha256": assignment["policy_sha256"],
                "driver_sha256": assignment["driver_sha256"],
                "parent_adapter_sha256": candidate["model"]["adapter_sha256"]}
