"""Create a dedicated empty app using existing contributor-authorized APIs."""

import argparse
import asyncio
import json
from pathlib import Path

from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope


async def setup(args):
    import modal

    if not args.app.startswith("gameworld-"):
        raise ValueError("Dedicated GameWorld app name required")
    workspace = await modal.Workspace.from_context().hydrate.aio()
    if workspace.name != args.workspace:
        raise ValueError("Workspace mismatch")
    environment = await modal.Environment.from_name(args.environment).hydrate.aio()
    try:
        await modal.App.lookup.aio(args.app, environment_name=args.environment, create_if_missing=False)
    except modal.exception.NotFoundError:
        pass
    else:
        raise ValueError("App already exists; do not silently adopt it")
    args.output.mkdir(parents=True, exist_ok=False)
    scope = {"workspace": args.workspace, "environment": args.environment, "environment_id": environment.object_id,
             "app": args.app, "isolation_policy": "app-scoped"}
    exclusive_write(args.output / "intent.json", canonical(scope))
    app = await modal.App.lookup.aio(args.app, environment_name=args.environment, create_if_missing=True)
    scope["app_id"] = app.app_id
    exclusive_write(args.output / "scope.json", canonical(scope))
    observed = await inspect_app_scope(args.workspace, args.environment, args.app)
    validate_app_scope(observed, scope)
    exclusive_write(args.output / "verified.json", canonical(observed))
    print(json.dumps(observed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--output", required=True, type=Path)
    asyncio.run(setup(parser.parse_args()))


if __name__ == "__main__":
    main()
