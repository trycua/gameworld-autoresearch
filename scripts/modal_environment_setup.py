"""Create only a new, restricted GameWorld pilot environment; never alter main."""

import argparse
import asyncio
import json
import importlib.metadata
from pathlib import Path

from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.modal_environment import inspect_environment, validate_environment, PILOT_BUDGET_DOLLARS


async def setup(args):
    import modal
    from modal.client import _Client
    from modal_proto import api_pb2

    if importlib.metadata.version("modal") != "1.5.5":
        raise ValueError("Setup RPC mapping requires Modal 1.5.5")
    if not args.name.startswith("gameworld-"):
        raise ValueError("Only a new gameworld- environment may be created")
    workspace = await modal.Workspace.from_context().hydrate.aio()
    if workspace.name != args.workspace:
        raise ValueError("Modal workspace mismatch")
    environments = await modal.Environment.objects.list.aio()
    if any(environment.name == args.name for environment in environments):
        raise ValueError("Environment exists; inspect it rather than overwriting settings")
    args.output.mkdir(parents=True, exist_ok=False)
    exclusive_write(args.output / "intent.json", canonical({
        "workspace": args.workspace, "environment": args.name,
        "budget_dollars": PILOT_BUDGET_DOLLARS, "max_concurrent_gpus": 1,
        "max_concurrent_tasks": 2, "restricted": True, "default_member_role": "no-access"}))
    await modal.Environment.objects.create.aio(args.name, restricted=True, default_role="no-access")
    environment = await modal.Environment.from_name(args.name).hydrate.aio()
    exclusive_write(args.output / "created.json", canonical({"environment_id": environment.object_id, "name": args.name}))
    client = await _Client.from_env()
    await client.stub.EnvironmentSetBudget(api_pb2.EnvironmentSetBudgetRequest(
        environment_id=environment.object_id, cycle_budget_dollars=PILOT_BUDGET_DOLLARS))
    await client.stub.EnvironmentUpdate(api_pb2.EnvironmentUpdateRequest(
        current_name=args.name, max_concurrent_gpus=1, max_concurrent_tasks=2))
    observed = await inspect_environment(args.workspace, args.name)
    validate_environment(observed, args.name, environment.object_id)
    exclusive_write(args.output / "verified.json", canonical(observed))
    print(json.dumps(observed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(setup(args))


if __name__ == "__main__":
    main()
