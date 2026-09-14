"""Trusted Fleet execution for GameWorld driver builds and interactive rollouts."""

import asyncio
import io
import json
from pathlib import Path, PurePosixPath
import shlex
import tarfile
import time
from urllib.parse import urlsplit

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_candidate_episode import verify_artifacts as verify_evaluation_artifacts
from fps_bench.gameworld_grpo import policy_digest, validate_policy_identity, verify_rollout_dataset
from fps_bench.gameworld_research import load_policy


MAX_DRIVER_ARCHIVE = 128 * 1024 * 1024
MAX_ROLLOUT_ARCHIVE = 640 * 1024 * 1024
MAX_EVALUATION_ARCHIVE = 640 * 1024 * 1024


def extract_output_archive(data, output, maximum):
    if not isinstance(data, bytes) or not data or len(data) > maximum:
        raise ValueError("Fleet artifact archive is empty or exceeds its transfer bound")
    output = Path(output)
    if output.exists():
        raise FileExistsError("Refusing to overwrite a Fleet artifact directory")
    total = 0
    files = []
    names = set()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("Fleet artifact archive has no members")
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "output"
                    or not (member.isdir() or member.isfile())):
                raise ValueError("Fleet artifact archive contains an unsafe member")
            if member.isfile():
                if len(path.parts) == 1 or path in names:
                    raise ValueError("Fleet artifact archive repeats or replaces its root")
                names.add(path)
                total += member.size
                if total > maximum:
                    raise ValueError("Fleet artifacts exceed their uncompressed transfer bound")
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("Fleet artifact file cannot be read")
                files.append((path.parts[1:], source.read()))
    if any(parent in names for name in names for parent in name.parents if str(parent) != "."):
        raise ValueError("Fleet artifact archive has conflicting file paths")
    output.mkdir(parents=True)
    for parts, payload in files:
        destination = output.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        exclusive_write(destination, payload, 0o400)
    return output


def artifact_receipt(root, job_id, operation):
    root = Path(root)
    files = {str(path.relative_to(root)): digest(path.read_bytes())
             for path in sorted(root.rglob("*"))
             if path.is_file() and path.name != "artifact-receipt.json"}
    if not files:
        raise ValueError("Fleet worker exported no files")
    return {"schema_version": 1, "job_id": job_id, "operation": operation,
            "root": str(root.resolve()), "files": files}


def verify_artifact_receipt(root, job_id, operation):
    root = Path(root)
    path = root / "artifact-receipt.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing immutable Fleet artifact receipt")
    receipt = json.loads(path.read_bytes())
    if receipt != artifact_receipt(root, job_id, operation):
        raise LedgerConflict("Fleet artifact custody changed after export")
    return receipt


class FleetSandboxBackend:
    async def stage(self, sandbox, remote_root, files):
        result = await sandbox.shell.run(
            f"rm -rf {shlex.quote(remote_root)} && mkdir -m 700 {shlex.quote(remote_root)}", timeout=30)
        if not result.success:
            raise RuntimeError("Fleet staging directory could not be created")
        for name, data in files.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or len(data) > 16 * 1024 * 1024:
                raise ValueError("Unsafe or oversized Fleet staging input")
            await sandbox.files.write_bytes(f"{remote_root}/{name}", data)

    async def run(self, sandbox, remote_root, command, timeout):
        if type(timeout) is not int or timeout <= 0:
            raise ValueError("Fleet worker timeout must be a positive integer")
        completion = remote_root + "/output/provider-result.json"
        worker_log = remote_root + "/worker.log"
        wrapped = (
            "set +e\n"
            f"timeout --kill-after=5s {timeout}s bash -c {shlex.quote(command)} "
            f">{shlex.quote(worker_log)} 2>&1\n"
            "worker_rc=$?\n"
            f"mkdir -p {shlex.quote(remote_root + '/output')}\n"
            f"mv {shlex.quote(worker_log)} {shlex.quote(remote_root + '/output/worker.log')}\n"
            f"printf '{{\"returncode\":%s}}\\n' \"$worker_rc\" > "
            f"{shlex.quote(completion + '.tmp')} && "
            f"mv {shlex.quote(completion + '.tmp')} {shlex.quote(completion)}\n"
            "exit 0\n"
        )
        launcher = (
            "import subprocess; "
            f"log = open({remote_root + '/launcher.log'!r}, 'ab'); "
            f"process = subprocess.Popen(['bash', '-c', {wrapped!r}], "
            "stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, "
            "start_new_session=True, close_fds=True); print(process.pid)"
        )
        launch = "python3 -c " + shlex.quote(launcher)
        result = await sandbox.shell.run(launch, timeout=15)
        if not result.success:
            raise RuntimeError("Fleet worker wrapper did not launch")
        deadline = time.monotonic() + timeout + 15
        while time.monotonic() < deadline:
            result = await sandbox.shell.run(f"test -f {shlex.quote(completion)}", timeout=10)
            if result.success:
                return
            if result.returncode != 1:
                raise RuntimeError("Fleet worker completion probe failed")
            await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
        raise TimeoutError("Fleet worker did not publish completion within its bound")

    async def collect(self, sandbox, remote_root, output, maximum):
        archive = remote_root + ".tar.gz"
        result = await sandbox.shell.run(
            f"rm -f {shlex.quote(archive)} && tar -C {shlex.quote(remote_root)} -czf "
            f"{shlex.quote(archive)} output",
            timeout=120,
        )
        if not result.success:
            raise RuntimeError("Fleet worker artifacts are not ready for export")
        total = await sandbox.files.size(archive)
        if type(total) is not int or not 0 < total <= maximum:
            raise ValueError("Fleet artifact archive size exceeds the transfer bound")
        chunks = []
        offset = 0
        while offset < total:
            chunk = await sandbox.files.read_bytes(archive, offset=offset, length=min(1024 * 1024, total - offset))
            if not chunk:
                raise IOError("Fleet artifact archive ended before its declared size")
            chunks.append(chunk)
            offset += len(chunk)
        return extract_output_archive(b"".join(chunks), output, maximum)

    async def cleanup(self, sandbox, remote_root):
        result = await sandbox.shell.run(
            f"rm -rf {shlex.quote(remote_root)} {shlex.quote(remote_root + '.tar.gz')}", timeout=30)
        if not result.success:
            raise RuntimeError("Fleet staging cleanup failed")


class GameWorldFleetExecutor:
    def __init__(self, controller, lifecycle, output, backend=None):
        self.controller, self.lifecycle = controller, lifecycle
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.backend = backend or FleetSandboxBackend()
        self.policy, self.context = load_policy()
        with controller.ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS gameworld_fleet_attempts ("
                               "job_id TEXT PRIMARY KEY REFERENCES jobs(id), operation TEXT NOT NULL, "
                               "remote_root TEXT NOT NULL, started_at INTEGER NOT NULL)")

    def context_for(self, job_id, kind):
        with self.controller.ledger.transaction() as connection:
            self.controller._controller(connection)
            job = dict(self.controller._job(connection, job_id))
            if job["kind"] != kind:
                raise ValueError("Fleet executor received the wrong job kind")
            candidate = json.loads(self.controller._candidate(connection, job["candidate"])["manifest"])
            return job, json.loads(job["specification"]), candidate

    def attempt(self, job_id, operation, remote_root):
        with self.controller.ledger.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM gameworld_fleet_attempts WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                if existing["operation"] != operation or existing["remote_root"] != remote_root:
                    raise LedgerConflict("Fleet worker attempt identity changed")
                return True
            connection.execute("INSERT INTO gameworld_fleet_attempts VALUES (?,?,?,?)",
                               (job_id, operation, remote_root, int(time.time())))
            self.controller.ledger._event(connection, "gameworld_fleet_worker_attempted", {
                "job_id": job_id, "operation": operation, "remote_root": remote_root,
            })
            return False

    async def execute(self, job_id, operation, staged, command, maximum):
        local = self.output / job_id
        if (local / "artifact-receipt.json").is_file():
            return None, local, verify_artifact_receipt(local, job_id, operation)
        remote_root = "/tmp/gw-" + digest(canonical([job_id, operation]))[:24]
        sandbox = await self.lifecycle.acquire(job_id)
        attempted = self.attempt(job_id, operation, remote_root)
        if not attempted:
            await self.backend.stage(sandbox, remote_root, staged)
            timeout = max(30, self.lifecycle.job(job_id)["deadline"] - int(time.time()) - 30)
            await self.backend.run(sandbox, remote_root, command(remote_root), timeout)
        root = await self.backend.collect(sandbox, remote_root, local, maximum)
        receipt = artifact_receipt(root, job_id, operation)
        exclusive_write(root / "artifact-receipt.json", canonical(receipt), 0o400)
        return sandbox, root, receipt

    async def finish_provider(self, job_id, sandbox, operation):
        if sandbox is not None:
            remote_root = "/tmp/gw-" + digest(canonical([job_id, operation]))[:24]
            await self.backend.cleanup(sandbox, remote_root)
        return await self.lifecycle.release(job_id)

    async def driver_candidate(self, job_id, proposal_path, patch_path):
        job, specification, parent = self.context_for(job_id, "driver_build")
        assignment = specification["assignment"]
        proposal_bytes, patch = Path(proposal_path).read_bytes(), Path(patch_path).read_bytes()
        proposal = json.loads(proposal_bytes)
        if (assignment.get("operation") != "driver-candidate" or assignment.get("pool") != self.lifecycle.pool
                or canonical(proposal) != proposal_bytes or proposal.get("id") != assignment.get("proposal_id")
                or digest(proposal_bytes) != assignment.get("proposal_sha256")
                or digest(patch) != assignment.get("patch_sha256")):
            raise ValueError("Driver worker inputs differ from the admitted proposal and patch")

        def command(root):
            return (
                f"/opt/gameworld-venv/bin/python /opt/gameworld-autoresearch/scripts/gameworld_driver_worker.py "
                f"--proposal {shlex.quote(root + '/proposal.json')} "
                f"--proposal-sha256 {shlex.quote(assignment['proposal_sha256'])} "
                f"--patch {shlex.quote(root + '/candidate.patch')} "
                f"--output {shlex.quote(root + '/output')}"
            )

        sandbox, root, receipt = await self.execute(
            job_id, "driver-candidate", {"proposal.json": proposal_bytes, "candidate.patch": patch},
            command, MAX_DRIVER_ARCHIVE)
        provider = json.loads((root / "provider-result.json").read_bytes())
        if provider != {"returncode": 0}:
            result = {"status": "failed", "candidate_id": proposal["id"] + "-candidate",
                      "error_type": json.loads((root / "error.json").read_bytes()).get("error_type", "WorkerError")}
            self.controller.record_result(job_id, result, digest(canonical(receipt)))
            await self.finish_provider(job_id, sandbox, "driver-candidate")
            return {"result": result, "candidate": None, "artifacts": receipt}
        result_bytes = (root / "result.json").read_bytes()
        result = json.loads(result_bytes)
        manifest = json.loads((root / "driver-manifest.json").read_bytes())
        binary = (root / "cua-driver").read_bytes()
        if (canonical(result) != result_bytes or result.get("proposal_sha256") != assignment["proposal_sha256"]
                or result.get("patch_sha256") != assignment["patch_sha256"]
                or result.get("manifest_sha256") != digest(canonical(manifest))
                or result.get("driver_sha256") != digest(binary)
                or manifest.get("binary") != {"path": "cua-driver", "sha256": result["driver_sha256"]}):
            raise ValueError("Driver worker artifacts differ from admitted identities")
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        await self.finish_provider(job_id, sandbox, "driver-candidate")
        candidate = {
            **{key: parent[key] for key in ("contract_hash", "image", "model", "policy_sha256")},
            "id": result["candidate_id"], "parent": job["candidate"], "change_class": "driver",
            "hypothesis": proposal["hypothesis"], "driver_sha256": result["driver_sha256"],
            "patch_sha256": result["patch_sha256"], "proposal_sha256": result["proposal_sha256"],
            "comparison": proposal["id"],
            "artifact_sha256": digest(canonical(receipt)), "artifact_root": str(root.resolve()),
        }
        self.controller.register_candidate(candidate)
        return {"result": result, "candidate": candidate, "artifacts": receipt}

    async def rollout(self, job_id, policy_identity_path, qwen_environment, driver_binary=None):
        job, specification, candidate = self.context_for(job_id, "rollout")
        assignment = specification["assignment"]
        identity_bytes = Path(policy_identity_path).read_bytes()
        identity = json.loads(identity_bytes)
        if canonical(identity) != identity_bytes or policy_digest(identity) != assignment["policy_sha256"]:
            raise ValueError("Rollout policy identity differs from controller admission")
        validate_policy_identity(identity, self.policy)
        parsed = urlsplit(qwen_environment.get("QWEN_BASE_URL", ""))
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or digest(qwen_environment["QWEN_BASE_URL"].rstrip("/").encode())
                != identity["deployment"]["endpoint_sha256"]
                or len(qwen_environment.get("QWEN_API_KEY", "")) < 32):
            raise ValueError("Rollout serving credentials or endpoint differ from the policy identity")
        driver = b""
        if candidate["driver_sha256"] != assignment["driver_sha256"]:
            raise ValueError("Rollout driver differs from the source candidate")
        driver_path = "/usr/local/bin/cua-driver"
        staged = {"policy.json": identity_bytes}
        if driver_binary is not None:
            driver = Path(driver_binary).read_bytes()
            if digest(driver) != assignment["driver_sha256"]:
                raise ValueError("Rollout driver binary differs from controller admission")
            staged["cua-driver"] = driver
        env = "\n".join(f"export {name}={shlex.quote(qwen_environment[name])}"
                         for name in ("QWEN_API_KEY", "QWEN_BASE_URL")) + "\n"
        staged["qwen.env"] = env.encode()
        worker_assignment = {
            "schema_version": 1, "group_id": assignment["group_id"], "game": assignment["game"],
            "task": assignment["task"], "seed": assignment["seed"], "members": assignment["members"],
            "max_steps": assignment["max_steps"],
            "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
            "driver_sha256": assignment["driver_sha256"],
        }
        staged["assignment.json"] = canonical(worker_assignment)

        def command(root):
            selected_driver = root + "/cua-driver" if driver else driver_path
            setup = f"chmod 500 {shlex.quote(selected_driver)} && " if driver else ""
            return (
                f"chmod 600 {shlex.quote(root + '/qwen.env')} && . {shlex.quote(root + '/qwen.env')} && "
                f"rm -f {shlex.quote(root + '/qwen.env')} && export QWEN_API_KEY QWEN_BASE_URL DISPLAY=:1 "
                f"GAMEWORLD_HOME=/opt/GameWorld && {setup}"
                f"/opt/gameworld-venv/bin/python /opt/gameworld-autoresearch/scripts/gameworld_rollout_worker.py "
                f"--assignment {shlex.quote(root + '/assignment.json')} "
                f"--policy-identity {shlex.quote(root + '/policy.json')} "
                f"--output {shlex.quote(root + '/output')} --driver {shlex.quote(selected_driver)}"
            )

        sandbox, root, receipt = await self.execute(
            job_id, "rollout", staged, command, MAX_ROLLOUT_ARCHIVE)
        provider = json.loads((root / "provider-result.json").read_bytes())
        if provider != {"returncode": 0}:
            result = {**assignment, "candidate": job["candidate"], "contract_sha256": self.controller.contract_hash,
                      "status": "failed", "error_type": "RolloutWorkerError"}
        else:
            worker = json.loads((root / "result.json").read_bytes())
            verified = verify_rollout_dataset(
                root / "dataset", worker["dataset_sha256"], policy=self.policy, context=self.context,
                expected_policy=identity, expected_driver_sha256=assignment["driver_sha256"])
            result = {**assignment, "candidate": job["candidate"], "contract_sha256": self.controller.contract_hash,
                      "status": "complete", "dataset_sha256": worker["dataset_sha256"],
                      "groups": verified["groups"], "trajectories": verified["trajectories"],
                      "zero_variance_groups": verified["zero_variance_groups"], "usage": worker["usage"],
                      "seconds": worker["seconds"]}
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        await self.finish_provider(job_id, sandbox, "rollout")
        return {"result": result, "artifacts": receipt}

    async def evaluate(self, job_id, policy_identity_path, qwen_environment, driver_binary=None):
        job, specification, candidate = self.context_for(job_id, "evaluation")
        assignment = specification["assignment"]
        identity_bytes = Path(policy_identity_path).read_bytes()
        identity = json.loads(identity_bytes)
        endpoint = qwen_environment.get("QWEN_BASE_URL", "").rstrip("/")
        parsed = urlsplit(endpoint)
        if (canonical(identity) != identity_bytes or policy_digest(identity) != candidate["policy_sha256"]
                or parsed.scheme != "https" or parsed.username or parsed.password
                or digest(endpoint.encode()) != identity.get("deployment", {}).get("endpoint_sha256")
                or len(qwen_environment.get("QWEN_API_KEY", "")) < 32):
            raise ValueError("Evaluation serving identity or credentials differ from the candidate")
        validate_policy_identity(identity, self.policy)
        driver = b""
        selected_driver = "/usr/local/bin/cua-driver"
        staged = {"contract.json": self.controller.contract_path.read_bytes(),
                  "assignment.json": canonical(assignment), "candidate.json": canonical(candidate),
                  "policy.json": identity_bytes}
        if driver_binary is not None:
            driver = Path(driver_binary).read_bytes()
            if digest(driver) != candidate["driver_sha256"]:
                raise ValueError("Evaluation driver binary differs from the candidate")
            staged["cua-driver"] = driver
        elif candidate["driver_sha256"] != self.controller.contract["spec"].get("baseline_driver_sha256"):
            raise ValueError("A nonbaseline evaluation driver must be staged explicitly")
        env = "\n".join(f"export {name}={shlex.quote(qwen_environment[name])}"
                         for name in ("QWEN_API_KEY", "QWEN_BASE_URL")) + "\n"
        staged["qwen.env"] = env.encode()

        def command(root):
            driver_path = root + "/cua-driver" if driver else selected_driver
            setup = f"chmod 500 {shlex.quote(driver_path)} && " if driver else ""
            return (
                f"chmod 600 {shlex.quote(root + '/qwen.env')} && . {shlex.quote(root + '/qwen.env')} && "
                f"rm -f {shlex.quote(root + '/qwen.env')} && export QWEN_API_KEY QWEN_BASE_URL DISPLAY=:1 "
                f"GAMEWORLD_HOME=/opt/GameWorld && {setup}"
                f"/opt/gameworld-venv/bin/python -m fps_bench.gameworld_candidate_episode "
                f"--contract {shlex.quote(root + '/contract.json')} "
                f"--contract-sha256 {shlex.quote(self.controller.contract_hash)} "
                f"--assignment {shlex.quote(root + '/assignment.json')} "
                f"--candidate {shlex.quote(root + '/candidate.json')} "
                f"--policy-identity {shlex.quote(root + '/policy.json')} "
                f"--output {shlex.quote(root + '/output')} --driver {shlex.quote(driver_path)}"
            )

        sandbox, root, receipt = await self.execute(
            job_id, "evaluation", staged, command, MAX_EVALUATION_ARCHIVE)
        provider = json.loads((root / "provider-result.json").read_bytes())
        if provider != {"returncode": 0}:
            result = {**assignment, "candidate": job["candidate"], "contract_sha256": self.controller.contract_hash,
                      "status": "failed", "error_type": "EvaluationWorkerError"}
        else:
            result = verify_evaluation_artifacts(
                root, self.controller.contract_hash, assignment, candidate, identity)
        self.controller.record_result(job_id, result, digest(canonical(receipt)))
        await self.finish_provider(job_id, sandbox, "evaluation")
        return {"result": result, "artifacts": receipt}
