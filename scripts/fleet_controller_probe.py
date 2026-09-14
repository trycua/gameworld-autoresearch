"""Real, bounded Fleet-only probe: claim, verify bundled driver, rebuild, release."""

import argparse
import asyncio
import json
from pathlib import Path
import time

from fps_bench.campaign_controller import CampaignController
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.fleet_provider import FleetLifecycle


PROBE = '''/opt/gameworld-venv/bin/python - <<'INNER'
import hashlib,json,pathlib,subprocess
root=pathlib.Path('/opt/gameworld-autoresearch')
config=json.loads((root/'configs/qwen-gameworld-baseline.json').read_text())
source=json.loads((root/'image-source.json').read_text())
print(json.dumps({'driver_sha256':hashlib.sha256(pathlib.Path('/usr/local/bin/cua-driver').read_bytes()).hexdigest(),
'driver_version':subprocess.check_output(['/usr/local/bin/cua-driver','--version']).decode().strip(),
'source_commit':source['git_commit'],'protocol':config['protocol']}))
INNER'''


async def run(args):
    if args.resume:
        if not (args.output / "controller.sqlite").is_file():
            raise ValueError("Resume requires an existing controller database")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
    controller = CampaignController(args.output / "controller.sqlite", args.contract, args.expected_hash)
    controller.initialize("fleet-only-prelaunch-" + args.output.name[-20:].replace("_", "-"), duration_seconds=3600)
    template = controller.contract["episode_template"]
    controller.register_candidate({"id": "baseline", "parent": None, "change_class": "baseline",
        "hypothesis": "Fleet-only infrastructure verification; not a benchmark or training run",
        "contract_hash": args.expected_hash, "image": controller.contract["spec"]["provenance"]["image"],
        "driver_sha256": args.expected_driver_hash,
        "policy_sha256": controller.contract["spec"]["policy_sha256"],
        "model": {"base_model": template["model"], "base_revision": template["revision"],
                  "processor_revision": template["revision"], "adapter_sha256": None, "served_model": template["served_model"]}})
    fleet = FleetLifecycle(controller, args.pool, args.output)
    before = await fleet.preflight(1800)
    if not (args.output / "pool-before.json").exists():
        exclusive_write(args.output / "pool-before.json", canonical(before))
    job = "warm-driver-probe"
    controller.admit_job(job, "baseline", "driver_build", {"pool": args.pool, "operation": "warm-driver-probe"}, {}, 900)
    sandbox = None
    failure = None
    try:
        sandbox = await fleet.acquire(job)
        initial = await sandbox.shell.run(PROBE, timeout=25)
        if not initial.success:
            raise RuntimeError("Initial driver probe failed")
        identity = json.loads(initial.stdout)
        exclusive_write(args.output / "driver-before.json", canonical(identity))
        if (identity["driver_sha256"] != args.expected_driver_hash or identity["source_commit"] != args.expected_source_commit
                or identity["protocol"] != "gameworld-2048-cua-qwen-v2"):
            raise RuntimeError("Claimed worker does not match pristine image provenance")
        started = time.monotonic()
        build = await sandbox.shell.run("timeout --kill-after=2s 20s bash /opt/gameworld-autoresearch/image/rebuild_driver.sh", timeout=25)
        exclusive_write(args.output / "rebuild.log", (build.stdout + "\n" + build.stderr).encode())
        seconds = time.monotonic() - started
        if not build.success:
            raise RuntimeError("Bounded warm rebuild failed; inspect exported log")
        final = await sandbox.shell.run(PROBE, timeout=25)
        if not final.success:
            raise RuntimeError("Post-build probe failed")
        rebuilt = json.loads(final.stdout)
        if rebuilt != identity:
            raise RuntimeError("Unmodified rebuild changed driver/source identity")
        claim = await fleet.backend.find_claim(args.pool, fleet.identity(job)[1]["claim"])
        if claim is None or not claim["sandbox_name"]:
            raise RuntimeError("Bound sandbox identity was not verified")
        result = {"status": "complete", "warm_rebuild_seconds": seconds, "driver": rebuilt, "claim": claim,
                  "template_runtime": before["runtime"],
                  "runtime_evidence": "Fleet template and bound sandbox identity, not a direct CRI attestation",
                  "modal_operations": 0, "qwen_inference_calls": 0, "benchmark_episode": False}
        exclusive_write(args.output / "probe-result.json", canonical(result))
        controller.record_result(job, result, digest(canonical(result)))
        print(json.dumps(result), flush=True)
    except Exception as error:
        failure = error
        error_path = args.output / "probe-error.json"
        if error_path.exists():
            error_path = args.output / f"probe-error-{time.time_ns()}.json"
        exclusive_write(error_path, canonical({"type": type(error).__name__, "message": str(error)}))
    finally:
        try:
            if sandbox is not None:
                await sandbox.disconnect()
        finally:
            await fleet.release(job)
        exclusive_write(args.output / "controller-after-release.json", canonical(controller.snapshot()))
    print(json.dumps({"claim_released": True, "probe_failed": failure is not None}), flush=True)
    if failure:
        raise failure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-hash", required=True)
    parser.add_argument("--expected-driver-hash", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
