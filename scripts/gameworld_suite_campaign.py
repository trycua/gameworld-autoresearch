"""Run the bounded all-catalog compatibility baseline on the managed Fleet pool."""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import time
from urllib.parse import urlsplit

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.gameworld_suite_catalog import load
from fps_bench.gameworld_suite_episode import SERVED_MODEL
from fps_bench.qwen_baseline import endpoint, request
from fps_bench.telemetry import ResearchTelemetry


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "gameworld-joint-20260913"
POOL = "gameworld-autoresearch"
QWEN_HOST = "cuaai--gameworld-qwen-baseline-serve.modal.run"
EPISODE_SOURCE = ROOT / "fps_bench/gameworld_suite_episode.py"
RESERVATION_MICRO_USD = 100_000_000
MAX_DURATION_SECONDS = 21_600


def assignments(manifest, manifest_hash, seed):
    return [
        {
            "id": f"{game['game']}--{task['task']}",
            "game": game["game"],
            "task": task["task"],
            "seed": seed,
            "served_model": SERVED_MODEL,
            "catalog_manifest_sha256": manifest_hash,
        }
        for game in manifest["games"]
        for task in game["tasks"]
    ]


def validate_summary(summary):
    required = {"status", "success", "steps", "invalid_actions", "execution_status",
                "progress", "usage", "seconds", "evaluation"}
    if (not isinstance(summary, dict) or set(summary) != required
            or summary["status"] != "complete" or type(summary["success"]) is not bool
            or summary["steps"] != 1 or type(summary["invalid_actions"]) is not int
            or not isinstance(summary["execution_status"], str)
            or type(summary["progress"]) not in (int, float) or not 0 <= summary["progress"] <= 1
            or type(summary["seconds"]) not in (int, float) or summary["seconds"] < 0
            or set(summary["usage"]) != {"prompt_tokens", "completion_tokens"}
            or any(type(value) is not int or value < 0 for value in summary["usage"].values())):
        raise ValueError("Invalid suite episode summary")
    return summary


def qwen_environment(path):
    values = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        name, separator, encoded = line.partition("=")
        if separator and name in {"QWEN_API_KEY", "QWEN_BASE_URL"}:
            decoded = shlex.split(encoded)
            if len(decoded) != 1:
                raise ValueError("Invalid Qwen environment value")
            values[name] = decoded[0]
    if len(values.get("QWEN_API_KEY", "")) < 32:
        raise ValueError("Qwen API key is missing or too short")
    parsed = urlsplit(values.get("QWEN_BASE_URL", ""))
    if parsed.scheme != "https" or parsed.hostname != QWEN_HOST or parsed.path.rstrip("/") != "/v1":
        raise ValueError("Qwen endpoint differs from the pinned baseline deployment")
    return values


def write_once(path, data):
    payload = data if isinstance(data, bytes) else canonical(data)
    path = Path(path)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Immutable output changed: {path}")
        return False
    exclusive_write(path, payload)
    return True


class FailureGate:
    def __init__(self, maximum=3):
        self.maximum = maximum
        self.consecutive = 0
        self.stopped = asyncio.Event()
        self.lock = asyncio.Lock()

    async def success(self):
        async with self.lock:
            self.consecutive = 0

    async def failure(self):
        async with self.lock:
            self.consecutive += 1
            if self.consecutive >= self.maximum:
                self.stopped.set()


class SuiteCampaign:
    def __init__(self, args):
        self.args = args
        self.output = args.output
        self.events_path = self.output / "events.jsonl"
        self.event_lock = asyncio.Lock()
        self.gate = FailureGate()
        self.ledger = CampaignLedger(args.database)
        self.manifest, summary = load(args.manifest)
        self.manifest_hash = summary["manifest_sha256"]
        self.jobs = assignments(self.manifest, self.manifest_hash, args.seed)
        self.source = EPISODE_SOURCE.read_bytes()
        self.source_hash = digest(self.source)
        self.qwen = qwen_environment(args.qwen_env)
        self.telemetry = None
        self.intent = self.initialize()

    def initialize(self):
        snapshot = self.ledger.snapshot()
        if snapshot["campaign"]["id"] != CAMPAIGN or snapshot["campaign"]["frozen"]:
            raise ValueError("Healthy canonical campaign ledger required")
        static = {
            "schema_version": 1,
            "campaign": CAMPAIGN,
            "phase": "all-catalog-one-step-compatibility-baseline",
            "pool": self.args.pool,
            "workers": self.args.workers,
            "seed": self.args.seed,
            "catalog_manifest_sha256": self.manifest_hash,
            "episode_source_sha256": self.source_hash,
            "qwen_endpoint_sha256": digest(self.qwen["QWEN_BASE_URL"].encode()),
            "served_model": SERVED_MODEL,
            "assignment_count": len(self.jobs),
            "reservation_micro_usd": RESERVATION_MICRO_USD,
            "reservation_basis": "Conservative shared hold for deploying and using one max-concurrency Qwen L4 endpoint during a six-hour supervised sweep; retained until provider reconciliation",
        }
        intent_path = self.output / "intent.json"
        if self.args.resume:
            intent = json.loads(intent_path.read_bytes())
            for key, value in static.items():
                if intent.get(key) != value:
                    raise ValueError(f"Resume identity changed: {key}")
            if int(time.time()) >= intent["deadline"]:
                raise ValueError("Campaign deadline has passed")
        else:
            self.output.mkdir(parents=True, exist_ok=False)
            now = int(time.time())
            intent = {
                **static,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "deadline": now + self.args.duration,
                "reservation_expires_at": now + self.args.duration + 3600,
                "reservation_id": "suite-baseline-v1-" + self.manifest_hash[:16],
            }
            write_once(intent_path, intent)
        self.ledger.reserve(intent["reservation_id"], "modal_micro_usd",
                            intent["reservation_micro_usd"], intent["reservation_expires_at"])
        self.telemetry = ResearchTelemetry(self.output / "telemetry.sqlite", CAMPAIGN)
        return intent

    async def event(self, kind, payload):
        row = canonical({"timestamp": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload})
        async with self.event_lock:
            with self.events_path.open("ab") as handle:
                handle.write(row)
                handle.flush()
                os.fsync(handle.fileno())

    def completed(self, job):
        root = self.output / "episodes" / job["id"]
        return (root / "receipt.json").is_file() or (root / "error.json").is_file()

    async def preflight(self):
        await self.event("preflight_started", {"assignment_count": len(self.jobs)})
        models = await asyncio.to_thread(request, endpoint(), "/models", 900)
        if SERVED_MODEL not in [item.get("id") for item in models.get("data", [])]:
            raise ValueError("Pinned Qwen model is not served")
        await self.event("preflight_complete", {"served_model": SERVED_MODEL})

    async def episode(self, sandbox, lane, job):
        local = self.output / "episodes" / job["id"]
        local.mkdir(parents=True, exist_ok=True)
        remote_root = "/tmp/gameworld-suite"
        remote_output = f"{remote_root}/{job['id']}"
        remote_config = f"{remote_root}/{job['id']}.json"
        remote_archive = f"{remote_root}/{job['id']}.tar.gz"
        await sandbox.files.write_bytes(remote_config, canonical({key: job[key] for key in (
            "game", "task", "seed", "served_model", "catalog_manifest_sha256")}))
        await self.event("episode_started", {"lane": lane, "id": job["id"], "game": job["game"], "task": job["task"]})
        command = f"""
set +e
rm -rf {shlex.quote(remote_output)} {shlex.quote(remote_archive)}
. /tmp/gameworld-qwen.env
export QWEN_API_KEY QWEN_BASE_URL DISPLAY=:1 GAMEWORLD_HOME=/opt/GameWorld
PYTHONPATH=/opt/gameworld-autoresearch /opt/gameworld-venv/bin/python /tmp/gameworld-suite-episode.py \
  --config {shlex.quote(remote_config)} --output {shlex.quote(remote_output)}
episode_rc=$?
tar -C {shlex.quote(remote_root)} -czf {shlex.quote(remote_archive)} {shlex.quote(job['id'])} 2>/dev/null
archive_rc=$?
if [ "$episode_rc" -ne 0 ]; then exit "$episode_rc"; fi
exit "$archive_rc"
"""
        result = await sandbox.shell.run(command, timeout=240)
        archive = await sandbox.files.read_bytes(remote_archive) if await sandbox.files.exists(remote_archive) else b""
        if archive:
            if len(archive) > 16 * 1024 * 1024:
                raise ValueError("Episode archive exceeds 16 MiB")
            write_once(local / "artifacts.tar.gz", archive)
        manifest = await sandbox.files.read_bytes(remote_output + "/manifest.json") if await sandbox.files.exists(remote_output + "/manifest.json") else b""
        summary_raw = await sandbox.files.read_bytes(remote_output + "/summary.json") if await sandbox.files.exists(remote_output + "/summary.json") else b""
        if manifest:
            write_once(local / "manifest.json", manifest)
        if result.success and summary_raw:
            summary = validate_summary(json.loads(summary_raw))
            write_once(local / "summary.json", summary_raw)
            receipt = {"id": job["id"], "game": job["game"], "task": job["task"], "lane": lane,
                       "claim": sandbox.claim_name, "sandbox": sandbox.name,
                       "episode_source_sha256": self.source_hash,
                       "archive_sha256": digest(archive), "summary": summary}
            write_once(local / "receipt.json", receipt)
            await self.event("episode_complete", {"lane": lane, "id": job["id"],
                                                   "success": summary["success"],
                                                   "execution_status": summary["execution_status"]})
            await self.gate.success()
        else:
            error = {"id": job["id"], "game": job["game"], "task": job["task"], "lane": lane,
                     "claim": sandbox.claim_name, "sandbox": sandbox.name,
                     "returncode": result.returncode, "stdout": result.stdout[-2000:],
                     "stderr": result.stderr[-2000:], "archive_sha256": digest(archive) if archive else None}
            write_once(local / "error.json", error)
            await self.event("episode_failed", {"lane": lane, "id": job["id"],
                                                 "returncode": result.returncode})
            await self.gate.failure()
        await sandbox.shell.run(f"rm -rf {shlex.quote(remote_output)} {shlex.quote(remote_config)} {shlex.quote(remote_archive)}", timeout=30)

    def aggregate(self):
        receipts, errors = [], []
        for job in self.jobs:
            root = self.output / "episodes" / job["id"]
            if (root / "receipt.json").is_file():
                receipts.append(json.loads((root / "receipt.json").read_bytes()))
            elif (root / "error.json").is_file():
                errors.append(json.loads((root / "error.json").read_bytes()))
        successes = sum(item["summary"]["success"] for item in receipts)
        prompt_tokens = sum(item["summary"]["usage"]["prompt_tokens"] for item in receipts)
        completion_tokens = sum(item["summary"]["usage"]["completion_tokens"] for item in receipts)
        return {
            "assignments": len(self.jobs), "completed": len(receipts), "failed": len(errors),
            "pending": len(self.jobs) - len(receipts) - len(errors), "successes": successes,
            "success_rate": successes / len(receipts) if receipts else 0,
            "mean_progress": (sum(item["summary"]["progress"] for item in receipts) / len(receipts)) if receipts else 0,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "execution_statuses": dict(Counter(item["summary"]["execution_status"] for item in receipts)),
        }

    async def emit(self, started, final=False):
        aggregate = self.aggregate()
        count = aggregate["completed"] + aggregate["failed"]
        self.telemetry.record(
            f"suite-baseline-v1-{count}-{'final' if final else 'running'}",
            "gameworld-eval",
            {"experiment": "suite-baseline-v1", "phase": "baseline", "split": "catalog",
             "task": "all", "change_class": "baseline", "outcome": "complete" if final else "running"},
            {"gameworld_eval_completed_episodes": aggregate["completed"],
             "gameworld_eval_failed_episodes": aggregate["failed"],
             "gameworld_eval_success_rate": aggregate["success_rate"],
             "gameworld_eval_mean_progress": aggregate["mean_progress"],
             "gameworld_eval_seconds": time.monotonic() - started},
        )
        flush = self.telemetry.flush()
        await self.event("aggregate", {**aggregate, "telemetry": flush})
        return aggregate

    async def worker(self, pool, lane, queue, started):
        claim = f"gw-suite-{self.manifest_hash[:8]}-w{lane}"
        async with pool.claim(name=claim, service="server", time_to_start=900,
                              ttl_seconds_after_created=MAX_DURATION_SECONDS) as sandbox:
            await self.event("worker_ready", {"lane": lane, "claim": claim, "sandbox": sandbox.name})
            await sandbox.files.write_bytes("/tmp/gameworld-suite-episode.py", self.source)
            remote_env = "\n".join(f"export {name}={shlex.quote(value)}" for name, value in sorted(self.qwen.items())) + "\n"
            await sandbox.files.write_bytes("/tmp/gameworld-qwen.env", remote_env.encode())
            try:
                setup = await sandbox.shell.run("rm -rf /tmp/gameworld-suite && mkdir -p /tmp/gameworld-suite && chmod 600 /tmp/gameworld-qwen.env", timeout=30)
                if not setup.success:
                    raise RuntimeError(setup.stderr)
                while not self.gate.stopped.is_set():
                    try:
                        job = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    try:
                        await self.episode(sandbox, lane, job)
                        aggregate = self.aggregate()
                        if (aggregate["completed"] + aggregate["failed"]) % 10 == 0:
                            await self.emit(started)
                    finally:
                        queue.task_done()
            finally:
                cleanup = await sandbox.shell.run(
                    "rm -rf /tmp/gameworld-qwen.env /tmp/gameworld-suite-episode.py /tmp/gameworld-suite",
                    timeout=30,
                )
                if not cleanup.success:
                    raise RuntimeError("Failed to scrub worker staging files")

    async def run(self):
        if self.args.prepare_only:
            await self.event("campaign_prepared", {"reservation_id": self.intent["reservation_id"],
                                                   "deadline": self.intent["deadline"]})
            print(json.dumps({"prepared": True, "intent": str(self.output / "intent.json"),
                              "reservation_id": self.intent["reservation_id"]}, indent=2))
            return 0
        if (self.output / "report.json").is_file():
            print(json.dumps(json.loads((self.output / "report.json").read_bytes()), indent=2))
            return 0
        started = time.monotonic()
        await self.preflight()
        from cua_sandbox import Pool
        pool = await Pool.get(self.args.pool)
        queue = asyncio.Queue()
        for job in self.jobs:
            if not self.completed(job):
                queue.put_nowait(job)
        workers = await asyncio.gather(
            *(self.worker(pool, lane, queue, started) for lane in range(self.args.workers)),
            return_exceptions=True,
        )
        worker_errors = [{"lane": lane, "type": type(error).__name__, "message": str(error)[-500:]}
                         for lane, error in enumerate(workers) if isinstance(error, BaseException)]
        aggregate = await self.emit(started, final=queue.empty() and not worker_errors)
        report = {**aggregate, "worker_errors": worker_errors,
                  "stopped_after_repeated_failures": self.gate.stopped.is_set(),
                  "finished_at": datetime.now(timezone.utc).isoformat(),
                  "reservation_id": self.intent["reservation_id"],
                  "reservation_reconciled": False}
        if aggregate["pending"] == 0 and not worker_errors:
            write_once(self.output / "report.json", report)
        else:
            write_once(self.output / f"stopped-{aggregate['completed'] + aggregate['failed']:03d}.json", report)
        print(json.dumps(report, indent=2), flush=True)
        return int(aggregate["pending"] != 0 or bool(worker_errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "configs/evaluation/gameworld-suite-v1.json")
    parser.add_argument("--qwen-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pool", default=POOL)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=int, default=MAX_DURATION_SECONDS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        parser.error("workers must be 1..2")
    if not 3600 <= args.duration <= MAX_DURATION_SECONDS:
        parser.error("duration must be 3600..21600 seconds")
    if args.pool != POOL:
        parser.error("the campaign is pinned to the Terraform-managed pool")
    if args.resume and args.prepare_only:
        parser.error("prepare-only creates a new campaign phase and cannot resume")
    raise SystemExit(asyncio.run(SuiteCampaign(args).run()))


if __name__ == "__main__":
    main()
