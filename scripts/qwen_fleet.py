# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["cua-sandbox==0.7.0"]
# ///
"""Manage this pilot's Fleet pool/claim without embedding credentials.

uv run scripts/qwen_fleet.py provision --state results/runs/fleet-pilot
uv run scripts/qwen_fleet.py exec --state results/runs/fleet-pilot --command 'uname -a'
"""

import argparse
import asyncio
import json
import hashlib
import shlex
import os
import re
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cua_sandbox import Image, Pool, Sandbox, WarmPoolAutoscaling

IMAGE = "public.ecr.aws/k5j5w0x5/cua-ubuntu-24.04@sha256:c1e601dbb748fdc467c663136f7592e308a91a3c19c309b75261544432826a57"


def check_public_ghcr(image):
    match = re.fullmatch(r"ghcr\.io/([a-z0-9._/-]+)@(sha256:[0-9a-f]{64})", image)
    if not match:
        raise ValueError("gVisor requires a pinned public GHCR image: ghcr.io/owner/image@sha256:...")
    repository, digest = match.groups()
    query = urllib.parse.urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
    with urllib.request.urlopen("https://ghcr.io/token?" + query, timeout=30) as response:
        token = json.load(response)["token"]
    req = urllib.request.Request(f"https://ghcr.io/v2/{repository}/manifests/{digest}", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    if "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("registry manifest digest mismatch")


def gvisor_requests(metadata):
    from fleet_sdk import (
        CreatePoolRequestBuilder, CreateTemplateRequestBuilder,
        OsGymSandboxTemplateSpecBuilder, OsGymSandboxWarmPoolSpecBuilder,
        PreservedJson, RuntimeKind, SandboxServiceBuilder, SandboxTemplateRefBuilder,
        ServiceProtocol, VmTemplateBuilder,
    )
    name = metadata["pool"]
    services = [SandboxServiceBuilder().name(label).target_port(port).protocol(ServiceProtocol.TCP).build()
                for label, port in (("server", 8000), ("novnc", 6080))]
    vm = (VmTemplateBuilder().container_disk_image(metadata["image"]).runtime(RuntimeKind.GVISOR)
          .cpu_cores(metadata["cpu"]).memory(f"{metadata['memory_mb']}Mi").services(services)
          .probes(PreservedJson.from_json(json.dumps({"readinessProbe": {"tcpSocket": {"port": 8000}}}))).build())
    template = (CreateTemplateRequestBuilder().namespace(name).name(name)
                .spec(OsGymSandboxTemplateSpecBuilder().vm_template(vm).build()).build())
    pool = (CreatePoolRequestBuilder().namespace(name)
            .spec(OsGymSandboxWarmPoolSpecBuilder().replicas(1)
                  .sandbox_template_ref(SandboxTemplateRefBuilder().name(name).build())
                  .autoscaling(WarmPoolAutoscaling(min_pool_size=0, initial_pool_size=1, max_pool_size=20))
                  .ttl_seconds_after_created(metadata["pool_ttl_seconds"]).build()).build())
    return pool, template


def save(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(data, output, indent=2)
        output.write("\n")


async def main(args):
    if args.operation == "provision":
        image = args.image or IMAGE
        if args.runtime == "gvisor":
            check_public_ghcr(image)
        args.state.mkdir(parents=True, exist_ok=False)
        name = "qwen-lplatform-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6]
        metadata = {"pool": name, "claim": "baseline", "image": image, "runtime": args.runtime,
                    "cpu": 4, "memory_mb": 16384, "min_pool_size": 0, "max_pool_size": 20, "pool_ttl_seconds": 21600,
                    "claim_ttl_seconds": 14400, "created_at": datetime.now(timezone.utc).isoformat()}
        save(args.state / "pool.json", metadata)
        if args.runtime == "gvisor":
            from cua_sandbox.pool import Template
            pool_request, template_request = gvisor_requests(metadata)
            pool = await Pool.reconcile(pool_request)
            template = await Template.reconcile(template_request)
            pool._owned_template = template.resource
        else:
            pool = await Pool.apply(
                Image.from_registry(image, kind="vm"), name=name,
                replicas=1, cpu=4, memory_mb=16384, services={"server": 8000, "novnc": 6080},
                autoscaling=WarmPoolAutoscaling(min_pool_size=0, initial_pool_size=1, max_pool_size=20),
                ttl_seconds_after_created=21600,
            )
        print(f"Pool created: {name}; waiting for desktop", flush=True)
        sandbox = await pool.claim(name="baseline", service="server", time_to_start=900,
                                   ttl_seconds_after_created=14400)
        try:
            save(args.state / "claim.json", sandbox.to_dict())
            print(f"Claim ready: {sandbox.claim_name}", flush=True)
            result = await sandbox.shell.run("uname -a; id; nproc; free -m; df -h /; command -v cua-driver; command -v cargo; echo DISPLAY=$DISPLAY", timeout=20)
            (args.state / "initial-probe.txt").write_text(result.stdout + "\n" + result.stderr)
            print(result.stdout)
        finally:
            await sandbox.disconnect()
        return
    metadata = json.loads((args.state / "pool.json").read_text())
    if args.operation == "delete-pool":
        if not args.confirm:
            raise ValueError("--confirm is required to delete this owned pool")
        pool = await Pool.get(metadata["pool"])
        await pool.delete()
        print(f"Requested deletion: {metadata['pool']}")
        return
    reference = json.loads((args.state / "claim.json").read_text())
    async with Sandbox.from_dict(reference) as sandbox:
        if args.operation == "exec":
            result = await sandbox.shell.run(args.command, timeout=25)
            print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")
            if not result.success:
                raise SystemExit(result.returncode or 1)
        elif args.operation == "upload":
            staging = args.remote + ".parts-" + uuid.uuid4().hex[:8]
            result = await sandbox.shell.run(f"mkdir -m 700 {shlex.quote(staging)}", timeout=20)
            if not result.success:
                raise RuntimeError(result.stderr)
            digest = hashlib.sha256()
            parts = []
            with args.local.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    destination = f"{staging}/{len(parts):06d}"
                    await sandbox.files.write_bytes(destination, chunk)
                    digest.update(chunk)
                    parts.append(destination)
            command = "cat " + (" ".join(shlex.quote(part) for part in parts) or "/dev/null")
            command += f" > {shlex.quote(args.remote)} && sha256sum {shlex.quote(args.remote)}"
            result = await sandbox.shell.run(command, timeout=25)
            if not result.success or result.stdout.split()[0] != digest.hexdigest():
                raise RuntimeError("upload integrity check failed")
            await sandbox.files.remove_dir(staging)
            print(f"Upload complete: {digest.hexdigest()}")
        elif args.operation == "download":
            args.local.parent.mkdir(parents=True, exist_ok=True)
            total = await sandbox.files.size(args.remote)
            digest = hashlib.sha256()
            temporary = args.local.with_suffix(args.local.suffix + ".partial")
            with temporary.open("wb") as destination:
                offset = 0
                while offset < total:
                    chunk = await sandbox.files.read_bytes(args.remote, offset=offset, length=min(1024 * 1024, total - offset))
                    if not chunk:
                        raise RuntimeError("short download")
                    destination.write(chunk)
                    digest.update(chunk)
                    offset += len(chunk)
            result = await sandbox.shell.run(f"sha256sum {shlex.quote(args.remote)}", timeout=20)
            if not result.success or result.stdout.split()[0] != digest.hexdigest():
                raise RuntimeError("download integrity check failed")
            temporary.replace(args.local)
            print(f"Download complete: {digest.hexdigest()}")
        elif args.operation == "release":
            await sandbox.close()
            print(f"Released claim: {metadata['claim']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("provision", "exec", "upload", "download", "release", "delete-pool"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--runtime", choices=("vm", "gvisor"), default="vm")
    parser.add_argument("--image")
    parser.add_argument("--command")
    parser.add_argument("--local", type=Path)
    parser.add_argument("--remote")
    parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args()
    if arguments.operation == "exec" and not arguments.command:
        parser.error("exec requires --command")
    if arguments.operation in ("upload", "download") and not (arguments.local and arguments.remote):
        parser.error("transfer requires --local and --remote")
    asyncio.run(main(arguments))
