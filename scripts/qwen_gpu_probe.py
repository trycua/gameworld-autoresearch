"""Supervised L40S probe with a canonical ledger hold and explicit shutdown."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import time

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.modal_artifacts import ModalSandboxFiles
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION, verify_adapter


async def run(args):
    import modal
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", args.probe_id):
        raise ValueError("Bounded unique probe ID required")
    ledger = CampaignLedger(args.database)
    if ledger.snapshot()["campaign"]["id"] != "gameworld-joint-20260913":
        raise ValueError("Canonical campaign ledger required")
    scope = json.loads(args.scope.read_bytes())
    validate_app_scope(await inspect_app_scope(scope["workspace"], scope["environment"], scope["app"]), scope)
    image_import = json.loads(args.image_import.read_bytes())
    if image_import["specification"]["scope"] != scope:
        raise ValueError("Image import belongs to another scope")
    image = (args.episode / "000.png").read_bytes()
    first = json.loads((args.episode / "trajectory.jsonl").read_text().splitlines()[0])
    if first["observation"] != "000.png" or first["observation_sha256"] != digest(image):
        raise ValueError("Historical screenshot differs from recorded rollout")
    source = {"source": "gameworld-pristine-v2", "seed": 42, "step": 0,
              "image_sha256": digest(image), "response": first["response"], "frozen_campaign_data": False}
    worker = Path("scripts/qwen_gpu_probe_worker.py").read_bytes()
    args.output.mkdir(parents=True, exist_ok=False)
    name = "gw-" + args.probe_id
    plan = {"probe_id": args.probe_id, "scope": scope, "image_id": image_import["image_id"], "source": source,
            "worker_sha256": digest(worker), "timeout_seconds": 900, "gpu": "L40S", "cpu": 4, "memory_mib": 32768}
    tags = {"campaign": "gameworld-joint-20260913", "probe": args.probe_id, "identity": digest(canonical(plan))}
    try:
        await modal.Sandbox.from_name.aio(scope["app"], name, environment_name=scope["environment"])
    except modal.exception.NotFoundError:
        pass
    else:
        raise ValueError("Probe name already exists; reconcile rather than create again")
    ledger.reserve(args.probe_id, "modal_micro_usd", 10_000_000, int(time.time()) + 3600)
    exclusive_write(args.output / "intent.json", canonical({**plan, "tags": tags, "reservation_micro_usd": 10_000_000}))
    exclusive_write(args.output / "input.json", canonical(source))
    sandbox = None
    try:
        app = await modal.App.lookup.aio(scope["app"], environment_name=scope["environment"], create_if_missing=False)
        if app.app_id != scope["app_id"]:
            raise ValueError("App was replaced")
        sandbox = await asyncio.wait_for(modal.Sandbox.create.aio(
            "/bin/sleep", "900", app=app, image=modal.Image.from_id(image_import["image_id"]),
            name=name, tags=tags, gpu="L40S", cpu=(4, 4), memory=(32768, 32768), timeout=900,
            block_network=True, secrets=[], volumes={}, network_file_systems={}, include_oidc_identity_token=False,
            env={"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}), 180)
        exclusive_write(args.output / "sandbox.json", canonical({"sandbox_id": sandbox.object_id, "tags": tags}))
        print(json.dumps({"sandbox_id": sandbox.object_id, "status": "created"}), flush=True)
        files = ModalSandboxFiles(sandbox.object_id)
        provenance = await files.read("/app/training-image.json")
        if digest(provenance) != digest(args.image_source.read_bytes()):
            raise ValueError("Imported worker provenance differs from CI")
        process = await sandbox.exec.aio("python", "-c", "import os; os.mkdir('/input')", timeout=30)
        if await process.wait.aio() != 0:
            raise ValueError("Input directory already exists")
        for path, data in (("000.png", image), ("input.json", canonical(source)), ("gpu_probe.py", worker)):
            await sandbox.filesystem.write_bytes.aio(data, "/input/" + path)
        process = await sandbox.exec.aio("python", "/input/gpu_probe.py", workdir="/app", timeout=600, secrets=[])
        stdout, stderr, code = await asyncio.wait_for(asyncio.gather(
            process.stdout.read.aio(), process.stderr.read.aio(), process.wait.aio()), 650)
        exclusive_write(args.output / "worker.stdout", stdout.encode())
        exclusive_write(args.output / "worker.stderr", stderr.encode())
        if code != 0:
            raise RuntimeError(f"GPU worker exited {code}; see captured stderr")
        report_data = await files.read("/output/probe.json")
        report = json.loads(report_data)
        if report["source"] != source or report["worker_sha256"] != digest(worker) or report["image_manifest_sha256"] != digest(provenance):
            raise ValueError("Probe result provenance mismatch")
        exclusive_write(args.output / "probe.json", report_data)
        adapter_manifest = await files.read("/output/training/adapter/adapter-manifest.json")
        manifest = json.loads(adapter_manifest)
        if set(manifest["files"]) - {"adapter_config.json", "adapter_model.safetensors", "README.md"}:
            raise ValueError("Unexpected checkpoint inventory")
        for path in ["result.json", "loss.jsonl", "adapter/adapter-manifest.json", *["adapter/" + path for path in manifest["files"]]]:
            exclusive_write(args.output / "training" / path, await files.read("/output/training/" + path), 0o400)
        verify_adapter(args.output / "training/adapter", report["training"]["adapter_manifest_sha256"],
                       BASE_MODEL, BASE_REVISION, digest(canonical(source)), digest(canonical(report["contract"])))
        print(json.dumps(report), flush=True)
    finally:
        if sandbox is None:
            try:
                sandbox = await asyncio.wait_for(modal.Sandbox.from_name.aio(scope["app"], name, environment_name=scope["environment"]), 30)
            except modal.exception.NotFoundError:
                exclusive_write(args.output / "cleanup-unresolved.json", canonical({"reason": "No acknowledged sandbox; hold retained"}))
        if sandbox is not None:
            if await sandbox.get_tags.aio() != tags:
                raise ValueError("Refusing to terminate mismatched sandbox")
            await asyncio.wait_for(sandbox.terminate.aio(wait=True), 120)
            code = await asyncio.wait_for(sandbox.poll.aio(), 30)
            if type(code) is not int:
                raise RuntimeError("Sandbox termination unconfirmed")
            exclusive_write(args.output / "terminated.json", canonical({"sandbox_id": sandbox.object_id,
                "returncode": code, "checked_at": datetime.now(timezone.utc).isoformat(), "billing_reconciled": False}))
            print(json.dumps({"status": "terminated", "sandbox_id": sandbox.object_id}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("database", "scope", "image-import", "image-source", "episode", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--probe-id", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
