"""Reconcile one stopped Modal deployment against its retained campaign hold."""

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sqlite3

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.evaluation_contract import canonical, digest, exclusive_write
from fps_bench.modal_billing import normalize_report, utc_hour
from fps_bench.modal_reconciliation import reconcile


CAMPAIGN = "gameworld-joint-20260913"


def load_deployment(path):
    path = Path(path)
    data = path.read_bytes()
    deployment = json.loads(data)
    required = {"app_id", "app_name", "environment", "function_id", "function_tag", "image_ids", "served_model",
                "source_sha256", "config_sha256", "deployment_tag", "deployment_version",
                "git_commit", "recorded_at", "schema_version", "web_url", "modal_client_version"}
    if (path.is_symlink() or canonical(deployment) != data or set(deployment) != required
            or deployment["schema_version"] != 1
            or not re.fullmatch(r"ap-[A-Za-z0-9]+", deployment["app_id"])
            or not deployment["app_name"].startswith("gameworld-")
            or not re.fullmatch(r"fu-[A-Za-z0-9]+", deployment["function_id"])
            or not isinstance(deployment["function_tag"], str) or not deployment["function_tag"]
            or not isinstance(deployment["image_ids"], list) or not deployment["image_ids"]
            or deployment["image_ids"] != sorted(set(deployment["image_ids"]))
            or any(not re.fullmatch(r"im-[A-Za-z0-9]+", image) for image in deployment["image_ids"])
            or not re.fullmatch(r"[0-9a-f]{64}", deployment["source_sha256"])
            or not re.fullmatch(r"[0-9a-f]{64}", deployment["config_sha256"])
            or not re.fullmatch(r"[0-9a-f]{40}", deployment["git_commit"])):
        raise ValueError("Modal deployment manifest is not canonical or complete")
    return data, deployment


def backup_database(source, destination):
    source_connection = sqlite3.connect(f"file:{Path(source).resolve()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    os.chmod(destination, 0o400)


async def run(args):
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    ledger = CampaignLedger(args.database)
    if ledger.snapshot()["campaign"]["id"] != CAMPAIGN:
        raise ValueError("Canonical GameWorld ledger required")
    deployment_data, deployment = load_deployment(args.deployment)
    scope = {
        "workspace": args.workspace, "environment": deployment["environment"],
        "object_ids": [deployment["app_id"]], "start": args.start, "end": args.end,
    }
    normalize_report([], scope)
    if args.output.exists():
        raise FileExistsError("Use a new evidence directory for each provider retrieval")
    args.output.mkdir(parents=True, mode=0o700)
    exclusive_write(args.output / "deployment.json", deployment_data, 0o400)
    backup_database(args.database, args.output / "campaign-before.sqlite")

    workspace = await modal.Workspace.from_context().hydrate.aio()
    if workspace.name != args.workspace:
        raise ValueError("Active Modal credentials belong to another workspace")
    report = await workspace.billing.report.aio(
        start=utc_hour(args.start), end=utc_hour(args.end), resolution="h")
    rows = [{"object_id": row.object_id, "environment": row.environment_name,
             "interval_start": row.interval_start.isoformat(), "cost": str(row.cost),
             "cost_by_resource": {key: str(value) for key, value in row.cost_by_resource.items()}}
            for row in report if row.object_id == deployment["app_id"]]
    normalize_report(rows, scope)
    provider = {
        "scope": scope, "method": "Workspace.billing.report", "rows": rows,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sdk_version": importlib.metadata.version("modal"),
    }
    exclusive_write(args.output / "provider-report.json", canonical(provider), 0o400)

    client = await _Client.from_env()
    lifecycle = (await client.stub.AppGetLifecycle(
        api_pb2.AppGetLifecycleRequest(app_id=deployment["app_id"]))).lifecycle
    tasks = await client.stub.TaskList(api_pb2.TaskListRequest(app_id=deployment["app_id"]))
    lookup = await client.stub.AppGetByDeploymentName(api_pb2.AppGetByDeploymentNameRequest(
        name=deployment["app_name"], environment_name=deployment["environment"]))
    observed_app_id = lookup.app_id or lookup.previous_app_id
    if (lifecycle.app_state != api_pb2.APP_STATE_STOPPED or tasks.tasks
            or observed_app_id != deployment["app_id"]
            or lookup.environment_name != deployment["environment"]
            or not lifecycle.stopped_at):
        raise ValueError("Modal deployment is not stopped or differs from launch identity")
    running_sandboxes = [sandbox.object_id async for sandbox in
                         modal.Sandbox.list.aio(app_id=deployment["app_id"])]
    if running_sandboxes:
        raise ValueError("Stopped deployment still owns running sandboxes")
    finished_at = datetime.fromtimestamp(lifecycle.stopped_at, timezone.utc).isoformat()
    resource = {
        "reservation_id": args.reservation_id, "kind": "deployed_app",
        "provider_id": deployment["app_id"], "app_id": deployment["app_id"],
        "deployment_name": deployment["app_name"], "observed_deployment_name": deployment["app_name"],
        "observed_app_id": observed_app_id, "function_id": deployment["function_id"],
        "function_tag": deployment["function_tag"],
        "image_ids": sorted(deployment["image_ids"]),
        "deployment_manifest_sha256": digest(deployment_data),
        "state": "stopped", "running_tasks": 0, "finished_at": finished_at,
    }
    closure = {
        "scope": scope, "resources": [resource], "running_sandbox_ids": running_sandboxes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "provider_report_sha256": digest(canonical(provider)),
    }
    exclusive_write(args.output / "closure.json", canonical(closure), 0o400)
    specification = {"scope": scope, "reservation_ids": [args.reservation_id],
                     "policy": "retain-full-allocation-no-refund-v1"}
    result = reconcile(ledger, specification, rows, closure)
    exclusive_write(args.output / "reconciliation.json", canonical(result), 0o400)
    print(json.dumps({key: value for key, value in result.items() if key != "snapshot"}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--workspace", default="cuaai")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
